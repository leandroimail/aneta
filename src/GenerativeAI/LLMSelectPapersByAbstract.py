import os
import sys
import json
from typing import Dict, List, Optional, Any, Union, Literal, TypeVar, Generic, Type
from dotenv import load_dotenv
from pathlib import Path
import google.generativeai as genai
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator  # Atualizado para usar field_validator

# Local imports
from src.GenerativeAI.LLMUtils import run_prepare_base_prompt

# Load environment variables
load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("Config/.env"))

class AnswerWithComment(BaseModel):
    """
    Model for answers that include a yes/no response with explanatory comment.
    
    Attributes:
        answer (str): Binary response to a question or criterion (yes or no)
        comment (str): Explanation justifying the answer
    """
    answer: str = Field(..., description="Binary response to a question or criterion")
    comment: str = Field(..., description="Explanation justifying the answer")
    
    @field_validator('answer')  # Substituído validator por field_validator
    @classmethod  # Necessário no field_validator
    def answer_must_be_yes_or_no(cls, v):
        """Validate that answer is either yes or no."""
        if v not in ["yes", "no"]:
            raise ValueError('answer must be either "yes" or "no"')
        return v

class SupportingQuestionAnswer(BaseModel):
    """
    Model for flexible answers that include a response with explanatory comment.
    Unlike AnswerWithComment, this allows any string as an answer, not just yes/no.
    
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
    
    @field_validator('research_questions')  # Substituído validator por field_validator
    @classmethod  # Necessário no field_validator
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


# Define generic type for Pydantic models
T = TypeVar('T', bound=BaseModel)

# Define a base LLM client class for consistent interface
class LLMClient(Generic[T]):
    """Base class for LLM clients to provide a consistent interface."""
    
    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        Invoke the LLM with the given messages.
        
        Args:
            messages: List of message dicts with role and content
            
        Returns:
            str: The content of the LLM's response
        """
        raise NotImplementedError("Subclasses must implement invoke method")
    
    def parse(self, messages: List[Dict[str, str]], response_model: Type[T]) -> T:
        """
        Parse the LLM response directly into a Pydantic model.
        
        Args:
            messages: List of message dicts with role and content
            response_model: Pydantic model class to parse the response into
            
        Returns:
            T: Parsed response in the specified Pydantic model
        """
        raise NotImplementedError("Subclasses must implement parse method")


class OpenAIClient(LLMClient):
    """Client for OpenAI API with support for large context windows."""
    
    def __init__(self, api_key: str, model: str):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key
            model: Model name to use
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        Invoke the OpenAI model with the given messages.
        
        Args:
            messages: List of message dicts with role and content
            
        Returns:
            str: The content of the model's response
        """
        try:
            # Create request parameters
            request_params = {
                "model": self.model,
                "messages": messages,
            }
                
            response = self.client.chat.completions.create(**request_params)
            return response.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"Error invoking OpenAI model: {e}")
    
    def parse(self, messages: List[Dict[str, str]], response_model: Type[T]) -> T:
        """
        Parse the OpenAI response directly into a Pydantic model.
        
        Args:
            messages: List of message dicts with role and content
            response_model: Pydantic model class to parse the response into
            
        Returns:
            T: Parsed response in the specified Pydantic model
        """
        try:
            # Create request parameters with json format
            request_params = {
                "model": self.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
            
            completion = self.client.chat.completions.create(**request_params)
            response_content = completion.choices[0].message.content
            
            # Save raw response content
            save_raw_llm_response(response_content)
            
            # Parse JSON response
            parsed_response = json.loads(response_content)
            # Use model_validate instead of parse_obj which is deprecated in pydantic v2
            try:
                # Try pydantic v2 approach first
                return response_model.model_validate(parsed_response)
            except AttributeError:
                # Fall back to pydantic v1 approach
                return response_model.parse_obj(parsed_response)
            
        except Exception as e:
            raise Exception(f"Error parsing OpenAI response: {e}")

class DeepSeekClient(LLMClient):
    """Client for DeepSeek API using OpenAI-compatible interface."""
    
    def __init__(self, api_key: str, model: str):
        """
        Initialize DeepSeek client.
        
        Args:
            api_key: DeepSeek API key
            model: Model name to use
        """
        self.client = OpenAI(
            api_key=api_key, 
            base_url=os.getenv("LLM_API_BASE_URL", "https://api.deepseek.com/v1")
        )
        self.model = model
    
    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        Invoke the DeepSeek model with the given messages.
        
        Args:
            messages: List of message dicts with role and content
            
        Returns:
            str: The content of the model's response
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Error invoking DeepSeek model: {e}")
    
    def parse(self, messages: List[Dict[str, str]], response_model: Type[T]) -> T:
        """
        Parse the DeepSeek response directly into a Pydantic model.
        
        Args:
            messages: List of message dicts with role and content
            response_model: Pydantic model class to parse the response into
            
        Returns:
            T: Parsed response in the specified Pydantic model
        """
        try:
            # Force JSON response format if supported
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"}
            )
            response_content = completion.choices[0].message.content
            
            # Save raw response content
            save_raw_llm_response(response_content)
            
            # Parse JSON response
            parsed_response = json.loads(response_content)
            try:
                # Try pydantic v2 approach first
                return response_model.model_validate(parsed_response)
            except AttributeError:
                # Fall back to pydantic v1 approach
                return response_model.parse_obj(parsed_response)
            
        except Exception as e:
            raise Exception(f"Error parsing DeepSeek response: {e}")

class GeminiClient(LLMClient):
    """Client for Google Gemini API."""
    
    def __init__(self, api_key: str, model: str):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Google API key
            model: Model name to use
        """
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name=model)
        except Exception as e:
            raise Exception(f"Error initializing Gemini client: {e}")
    
    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        Invoke the Gemini model with the given messages.
        
        Args:
            messages: List of message dicts with role and content
            
        Returns:
            str: The content of the model's response
        """
        try:
            # Convert messages to Gemini format
            gemini_messages = []
            for msg in messages:
                if msg["role"] == "user":
                    gemini_messages.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "system":
                    # For system messages, prepend to the first user message
                    if gemini_messages and gemini_messages[0]["role"] == "user":
                        gemini_messages[0]["parts"][0] = f"{msg['content']}\n\n{gemini_messages[0]['parts'][0]}"
                    else:
                        # If no user message yet, add as user message
                        gemini_messages.append({"role": "user", "parts": [msg["content"]]})
                else:
                    gemini_messages.append({"role": "model", "parts": [msg["content"]]})
            
            response = self.model.generate_content(gemini_messages)
            return response.text
        except Exception as e:
            raise Exception(f"Error invoking Gemini model: {e}")
    
    def parse(self, messages: List[Dict[str, str]], response_model: Type[T]) -> T:
        """
        Parse the Gemini response directly into a Pydantic model.
        
        Args:
            messages: List of message dicts with role and content
            response_model: Pydantic model class to parse the response into
            
        Returns:
            T: Parsed response in the specified Pydantic model
        """
        try:
            # First, enhance messages to explicitly request JSON output
            enhanced_messages = messages.copy()
            if enhanced_messages and enhanced_messages[-1]["role"] == "user":
                enhanced_messages[-1]["content"] += "\n\nPlease return your response in valid JSON format following the schema provided."
            
            # Get response as plain text
            response_content = self.invoke(enhanced_messages)
            
            # Save raw response content
            save_raw_llm_response(response_content)
            
            # Clean response to extract JSON content
            # Sometimes model returns markdown code block or other formatting
            json_content = response_content
            if "```json" in json_content:
                # Extract JSON from markdown code block if present
                start_idx = json_content.find("```json") + 7
                end_idx = json_content.find("```", start_idx)
                if end_idx > start_idx:
                    json_content = json_content[start_idx:end_idx].strip()
            
            # Parse JSON response
            parsed_response = json.loads(json_content)
            
            # Convert to pydantic model
            try:
                # Try pydantic v2 approach first
                return response_model.model_validate(parsed_response)
            except AttributeError:
                # Fall back to pydantic v1 approach
                return response_model.parse_obj(parsed_response)
                
        except json.JSONDecodeError as e:
            # If JSON parsing fails, show part of the raw response for debugging
            preview = response_content[:200] + "..." if len(response_content) > 200 else response_content
            raise Exception(f"Error parsing Gemini response as JSON: {e}. Response preview: {preview}")
        except Exception as e:
            raise Exception(f"Error parsing Gemini response: {e}")


def get_openai_llm() -> OpenAIClient:
    """
    Configure and return an OpenAI client.
    
    Returns:
        OpenAIClient: Configured OpenAI client
    """
    api_key = os.getenv("LLM_API_KEY_ABSTRACT")
    model = os.getenv("LLM_MODEL_ABSTRACT", "gpt-4.1-nano")
    
    if not api_key:
        raise ValueError("LLM_API_KEY_ABSTRACT environment variable not set")
    
    return OpenAIClient(
        api_key=api_key,
        model=model
    )


def get_gemini_llm() -> GeminiClient:
    """
    Configure and return a Google Gemini client.
    
    Returns:
        GeminiClient: Configured Gemini client
    """
    api_key = os.getenv("LLM_API_KEY_ABSTRACT")
    model = os.getenv("LLM_MODEL_ABSTRACT", "gemini-2.0-flash-lite")
    
    if not api_key:
        raise ValueError("LLM_API_KEY_ABSTRACT environment variable not set")
    
    return GeminiClient(
        api_key=api_key,
        model=model
    )


def get_deepseek_llm() -> DeepSeekClient:
    """
    Configure and return a DeepSeek client.
    
    Returns:
        DeepSeekClient: Configured DeepSeek client
    """
    api_key = os.getenv("LLM_API_KEY_ABSTRACT")
    model = os.getenv("LLM_MODEL_ABSTRACT", "deepseek-chat")
    
    if not api_key:
        raise ValueError("LLM_API_KEY_ABSTRACT environment variable not set")
    
    return DeepSeekClient(
        api_key=api_key,
        model=model
    )

def setup_llm() -> LLMClient:
    """
    Set up and configure the LLM based on environment variables.
    
    Returns:
        LLMClient: Configured LLM client
        
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
        llm_type = os.getenv("LLM_API_TYPE_ABSTRACT", "OpenAI")
        llm_model = os.getenv("LLM_MODEL_ABSTRACT", "default")
        
        # Create filename with LLM type and model info
        filename = f"select_bibs_filtered_by_abstract_{llm_type}_{llm_model}_raw.txt"
        
        if not output_path:
            output_path = os.path.join(path_data, "OUTPUTS", filename)
        else:
            # If output_path is provided but doesn't have .txt extension, add LLM info and '_raw.txt' suffix
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
        llm_type = os.getenv("LLM_API_TYPE_ABSTRACT", "OpenAI")
        llm_model = os.getenv("LLM_MODEL_ABSTRACT", "default")
        
        # Create filename with LLM type and model info
        filename = f"select_bibs_filtered_by_abstract_{llm_type}_{llm_model}.json"
        
        if not output_path:
            output_path = os.path.join(path_data, "OUTPUTS", filename)
        elif not output_path.endswith('.json'):
            # If output_path doesn't have .json extension, add LLM info and .json suffix
            base_path = output_path.rsplit('.', 1)[0] if '.' in output_path else output_path
            output_path = f"{base_path}_{llm_type}_{llm_model}.json"
        
        if not os.path.isabs(output_path):
            output_path = os.path.join(path_data, "OUTPUTS", output_path)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Convert to dict before saving - use model_dump() instead of dict()
        try:
            # Try pydantic v2 approach first
            response_dict = response.model_dump()
        except AttributeError:
            # Fall back to pydantic v1 approach
            response_dict = response.dict()
        
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
    prompt = run_prepare_base_prompt(input_bibtex_path)
    
    # Setup LLM
    llm_client = setup_llm()
    
    try:
        print("Sending request to LLM... (This may take a few minutes)")
        # Send message to LLM with direct parsing
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # Use the parse method to get strongly typed response
        response_json = llm_client.parse(messages, LLMResponseModel)
        
        # Save response to file if output_path is specified
        if output_path:
            save_llm_response_to_file(response_json, output_path)
        
        return response_json
    
    except Exception as e:
        print(f"Error during LLM analysis: {e}")
        raise Exception(f"Error during LLM analysis: {e}")


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
