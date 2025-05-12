import os
import sys
import json
from typing import Dict, List, Optional, Any, Union
from dotenv import load_dotenv
from pathlib import Path

# Langchain imports
from langchain.schema import HumanMessage
from langchain.chat_models import ChatOpenAI, AzureChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field, validator

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
    
    @validator('answer')
    def answer_must_be_yes_or_no(cls, v):
        """Validate that answer is either YES or NO."""
        if v not in ["YES", "NO"]:
            raise ValueError('answer must be either "YES" or "NO"')
        return v

class LLMResponseModel(BaseModel):
    """
    Model for LLM responses analyzing scientific articles.
    
    Attributes:
        research_questions (Dict[str, AnswerWithComment]): Questions about the research and their answers
        accepted_criteria (Optional[Dict[str, AnswerWithComment]]): Criteria for accepting articles
        rejection_criteria (Optional[Dict[str, AnswerWithComment]]): Criteria for rejecting articles
        additional_questions (Optional[Dict[str, str]]): Additional informational questions about the articles
        is_relevant (AnswerWithComment): Final determination if the article is relevant to the research
    """
    research_questions: Dict[str, AnswerWithComment] = Field(
        ..., 
        description="Questions about the research and their answers"
    )
    accepted_criteria: Optional[Dict[str, AnswerWithComment]] = Field(
        None, 
        description="Criteria for accepting articles"
    )
    rejection_criteria: Optional[Dict[str, AnswerWithComment]] = Field(
        None, 
        description="Criteria for rejecting articles"
    )
    additional_questions: Optional[Dict[str, str]] = Field(
        None, 
        description="Additional informational questions about the articles"
    )
    is_relevant: AnswerWithComment = Field(
        ..., 
        description="Final determination if the article is relevant to the research"
    )
    
    @validator('research_questions')
    def research_questions_must_have_principal(cls, v):
        """Validate that research_questions contains principal_research_question."""
        if 'principal_research_question' not in v:
            raise ValueError('research_questions must contain principal_research_question')
        return v


def setup_llm() -> Union[ChatOpenAI, AzureChatOpenAI]:
    """
    Set up and configure the LLM based on environment variables.
    
    Returns:
        Union[ChatOpenAI, AzureChatOpenAI]: Configured LLM chat model
        
    Raises:
        ValueError: If required environment variables are not set
    """
    api_key = os.getenv("LLM_API_KEY_ABSTRACT")
    api_url = os.getenv("LLM_API_URL_ABSTRACT")
    model = os.getenv("LLM_MODEL_ABSTRACT")
    
    if not api_key:
        raise ValueError("LLM_API_KEY_ABSTRACT environment variable not set")
    
    if api_url and "azure" in api_url.lower():
        # Setup for Azure OpenAI
        api_version = os.getenv("LLM_API_VERSION_ABSTRACT", "2023-05-15")
        deployment_name = os.getenv("LLM_DEPLOYMENT_NAME_ABSTRACT")
        
        if not deployment_name:
            raise ValueError("LLM_DEPLOYMENT_NAME_ABSTRACT environment variable not set for Azure OpenAI")
        
        return AzureChatOpenAI(
            azure_endpoint=api_url,
            openai_api_key=api_key,
            deployment_name=deployment_name,
            openai_api_version=api_version,
            temperature=0.0
        )
    else:
        # Setup for regular OpenAI
        return ChatOpenAI(
            model=model or "gpt-4",
            openai_api_key=api_key,
            temperature=0.0
        )


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
    prompt = run_prepare_base_prompt(input_bibtex_path)
    
    # Setup LLM
    chat_model = setup_llm()
    
    # Setup JSON output parser with our model
    parser = JsonOutputParser(pydantic_object=LLMResponseModel)
    
    try:
        print("Sending request to LLM... (This may take a few minutes)")
        # Send message to LLM
        messages = [HumanMessage(content=prompt)]
        llm_response = chat_model.predict_messages(messages)
        
        print("Parsing LLM response...")
        # Parse and validate response
        response_content = llm_response.content
        response_json = parser.parse(response_content)
        
        # Save response to file if output_path is specified
        if output_path:
            save_llm_response_to_file(response_json, output_path)
        
        return response_json
    
    except json.JSONDecodeError as e:
        print(f"Error parsing LLM response as JSON: {e}")
        print("Raw response:", llm_response.content)
        raise
    
    except Exception as e:
        print(f"Error during LLM analysis: {e}")
        raise


def save_llm_response_to_file(response: LLMResponseModel, output_path: str):
    """
    Save LLM response to a file.
    
    Args:
        response: Validated LLM response
        output_path: Path to save the response
    """
    try:
        path_data = os.getenv("PATH_DATA", ".data")
        if not os.path.isabs(output_path):
            output_path = os.path.join(path_data, "OUTPUTS", output_path)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Convert to dict before saving
        response_dict = response.dict()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response_dict, f, ensure_ascii=False, indent=2)
            
        print(f"LLM response saved to {output_path}")
    
    except Exception as e:
        print(f"Error saving LLM response: {e}")
        raise


def main(input_bibtex_path: Optional[str] = None):
    """
    Main function to run the LLM analysis pipeline.
    
    Args:
        input_bibtex_path: Path to the BibTeX file to analyze
    """
    try:
        # Define default output path
        output_path = "llm_abstract_analysis.json"
        
        print(f"Analyzing abstracts from {'default bibtex' if input_bibtex_path is None else input_bibtex_path}")
        
        # Run analysis
        response = analyze_abstracts_with_llm(input_bibtex_path, output_path)
        
        # Print summary
        print("\n=== Analysis Summary ===")
        print(f"Principal research question: {response.research_questions['principal_research_question'].answer}")
        print(f"Is article relevant: {response.is_relevant.answer}")
        print("=======================")
        
    except Exception as e:
        print(f"Error in main function: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Get input path from command line argument if provided
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        main(input_path)
    else:
        main()
