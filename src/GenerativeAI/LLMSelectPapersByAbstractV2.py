import os
import sys
import json
from typing import Dict, List, Optional, Any, Union
from dotenv import load_dotenv
from pathlib import Path

from langchain.schema import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_deepseek import ChatDeepSeek
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field, field_validator 

# Local imports
from src.GenerativeAI.LLMUtils import run_prepare_base_prompt

# Load environment variables
load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("Config/.env"))

class AnswerWithComment(BaseModel):
    """
    Model for answers that include a YES/NO response with explanatory comment.
    
    Attributes:
        answer (str): Binary response to a question or criterion (YES or NO)
        comment (str): Explanation justifying the answer
    """
    answer: str = Field(..., description="Binary response to a question or criterion")
    comment: str = Field(..., description="Explanation justifying the answer")
    
    @field_validator('answer')
    @classmethod 
    def answer_must_be_yes_or_no(cls, v):
        """Validate that answer is either YES or NO."""
        if v not in ["YES", "NO"]:
            raise ValueError('answer must be either "YES" or "NO"')
        return v

class SupportingQuestionAnswer(BaseModel):
    """
    Model for flexible answers that include a response with explanatory comment.
    Unlike AnswerWithComment, this allows any string as an answer, not just YES/NO.
    
    Attributes:
        answer (str): Response to a question, which can be any classification or certainty level
        comment (str): Explanation justifying the answer
    """
    answer: str = Field(..., description="Response to a question, which can be any classification or certainty level")
    comment: str = Field(..., description="Explanation justifying the answer")

class ArticleAnalysis(BaseModel):
    """
    Model for individual article analysis.
    
    Attributes:
        id (str): Unique identifier for the article, typically a DOI
        research_questions (Dict[str, AnswerWithComment]): Questions about the research and their answers
        supporting_questions (Optional[Dict[str, SupportingQuestionAnswer]]): Supporting questions with flexible answers
        accepted_criteria (Optional[Dict[str, AnswerWithComment]]): Criteria for accepting articles
        rejection_criteria (Optional[Dict[str, AnswerWithComment]]): Criteria for rejecting articles
        is_relevant (AnswerWithComment): Final determination if the article is relevant to the research
        additional_questions_by_article (Optional[Dict[str, str]]): Additional questions specific to this article
    """
    id: str = Field(..., description="Unique identifier for the article, typically a DOI")
    research_questions: Dict[str, AnswerWithComment] = Field(
        ..., 
        description="Questions about the research and their answers"
    )
    supporting_questions: Optional[Dict[str, SupportingQuestionAnswer]] = Field(
        None,
        description="Supporting questions with flexible answer options"
    )
    accepted_criteria: Optional[Dict[str, AnswerWithComment]] = Field(
        None, 
        description="Criteria for accepting articles"
    )
    rejection_criteria: Optional[Dict[str, AnswerWithComment]] = Field(
        None, 
        description="Criteria for rejecting articles"
    )
    is_relevant: AnswerWithComment = Field(
        ..., 
        description="Final determination if the article is relevant to the research"
    )
    additional_questions_by_article: Optional[Dict[str, str]] = Field(
        None, 
        description="Additional questions specific to this article"
    )
    
    @field_validator('research_questions') 
    @classmethod
    def research_questions_must_have_principal(cls, v):
        """Validate that research_questions contains principal_research_question."""
        if 'principal_research_question' not in v:
            raise ValueError('research_questions must contain principal_research_question')
        return v

class LLMResponseModel(BaseModel):
    """
    Model for the overall LLM response with article analyses.
    
    Attributes:
        articles (List[ArticleAnalysis]): Array of analyzed articles
        additional_questions_all_articles (Optional[Dict[str, str]]): Additional questions related to all articles collectively
    """
    articles: List[ArticleAnalysis] = Field(
        ..., 
        description="Array of analyzed articles"
    )
    additional_questions_all_articles: Optional[Dict[str, str]] = Field(
        None, 
        description="Additional questions related to all articles collectively"
    )


def get_openai_llm() -> ChatOpenAI:
    """
    Configure and return an OpenAI LLM instance.
    
    Returns:
        ChatOpenAI: Configured OpenAI chat model
    """
    api_key = os.getenv("LLM_API_KEY_ABSTRACT")
    model = os.getenv("LLM_MODEL_ABSTRACT", "gpt-4.1-nano")
    
    if not api_key:
        raise ValueError("LLM_API_KEY_ABSTRACT environment variable not set")
    
    return ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        request_timeout=300,
        max_retries=3,
    )


def get_gemini_llm() -> ChatGoogleGenerativeAI:
    """
    Configure and return a Google Gemini LLM instance.
    
    Returns:
        ChatGoogleGenerativeAI: Configured Gemini chat model
    """
    api_key = os.getenv("LLM_API_KEY_ABSTRACT")
    model = os.getenv("LLM_MODEL_ABSTRACT", "gemini-2.0-flash")
    
    if not api_key:
        raise ValueError("LLM_API_KEY_ABSTRACT environment variable not set")
    
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        request_timeout=300,
    )


def get_deepseek_llm() -> ChatOpenAI:
    """
    Configure and return a DeepSeek LLM instance using OpenAI compatibility.
    
    Returns:
        ChatOpenAI: Configured DeepSeek chat model
    """
    api_key = os.getenv("LLM_API_KEY_ABSTRACT")
    model = os.getenv("LLM_MODEL_ABSTRACT", "deepseek-chat")
    
    if not api_key:
        raise ValueError("LLM_API_KEY_ABSTRACT environment variable not set")

    # Using ChatOpenAI with DeepSeek base URL
    return ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        base_url=os.getenv("LLM_API_BASE_URL", "https://api.deepseek.com/v1"),
        request_timeout=300,
        max_retries=2,
    )


def setup_llm() -> BaseChatModel:
    """
    Set up and configure the LLM based on environment variables.
    
    Returns:
        BaseChatModel: Configured LLM chat model
        
    Raises:
        ValueError: If required environment variables are not set or if the LLM type is not supported
    """
    llm_type = os.getenv("LLM_API_TYPE_ABSTRACT", "OpenAI").lower()
    
    # Mapping of LLM types to their respective configuration functions
    llm_factories = {
        "openai": get_openai_llm,
        "gemini": get_gemini_llm,
        "deepseek": get_deepseek_llm,
    }
    
    if llm_type not in llm_factories:
        supported_types = ", ".join(llm_factories.keys())
        raise ValueError(f"Unsupported LLM type: {llm_type}. Supported types: {supported_types}")
    
    return llm_factories[llm_type]()


def save_raw_llm_response(raw_content: str, output_path: Optional[str] = None):
    """
    Save raw LLM response content to a text file.
    
    Args:
        raw_content (str): The raw string content returned by the LLM
        output_path (Optional[str]): Path to save the raw response, defaults to a standard location
    """
    try:
        path_data = os.getenv("PATH_DATA", ".data")
        # Obter informações do tipo e modelo LLM para incluir no nome do arquivo
        llm_type = os.getenv("LLM_API_TYPE_ABSTRACT", "OpenAI")
        llm_model = os.getenv("LLM_MODEL_ABSTRACT", "default")
        # Sanitizar o nome do modelo para uso em nomes de arquivo
        llm_model = llm_model.replace("/", "-").replace(":", "-")
        
        # Nome de arquivo com informações de tipo e modelo LLM
        filename = f"select_bibs_filtered_by_abstract_{llm_type}_{llm_model}_raw.txt"
        
        if not output_path:
            output_path = os.path.join(path_data, "OUTPUTS", filename)
        else:
            # Se output_path for fornecido mas não terminar com .txt, adicione o sufixo '_raw.txt'
            if not output_path.endswith('.txt'):
                base_path = output_path.rsplit('.', 1)[0] if '.' in output_path else output_path
                output_path = f"{base_path}_{llm_type}_{llm_model}_raw.txt"
            
            if not os.path.isabs(output_path):
                output_path = os.path.join(path_data, "OUTPUTS", output_path)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(raw_content)
            
        print(f"Raw LLM response saved to {output_path}")
    
    except Exception as e:
        raise Exception(f"Error saving raw LLM response: {e}")


def save_llm_response_to_file(response: LLMResponseModel, output_path: str):
    """
    Save LLM response to a file.
    
    Args:
        response: Validated LLM response
        output_path: Path to save the response
    """
    try:
        path_data = os.getenv("PATH_DATA", ".data")
        # Obter informações do tipo e modelo LLM para incluir no nome do arquivo
        llm_type = os.getenv("LLM_API_TYPE_ABSTRACT", "OpenAI")
        llm_model = os.getenv("LLM_MODEL_ABSTRACT", "default")
        # Sanitizar o nome do modelo para uso em nomes de arquivo
        llm_model = llm_model.replace("/", "-").replace(":", "-")
        
        # Nome de arquivo com informações de tipo e modelo LLM
        filename = f"select_bibs_filtered_by_abstract_{llm_type}_{llm_model}.json"
        
        if not output_path:
            output_path = os.path.join(path_data, "OUTPUTS", filename)
        elif not output_path.endswith('.json'):
            # Se output_path não terminar com .json, adicione as informações do LLM e o sufixo .json
            base_path = output_path.rsplit('.', 1)[0] if '.' in output_path else output_path
            output_path = f"{base_path}_{llm_type}_{llm_model}.json"
        
        if not os.path.isabs(output_path):
            output_path = os.path.join(path_data, "OUTPUTS", output_path)
            
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Converter para dict antes de salvar - usando model_dump() em vez de dict()
        response_dict = response.model_dump()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response_dict, f, ensure_ascii=False, indent=2)
            
        print(f"LLM response saved to {output_path}")
    
    except Exception as e:
        raise Exception(f"Error saving LLM response: {e}")


def analyze_abstracts_with_llm(input_bibtex_path: Optional[str] = None, 
                                output_path: Optional[str] = None) -> LLMResponseModel:
    """
    Analyze abstracts from BibTeX files using an LLM with a prepared prompt.
    
    Args:
        input_bibtex_path: Path to the BibTeX file to analyze
        output_path: Path to save the LLM response JSON
    
    Returns:
        LLMResponseModel: Validated LLM response
    """
    # Get the base prompt from LLMUtils
    base_prompt = run_prepare_base_prompt(input_bibtex_path)
    
    # Setup LLM
    chat_model = setup_llm()
    
    # Setup PydanticOutputParser with our model
    parser = PydanticOutputParser(pydantic_object=LLMResponseModel)
    
    try:
        print(f"Sending request to LLM...")
        
        # Format the prompt
        formatted_prompt = PromptTemplate(
            template="{base_prompt}\n\n{format_instructions}\n",
            input_variables=["base_prompt"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        ).format(base_prompt=base_prompt)
        
        messages = [HumanMessage(content=formatted_prompt)]
        
        # Get response from LLM
        llm_response = chat_model.invoke(messages)
        response_content = llm_response.content
        
        # Save raw response before any processing
        print("Saving raw LLM response...")
        save_raw_llm_response(response_content, output_path)
        
        # Try to parse the JSON response
        print("Parsing LLM response to JSON...")
        try:
            # Parse the raw content to JSON first
            response_json_dict = json.loads(response_content)
            
            # Then validate with Pydantic model
            response_json = LLMResponseModel.model_validate(response_json_dict)
            
            # Save processed response to file
            if output_path:
                save_llm_response_to_file(response_json, output_path)
            
            return response_json
        
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response as JSON: {e}")
            print("Raw response was saved, but could not be parsed as valid JSON")
            raise
        
        except Exception as e:
            print(f"Error validating LLM response with Pydantic model: {e}")
            print("Raw response was saved, but does not match expected schema")
            raise
    
    except Exception as e:
        print(f"Error during LLM analysis: {e}")
        raise


def run_select_bibs_filtered_by_abstract(input_bibtex_path: Optional[str] = None, output_path: Optional[str] = None):
    """
    Main function to run the LLM analysis pipeline.
    
    Args:
        input_bibtex_path: Path to the BibTeX file to analyze
        output_path: Path to save the output files
    """
    try:        
        print(f"Analyzing abstracts from {'default bibtex' if input_bibtex_path is None else input_bibtex_path}")
        
        # Run analysis
        response = analyze_abstracts_with_llm(input_bibtex_path, output_path)
        
        return response
        
    except Exception as e:
        print(f"Error in main function: {e}")
        sys.exit(1)
