import os
import sys
import json
import re  # Adicionada importação para expressões regulares
from typing import Dict, List, Optional, Any, Union, Literal, TypeVar, Generic, Type, Tuple
from dotenv import load_dotenv
from pathlib import Path
import asyncio  # added for asynchronous support
import aiohttp  # added for async HTTP requests
# Update import statements for the Google Generative AI library
from google import genai
from google.genai import types as genai_types  # Import types for config
from openai import OpenAI, AsyncOpenAI  # Import AsyncOpenAI for async operations
from pydantic import BaseModel, Field, field_validator  # Atualizado para usar field_validator

# Local imports
from src.GenerativeAI.LLMUtils import run_prepare_base_prompt
from src.GenerativeAI.LLMUtils import run_prepare_base_prompt_list
from src.GenerativeAI.multi_llm_config import LLMClientConfig, load_llm_client_configs

# Load environment variables
load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("config/.env"))

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
    """
    articles: List[ArticleAnalysis] = Field(
        ..., 
        description="Array of analyzed articles"
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
    
    async def async_invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        Asynchronously invoke the LLM with the given messages.
        
        Args:
            messages: List of message dicts with role and content
            
        Returns:
            str: The content of the LLM's response
        """
        # Default implementation runs the synchronous version in a thread pool
        return await asyncio.to_thread(self.invoke, messages)
    
    async def async_parse(self, messages: List[Dict[str, str]], response_model: Type[T]) -> T:
        """
        Asynchronously parse the LLM response directly into a Pydantic model.
        
        Args:
            messages: List of message dicts with role and content
            response_model: Pydantic model class to parse the response into
            
        Returns:
            T: Parsed response in the specified Pydantic model
        """
        # Default implementation runs the synchronous version in a thread pool
        return await asyncio.to_thread(self.parse, messages, response_model)


class OpenAIClient(LLMClient):
    """Client for OpenAI API with support for large context windows."""
    
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model name to use
            base_url: Optional custom endpoint (ex.: endpoint OpenAI-compatível do Gemini)
        """
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)
            self.async_client = AsyncOpenAI(api_key=api_key)
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
    
    async def async_invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        Asynchronously invoke the OpenAI model with the given messages.
        
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
                
            response = await self.async_client.chat.completions.create(**request_params)
            return response.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"Error asynchronously invoking OpenAI model: {e}")
    
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
            
            # Save raw response content - we'll do this in the main processing function
            # to avoid I/O during async operations
            
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
    
    async def async_parse(self, messages: List[Dict[str, str]], response_model: Type[T]) -> T:
        """
        Asynchronously parse the OpenAI response directly into a Pydantic model.
        
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
            
            completion = await self.async_client.chat.completions.create(**request_params)
            response_content = completion.choices[0].message.content
            
            # Save raw response content - we'll do this in the main processing function
            # to avoid I/O during async operations
            
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
            raise Exception(f"Error asynchronously parsing OpenAI response: {e}")


class DeepSeekClient(LLMClient):
    """Client for DeepSeek API using OpenAI-compatible interface."""
    
    def __init__(self, api_key: str, model: str):
        """
        Initialize DeepSeek client.
        
        Args:
            api_key: DeepSeek API key
            model: Model name to use
        """
        base_url = os.getenv("LLM_API_BASE_URL", "https://api.deepseek.com/v1")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
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
    
    async def async_invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        Asynchronously invoke the DeepSeek model with the given messages.
        
        Args:
            messages: List of message dicts with role and content
            
        Returns:
            str: The content of the model's response
        """
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Error asynchronously invoking DeepSeek model: {e}")
    
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
    
    async def async_parse(self, messages: List[Dict[str, str]], response_model: Type[T]) -> T:
        """
        Asynchronously parse the DeepSeek response directly into a Pydantic model.
        
        Args:
            messages: List of message dicts with role and content
            response_model: Pydantic model class to parse the response into
            
        Returns:
            T: Parsed response in the specified Pydantic model
        """
        try:
            # Force JSON response format if supported
            completion = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"}
            )
            response_content = completion.choices[0].message.content
            
            # Parse JSON response
            parsed_response = json.loads(response_content)
            try:
                # Try pydantic v2 approach first
                return response_model.model_validate(parsed_response)
            except AttributeError:
                # Fall back to pydantic v1 approach
                return response_model.parse_obj(parsed_response)
            
        except Exception as e:
            raise Exception(f"Error asynchronously parsing DeepSeek response: {e}")


class GeminiClient(LLMClient):
    """Client for Google Gemini API."""
    
    def __init__(self, api_key: str, model: str):
        """
        Initialize Gemini client using genai.Client.
        
        Args:
            api_key: Google API key
            model: Model name to use
        """
        try:
            self.client = genai.Client(api_key=api_key)
            self.model_name = model
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
            # Chain of Thought:
            # Gemini expects contents as a string or a list of strings, not as a list of dicts.
            # We need to concatenate all user and system messages into a single string prompt.
            # Only user and system roles are relevant for the prompt.
            is_reasonear = os.getenv("LLM_IS_REASONER_ABSTRACT", "False").lower() == "true"
            prompt_parts = []
            for msg in messages:
                if msg["role"] in ("user", "system"):
                    prompt_parts.append(msg["content"])
            prompt = "\n\n".join(prompt_parts)

            # Check if the model is from the gemini-2.5-flash family to add thinking_config
            model_lower = self.model_name.lower()
            if model_lower.startswith("gemini-2.5-flash") and not is_reasonear:
                # For non-reasoning mode, create ThinkingConfig without thinking_budget parameter
                config = genai_types.GenerateContentConfig(
                    thinking_config=genai_types.ThinkingConfig()
                )
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
            else:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )
            return response.text
        except Exception as e:
            raise Exception(f"Error invoking Gemini model: {e}")
    
    async def async_invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        Asynchronously invoke the Gemini model with the given messages.
        
        Args:
            messages: List of message dicts with role and content
            
        Returns:
            str: The content of the model's response
        """
        # Use asyncio.to_thread to run the synchronous invoke method in a thread pool
        return await asyncio.to_thread(self.invoke, messages)

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
    
    # Print debug information
    print(f"Initializing Gemini with model: {model}")
    print(f"API key available: {'Yes (hidden)' if api_key else 'No'}")
    print(f"LLM type: {os.getenv('LLM_API_TYPE_ABSTRACT', 'Not set')}")
    
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


def _build_client_from_config(cfg: LLMClientConfig) -> LLMClient:
    """Instancia a classe de cliente local correspondente ao provedor do config.

    - openai   -> OpenAIClient (endpoint OpenAI; base_url opcional)
    - google   -> OpenAIClient via endpoint OpenAI-compatível do Gemini (usa base_url)
    - gemini   -> GeminiClient nativo (google.genai)
    - deepseek -> DeepSeekClient (OpenAI-compatível)
    """
    provider = cfg.provider.lower()
    if provider == "openai":
        return OpenAIClient(api_key=cfg.api_key, model=cfg.model_name, base_url=cfg.base_url)
    if provider == "google":
        base_url = cfg.base_url or "https://generativelanguage.googleapis.com/v1beta/openai/"
        return OpenAIClient(api_key=cfg.api_key, model=cfg.model_name, base_url=base_url)
    if provider == "gemini":
        return GeminiClient(api_key=cfg.api_key, model=cfg.model_name)
    if provider == "deepseek":
        return DeepSeekClient(api_key=cfg.api_key, model=cfg.model_name)
    raise ValueError(f"Provedor de LLM não suportado: {cfg.provider}")


def setup_llms(group: str = "ABSTRACT", selected: Optional[Union[str, List[str]]] = None
               ) -> List[Tuple[LLMClientConfig, LLMClient]]:
    """Carrega os LLMs configurados para o grupo (multi-LLM).

    Usa ``LLM_CLIENTS_<GROUP>`` quando definido; caso contrário cai no LLM único legado
    (``LLM_*_<GROUP>``), preservando o comportamento atual. Retorna pares (config, cliente).

    Args:
        group: grupo de configuração (ex.: "ABSTRACT").
        selected: se informado, roda apenas o(s) LLM(s) cujo id/name/model casar
            (ex.: "gpt-5.4-nano" para rodar só o GPT).
    """
    configs = load_llm_client_configs(group, selected)
    if not configs:
        msg = (
            "Nenhum LLM configurado. Defina LLM_CLIENTS_ABSTRACT (multi-LLM) "
            "ou as variáveis LLM_*_ABSTRACT (single-LLM) em config/.env."
        )
        if selected:
            msg = f"Nenhum LLM corresponde a '{selected}'. " + msg
        raise ValueError(msg)
    return [(cfg, _build_client_from_config(cfg)) for cfg in configs]


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


def save_raw_llm_responses(raw_responses: List[str], output_dir: Optional[str] = None,
                           llm_type: Optional[str] = None, llm_model: Optional[str] = None):
    """
    Save multiple raw LLM responses to text files.

    Args:
        raw_responses (List[str]): List of raw string content returned by the LLM
        output_dir (Optional[str]): Directory to save the raw responses, defaults to PATH_DATA/OUTPUTS
        llm_type (Optional[str]): Identificador do LLM (pasta de saída). Default: env LLM_API_TYPE_ABSTRACT.
        llm_model (Optional[str]): Modelo do LLM (nome do arquivo). Default: env LLM_MODEL_ABSTRACT.
    """
    try:
        path_data = os.getenv("PATH_DATA", ".data")
        llm_type = llm_type or os.getenv("LLM_API_TYPE_ABSTRACT", "OpenAI")
        llm_model = llm_model or os.getenv("LLM_MODEL_ABSTRACT", "default")

        if not output_dir:
            output_dir = os.path.join(path_data, "OUTPUTS", "raw_responses", llm_type)
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Save all raw responses in a single consolidated file
        consolidated_path = os.path.join(output_dir, f"all_responses_{llm_type}_{llm_model}_raw.txt")
        with open(consolidated_path, 'w', encoding='utf-8') as f:
            for i, response in enumerate(raw_responses):
                f.write(f"\n\n{'='*50}\n")
                f.write(f"RESPONSE {i+1}\n")
                f.write(f"{'='*50}\n\n")
                f.write(response)
        
        print(f"All raw LLM responses saved to {consolidated_path}")
        
        # Also save individual response files
        for i, response in enumerate(raw_responses):
            individual_path = os.path.join(output_dir, f"response_{i+1}_{llm_type}_{llm_model}_raw.txt")
            with open(individual_path, 'w', encoding='utf-8') as f:
                f.write(response)
    
    except Exception as e:
        print(f"Error saving raw LLM responses: {e}")


def save_llm_responses_to_file(responses: List[ArticleAnalysis], output_path: Optional[str] = None,
                               llm_type: Optional[str] = None, llm_model: Optional[str] = None):
    """
    Save multiple LLM responses to a JSON file.

    Args:
        responses (List[ArticleAnalysis]): List of validated article analyses
        output_path (Optional[str]): Path to save the responses
        llm_type (Optional[str]): Identificador do LLM. Default: env LLM_API_TYPE_ABSTRACT.
        llm_model (Optional[str]): Modelo do LLM. Default: env LLM_MODEL_ABSTRACT.
    """
    try:
        path_data = os.getenv("PATH_DATA", ".data")
        llm_type = llm_type or os.getenv("LLM_API_TYPE_ABSTRACT", "OpenAI")
        llm_model = llm_model or os.getenv("LLM_MODEL_ABSTRACT", "default")

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
        
        # Convert responses to list of dicts
        response_list = []
        for response in responses:
            try:
                # Try pydantic v2 approach first
                response_dict = response.model_dump()
            except AttributeError:
                # Fall back to pydantic v1 approach
                response_dict = response.dict()
            response_list.append(response_dict)
        
        # Create a container that matches the LLMResponseModel structure
        response_container = {
            "articles": response_list
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response_container, f, ensure_ascii=False, indent=2)
            
        print(f"LLM responses saved to {output_path}")
    
    except Exception as e:
        print(f"Error saving LLM responses: {e}")


def clean_and_parse_json(file_content: str) -> Dict[str, Any]:
    """
    Cleans and parses JSON content from raw responses.
    
    Args:
        file_content: Response file content
        
    Returns:
        Dictionary containing the parsed JSON data
    """
    # Check if content is within code blocks
    json_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    matches = re.findall(json_block_pattern, file_content)
    
    if matches:
        # Get the first JSON block
        content = matches[0]
    else:
        # No code blocks, use raw content
        content = file_content
    
    # Additional cleaning
    content = content.replace("```json", "").replace("```", "").strip()
    content = content.strip("[").strip("]")
    
    # Try to parse as JSON
    try:
        dict_json = json.loads(content)
        if len(dict_json) == 1 and "id" not in dict_json:
            new_dict = {}
            for key, value in dict_json.items():
                new_dict["id"] = key
                new_dict = new_dict | value
            return new_dict
        return dict_json

    except json.JSONDecodeError:
        try:
            # Handle possible trailing commas
            content = re.sub(r',\s*}', '}', content)
            content = re.sub(r',\s*]', ']', content)
            return json.loads(content)
        except json.JSONDecodeError:
            # Return raw content as fallback
            return {"raw_content": content}


def convert_to_json_llm(raw_text: str, llm_client: Optional[LLMClient] = None) -> Dict[str, Any]:
    """
    Uses a language model to convert raw text into valid JSON.
    
    Args:
        raw_text: Raw text to be converted to JSON
        llm_client: Optional LLM client instance to use
        
    Returns:
        Dictionary with the JSON content parsed from the LLM response
    """
    try:
        # Define a prompt for JSON conversion
        prompt = f"""Convert the string into valid json. json must be unique dictionary, not a list or array,
Return only json without any other text or explanation or comments or any other text.
Do not add any other text or explanation or comments or any other text.

string json to convert:
{raw_text}
"""
        
        # Use the provided LLM client or create a new one
        if llm_client is None:
            # Get environment variables
            model = os.getenv("LLM_MODEL_SIMPLE", "gpt-4.1-nano")
            api_key = os.getenv("LLM_API_KEY_SIMPLE") or os.getenv("LLM_API_KEY_ABSTRACT")
            
            if not api_key:
                print("Error: API key for LLM not found")
                return {"error": "API key not found"}
            
            # Initialize a client
            llm_client = OpenAIClient(api_key=api_key, model=model)
        
        # Prepare messages
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # Get the response
        result_text = llm_client.invoke(messages)
        
        # Parse JSON from response
        return clean_and_parse_json(result_text)
            
    except Exception as e:
        print(f"Error using LLM for JSON conversion: {e}")
        return {"error": str(e)}

# Nova classe para armazenar artigos com sua sequência original
class SequencedArticle:
    """
    Stores article data with its original sequence number.
    """
    def __init__(self, sequence: int, prompt: str, id: Optional[str] = None):
        self.sequence = sequence
        self.prompt = prompt
        self.id = id
        self.article_analysis = None
        self.raw_response = None
        self.error = None
    
    def set_result(self, article_analysis: Optional[ArticleAnalysis], raw_response: str):
        """Set the result of processing this article."""
        self.article_analysis = article_analysis
        self.raw_response = raw_response
    
    def set_error(self, error: Exception):
        """Set error information if processing failed."""
        self.error = str(error)

# Refactored asynchronous function to process a single article
async def process_article_async(article: SequencedArticle, llm_client: LLMClient) -> None:
    """
    Process single article prompt asynchronously and store result in the article object.
    """
    try:
        print(f"Processing article {article.sequence+1}...")
        messages = [{"role": "user", "content": article.prompt}]
        
        # Asynchronously invoke LLM
        raw_response: str = await llm_client.async_invoke(messages)
        article.raw_response = raw_response
        
        # Try to parse as JSON
        try:
            # Clean response to extract JSON content
            json_content = raw_response
            if "```json" in json_content:
                # Extract JSON from markdown code block if present
                start_idx = json_content.find("```json") + 7
                end_idx = json_content.find("```", start_idx)
                if end_idx > start_idx:
                    json_content = json_content[start_idx:end_idx].strip()
            
            # Parse JSON response - primeira tentativa
            try:
                parsed_response = json.loads(json_content)
            except json.JSONDecodeError:
                # Primeira tentativa falhou, usar clean_and_parse_json
                print(f"⚠ JSON decode failed for article {article.sequence+1}, trying advanced cleaning...")
                parsed_response = clean_and_parse_json(raw_response)
                
                # Se ainda contiver raw_content, tentar convert_to_json_llm
                if "raw_content" in parsed_response:
                    print(f"⚠ Attempting LLM conversion for article {article.sequence+1}")
                    parsed_response = await asyncio.to_thread(convert_to_json_llm, parsed_response["raw_content"], llm_client)
                
            if "raw_content" in parsed_response:
                parsed_response = parsed_response["raw_content"]
            
            # Check if response has the {'articles': [...]} structure and extract the article
            if isinstance(parsed_response, dict) and 'articles' in parsed_response and isinstance(parsed_response['articles'], list) and parsed_response['articles']:
                # Extract the first article from the 'articles' array
                parsed_response = parsed_response['articles'][0]
            
            # Convert to ArticleAnalysis
            try:
                # Try pydantic v2 approach first
                article_analysis = ArticleAnalysis.model_validate(parsed_response)
            except AttributeError:
                # Fall back to pydantic v1 approach
                article_analysis = ArticleAnalysis.parse_obj(parsed_response)
            
            article.article_analysis = article_analysis
            print(f"✓ Article {article.sequence+1} successfully processed")
        
        except json.JSONDecodeError as e:
            print(f"⚠ Error parsing JSON for article {article.sequence+1}: {e}")
            print(f"Raw response preview: {raw_response[:200]}...")
            article.set_error(e)
        except Exception as e:
            print(f"⚠ Error converting to ArticleAnalysis for article {article.sequence+1}: {e}")
            article.set_error(e)
    
    except Exception as e:
        print(f"⚠ Error getting response for article {article.sequence+1}: {e}")
        article.set_error(e)


def check_raw_response_exists(idx: int, llm_type: str, llm_model: str, output_dir: Optional[str] = None) -> bool:
    """
    Checks if raw response file already exists for a specific article index.
    
    Args:
        idx (int): Index of the article (0-based)
        llm_type (str): Type of LLM used (e.g., "OpenAI", "Gemini")
        llm_model (str): Model name used
        output_dir (Optional[str]): Directory where raw responses are saved
        
    Returns:
        bool: True if file exists, False otherwise
    """
    try:
        path_data = os.getenv("PATH_DATA", ".data")
        
        if not output_dir:
            output_dir = os.path.join(path_data, "OUTPUTS", "raw_responses", llm_type)
        
        # Filename format matches the one used in save_raw_llm_responses function
        filepath = os.path.join(output_dir, f"response_{idx+1}_{llm_type}_{llm_model}_raw.txt")
        
        return os.path.exists(filepath)
        
    except Exception:
        return False


# Function to get rate limit from environment variable
def get_rate_limit() -> float:
    """
    Get the rate limit (requests per second) from environment variable.
    
    Returns:
        float: Maximum number of requests allowed per second
    """
    default_rate_limit = 10.0  # Default to 10 requests per second if not specified
    rate_limit_str = os.getenv("LLM_SECOND_RATE_LIMITE_ABSTRACT")
    
    if not rate_limit_str:
        print(f"LLM_SECOND_RATE_LIMITE_ABSTRACT not set. Using default rate limit of {default_rate_limit} requests/second")
        return default_rate_limit
    
    try:
        rate_limit = float(rate_limit_str)
        if rate_limit <= 0:
            print(f"Invalid rate limit value: {rate_limit}. Using default of {default_rate_limit} requests/second")
            return default_rate_limit
        print(f"Using rate limit of {rate_limit} requests/second")
        return rate_limit
    except ValueError:
        print(f"Could not parse rate limit value: {rate_limit_str}. Using default of {default_rate_limit} requests/second")
        return default_rate_limit

# Modified version of process_article_async with rate limiting
async def process_article_async_with_rate_limit(article: SequencedArticle,
                                                llm_client: LLMClient,
                                                semaphore: asyncio.Semaphore,
                                                min_delay: float,
                                                llm_type: Optional[str] = None,
                                                llm_model: Optional[str] = None,
                                                overwrite: Optional[bool] = None) -> None:
    """
    Process single article prompt asynchronously with rate limiting.
    Checks if raw response file already exists before calling LLM.

    Args:
        article: SequencedArticle object containing prompt and sequence
        llm_client: LLM client instance
        semaphore: Semaphore to control concurrent requests
        min_delay: Minimum delay between requests in seconds
        llm_type: Identificador do LLM (pasta de saída). Default: env LLM_API_TYPE_ABSTRACT.
        llm_model: Modelo do LLM (nome do arquivo). Default: env LLM_MODEL_ABSTRACT.
        overwrite: Sobrescreve arquivos existentes. Default: env LLM_OVERWRITE_ABSTRACT.
    """
    # Verificar se devemos sobrescrever arquivos existentes
    if overwrite is None:
        overwrite = os.getenv("LLM_OVERWRITE_ABSTRACT", "False").lower() == "true"
    llm_type = llm_type or os.getenv("LLM_API_TYPE_ABSTRACT", "OpenAI")
    llm_model = llm_model or os.getenv("LLM_MODEL_ABSTRACT", "default")
    path_data = os.getenv("PATH_DATA", ".data")
    
    # Preparar diretório para verificação de arquivos
    output_dir = os.path.join(path_data, "OUTPUTS", "raw_responses", llm_type)
    os.makedirs(output_dir, exist_ok=True)
    
    # Verificar se o arquivo RAW já existe
    if not overwrite and check_raw_response_exists(article.sequence, llm_type, llm_model, output_dir):
        print(f"⏩ Skipping LLM call for article {article.sequence+1} - raw response file already exists.")
        print(f"   Set LLM_OVERWRITE_ABSTRACT=True to override existing files.")
        
        # Tentar ler e processar o arquivo existente
        try:
            individual_path = os.path.join(output_dir, f"response_{article.sequence+1}_{llm_type}_{llm_model}_raw.txt")
            with open(individual_path, 'r', encoding='utf-8') as f:
                raw_response = f.read()
                
            article.raw_response = raw_response
            
            # Tentar processar o conteúdo existente
            try:
                # Clean response to extract JSON content
                json_content = raw_response
                if "```json" in json_content:
                    # Extract JSON from markdown code block if present
                    start_idx = json_content.find("```json") + 7
                    end_idx = json_content.find("```", start_idx)
                    if end_idx > start_idx:
                        json_content = json_content[start_idx:end_idx].strip()
                
                # Parse JSON response
                try:
                    parsed_response = json.loads(json_content)
                except json.JSONDecodeError:
                    # Primeira tentativa falhou, usar clean_and_parse_json
                    print(f"⚠ JSON decode failed for article {article.sequence+1}, trying advanced cleaning...")
                    parsed_response = clean_and_parse_json(raw_response)
                    
                    # Se ainda contiver raw_content, tentar convert_to_json_llm
                    if "raw_content" in parsed_response:
                        print(f"⚠ Attempting LLM conversion for article {article.sequence+1}")
                        parsed_response = await asyncio.to_thread(convert_to_json_llm, parsed_response["raw_content"], llm_client)
                
                if "raw_content" in parsed_response:
                    parsed_response = parsed_response["raw_content"]
                
                # Check if response has the {'articles': [...]} structure and extract the article
                if isinstance(parsed_response, dict) and 'articles' in parsed_response and isinstance(parsed_response['articles'], list) and parsed_response['articles']:
                    # Extract the first article from the 'articles' array
                    parsed_response = parsed_response['articles'][0]
                
                # Convert to ArticleAnalysis
                try:
                    # Try pydantic v2 approach first
                    article_analysis = ArticleAnalysis.model_validate(parsed_response)
                except AttributeError:
                    # Fall back to pydantic v1 approach
                    article_analysis = ArticleAnalysis.parse_obj(parsed_response)
                
                article.article_analysis = article_analysis
                print(f"✓ Article {article.sequence+1} successfully loaded from existing file")
                
            except Exception as e:
                print(f"⚠ Error processing existing file for article {article.sequence+1}: {e}")
                
        except Exception as e:
            print(f"⚠ Error reading existing file for article {article.sequence+1}: {e}")
        
        return
    
    # Se o arquivo não existe ou se devemos sobrescrever, processa normalmente
    async with semaphore:
        # Record start time for rate limiting
        start_time = asyncio.get_event_loop().time()
        
        # Process the article
        await process_article_async(article, llm_client)
        
        # Calculate how long processing took
        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        # If processing was too quick, add a delay to respect rate limit
        if elapsed_time < min_delay:
            delay_time = min_delay - elapsed_time
            await asyncio.sleep(delay_time)


# Refactored asynchronous function to process all articles with rate limiting (multi-LLM)
async def _process_articles_for_client(cfg: LLMClientConfig, llm_client: LLMClient,
                                       prompt_list: List[str],
                                       output_path: Optional[str] = None) -> List[ArticleAnalysis]:
    """
    Processa todos os artigos com UM cliente de LLM (rate-limit próprio do cliente).
    Salva respostas brutas/processadas na pasta específica desse LLM.
    """
    # Rate limit: por-cliente (cfg.rate_limit) com fallback para o do grupo (get_rate_limit)
    rate_limit = cfg.rate_limit or get_rate_limit()
    if rate_limit <= 0:
        rate_limit = get_rate_limit()
    min_delay = 1.0 / rate_limit
    max_concurrent = max(1, min(10, int(rate_limit * 1.5)))
    semaphore = asyncio.Semaphore(max_concurrent)

    print(f"[{cfg.name}/{cfg.model_name}] rate={rate_limit} req/s, "
          f"concorrência={max_concurrent}, delay_min={min_delay:.4f}s")

    # Lista de artigos sequenciados (fresca para este cliente)
    sequenced_articles = [SequencedArticle(idx, prompt) for idx, prompt in enumerate(prompt_list)]

    tasks = [
        process_article_async_with_rate_limit(
            article, llm_client, semaphore, min_delay,
            llm_type=cfg.name, llm_model=cfg.model_name, overwrite=cfg.overwrite,
        )
        for article in sequenced_articles
    ]
    await asyncio.gather(*tasks)

    raw_responses = [a.raw_response for a in sequenced_articles if a.raw_response]
    article_analyses = [a.article_analysis for a in sequenced_articles if a.article_analysis is not None]

    if raw_responses:
        save_raw_llm_responses(raw_responses, llm_type=cfg.name, llm_model=cfg.model_name)
    if output_path and article_analyses:
        save_llm_responses_to_file(article_analyses, output_path, llm_type=cfg.name, llm_model=cfg.model_name)

    print(f"[{cfg.name}/{cfg.model_name}] {len(article_analyses)}/{len(prompt_list)} artigos processados.")
    return article_analyses


async def analyze_abstracts_with_llm_one_on_one(input_bibtex_path: Optional[str] = None,
                                                output_path: Optional[str] = None,
                                                group: str = "ABSTRACT",
                                                selected: Optional[Union[str, List[str]]] = None
                                                ) -> List[ArticleAnalysis]:
    """
    Analisa abstracts com UM OU MAIS LLMs, um artigo por vez, com rate limiting.

    Cada LLM configurado (via LLM_CLIENTS_<GROUP>, ou o LLM único legado) processa TODOS os
    artigos de forma independente e salva seus resultados em pasta própria. Os LLMs rodam
    concorrentemente entre si (cada um com seu próprio semáforo/rate-limit).

    Args:
        input_bibtex_path: Caminho do arquivo BibTeX a analisar
        output_path: Caminho para salvar o JSON de respostas (opcional)
        group: Grupo de configuração de LLM (default "ABSTRACT")

    Returns:
        List[ArticleAnalysis]: análises combinadas de todos os LLMs
    """
    # Lista de prompts (compartilhada entre os LLMs)
    prompt_list = run_prepare_base_prompt_list(input_bibtex_path)

    # Carregar os LLMs configurados (todos, ou apenas o selecionado)
    clients = setup_llms(group, selected)
    print(f"Multi-LLM: {len(clients)} cliente(s): {', '.join(cfg.name for cfg, _ in clients)}")

    try:
        print(f"Processing {len(prompt_list)} articles for {len(clients)} LLM(s) asynchronously...")

        results = await asyncio.gather(
            *[_process_articles_for_client(cfg, client, prompt_list, output_path)
              for cfg, client in clients]
        )

        # Combina as análises de todos os LLMs (resultados independentes por cliente)
        combined = [analysis for sublist in results for analysis in sublist]
        print(f"Total combinado: {len(combined)} análises de {len(clients)} LLM(s).")
        return combined

    except Exception as e:
        print(f"Error during LLM analysis: {e}")
        return []

# Função principal refatorada para usar assincronidade
async def run_select_bibs_filtered_by_abstract(input_bibtex_path: Optional[str] = None,
                                                output_path: Optional[str] = None,
                                                selected: Optional[Union[str, List[str]]] = None):
    """
    Main function to run the LLM analysis pipeline.

    Args:
        input_bibtex_path: Path to the BibTeX file to analyze
        output_path: Path to save the output files
        selected: roda apenas o(s) LLM(s) cujo id/name/model casar (ex.: "gpt-5.4-nano")
    """
    try:
        print(f"Analyzing abstracts from {'default bibtex' if input_bibtex_path is None else input_bibtex_path}")
        responses = await analyze_abstracts_with_llm_one_on_one(input_bibtex_path, output_path, selected=selected)
        if responses:
            response_model = LLMResponseModel(articles=responses)
            return response_model
        else:
            print("No valid responses were obtained.")
            return None
    except Exception as e:
        print(f"Error in main function: {e}")
        sys.exit(1)