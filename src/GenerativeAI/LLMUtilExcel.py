import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
import yaml
import pandas as pd
from src.GenerativeAI.LLMSelectPapersByAbstractOneOnOne import OpenAIClient

# Carregar variáveis de ambiente do arquivo .env
load_dotenv(os.path.abspath(".conf"))
PROMPT = f"""Convert the string into valid json. json must be unique dictionary, not a list or array,
Return only json without any other text or explanation or comments or any other text.
Do not add any other text or explanation or comments or any other text.

string json to convert:
{{raw_text}}
"""


def read_json_schema(schema_path: Optional[str] = None) -> str:
    """
    Reads the JSON schema for formatting LLM responses.
    
    Args:
        schema_path: Path to the JSON schema file (optional)
        
    Returns:
        Dictionary with the JSON schema content
    """
    # Define default path if not provided
    if not schema_path:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        schema_path = os.path.join(base_dir, "src", "GenerativeAI", 
                                    "json_schema_abstract_LLM_response_one_on_one.json")
    
    try:
        with open(schema_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"Error reading JSON schema: {e}")
        # Return a basic schema in case of error
        return """{
            "type": "object",
            "required": ["id", "research_questions", "is_relevant"],
            "properties": {
                "id": {"type": "string"},
                "research_questions": {"type": "object"},
                "is_relevant": {"type": "object"}
            }
        }"""


def clean_and_parse_json(file_content: str) -> Dict[str, Any]:
    """
    Limpa e analisa o conteúdo JSON das respostas brutas.
    
    Args:
        file_content: Conteúdo do arquivo de resposta
        
    Returns:
        Dicionário contendo os dados JSON analisados
    """
    # Verificar se o conteúdo está dentro de blocos de código
    json_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    matches = re.findall(json_block_pattern, file_content)
    
    if matches:
        # Pegar o primeiro bloco JSON
        content = matches[0]
    else:
        # Sem blocos de código, usar o conteúdo bruto
        content = file_content
    
    # Limpeza adicional
    content = content.replace("```json", "").replace("```", "").replace("```", "").strip()

    content = content.strip("[").strip("]")
    
    # Tentar analisar como JSON
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
            # Lidar com possíveis vírgulas no final
            content = re.sub(r',\s*}', '}', content)
            content = re.sub(r',\s*]', ']', content)
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Falha ao analisar JSON: {e}")
            # Retornar conteúdo bruto como fallback
            return {"raw_content": content}


def convert_to_json_llm(raw_text: str) -> Dict[str, Any]:
    """
    Uses OpenAI's language model to convert raw text into valid JSON.
    Uses the OpenAIClient class for standardized LLM interaction.
    
    Args:
        raw_text: Raw text to be converted to JSON
        
    Returns:
        Dictionary with the JSON content parsed from the LLM response
    """
    try:
        # Get environment variables
        model = os.getenv("LLM_MODEL_SIMPLE", "gpt-4.1-nano")
        api_key = os.getenv("LLM_API_KEY_SIMPLE")
        
        if not api_key:
            print("Error: API key LLM_API_KEY_SIMPLE not found")
            return {"error": "API key not found"}
        
        # Initialize the OpenAIClient
        client = OpenAIClient(api_key=api_key, model=model)
        
        # Create prompt - sending full text without truncation
        prompt = PROMPT
        prompt = prompt.format(raw_text=raw_text).strip()

        # Prepare messages for the OpenAIClient
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # Use the client's invoke method to get the response
        result_text = client.invoke(messages)
        
        # Parse JSON from response
        return clean_and_parse_json(result_text)
            
    except Exception as e:
        print(f"Error using LLM for JSON conversion: {e}")
        return {"error": str(e)}


def save_parsed_json(parsed_content: Dict[str, Any], provider: str, model: str, file: str, base_dir: Optional[str] = None) -> str:
    """
    Saves the parsed JSON content to a file organized by provider and model.
    
    Args:
        parsed_content: The parsed JSON content to save
        provider: Provider name (e.g., 'OpenAI', 'Gemini')
        model: Model name (e.g., 'gpt-4', 'gemini-pro')
        file: Original file name
        base_dir: Base directory for output (optional)
        
    Returns:
        str: Path to the saved JSON file
    """
    # Determine base directory
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    
    # Create the output directory structure
    output_base = os.path.join(base_dir, ".data", "OUTPUTS", "processed_responses", "final_json")
    if not os.path.exists(output_base):
        os.makedirs(output_base)
    provider_dir = os.path.join(output_base, provider)
    model_dir = os.path.join(provider_dir, model)
    
    # Create directories if they don't exist
    os.makedirs(model_dir, exist_ok=True)
    
    # Create output filename - replace _raw.txt with .json
    output_filename = file.replace("_raw.txt", ".json")
    output_path = os.path.join(model_dir, output_filename)
    
    # Save the JSON content
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(parsed_content, f, ensure_ascii=False, indent=2)
        return output_path
    except Exception as e:
        print(f"Error saving JSON file {output_path}: {e}")
        return ""


def save_unconverted_files_log(unconverted_files: List[str], base_dir: Optional[str] = None) -> str:
    """
    Saves a log file with the list of files that couldn't be converted to proper JSON.
    
    Args:
        unconverted_files: List of file paths that couldn't be converted
        base_dir: Base directory for output (optional)
        
    Returns:
        str: Path to the saved log file
    """
    if not unconverted_files:
        return ""
        
    # Determine base directory
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    
    # Create the output directory structure
    output_dir = os.path.join(base_dir, ".data", "OUTPUTS", "processed_responses", "logs")
    os.makedirs(output_dir, exist_ok=True)
    
    # Create output filename with timestamp
    timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
    log_path = os.path.join(output_dir, f"unconverted_files_{timestamp}.log")
    
    # Save the log content
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"Unconverted files log - {pd.Timestamp.now()}\n")
            f.write("="*80 + "\n\n")
            f.write(f"Total unconverted files: {len(unconverted_files)}\n\n")
            for i, file_path in enumerate(unconverted_files, 1):
                f.write(f"{i}. {file_path}\n")
        print(f"Unconverted files log saved to: {log_path}")
        return log_path
    except Exception as e:
        print(f"Error saving unconverted files log: {e}")
        return ""


def read_raw_responses(base_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Lê todos os arquivos de resposta do diretório raw_responses e seus subdiretórios.
    
    Args:
        base_path: Caminho base dos arquivos de resposta
        
    Returns:
        Dicionário com os dados extraídos organizados por provedor
    """
    # Carregar perguntas de pesquisa para uso na extração de texto bruto
    yaml_path = os.path.join(os.path.dirname(base_path), "..", "..", "Config", "research_questions.yaml")
    research_questions = {}
    if os.path.exists(yaml_path):
        try:
            research_questions = read_research_questions(yaml_path)
        except Exception as e:
            print(f"Erro ao ler perguntas de pesquisa: {e}")
    
    results = {}
    unconverted_files = []  # Track files that couldn't be converted
    
    # Percorrer todos os subdiretórios
    for root, dirs, files in os.walk(base_path):
        provider = os.path.basename(root)
        
        # Pular o diretório base
        if provider == os.path.basename(base_path):
            continue
            
        if provider not in results:
            results[provider] = []
        
        # Encontrar todos os arquivos de resposta
        for file in files:
            if file.startswith("response_") and file.endswith("_raw.txt"):
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Extrair informações do nome do arquivo
                    pattern = r'response_(\d+)_([^_]+)_([^_]+)_raw\.txt'
                    match = re.search(pattern, file)
                    
                    if match:
                        response_id, provider_name, model = match.groups()
                        # Formatar response_id como string de 5 dígitos, preenchendo com zeros à esquerda
                        response_id = str(response_id).zfill(5)
                    else:
                        parts = file.replace("_raw.txt", "").split("_")
                        if len(parts) >= 4:
                            response_id = parts[1]
                            # Formatar response_id como string de 5 dígitos, preenchendo com zeros à esquerda
                            response_id = str(response_id).zfill(5)
                            provider_name = parts[2]
                            model = "_".join(parts[3:])
                        else:
                            response_id, provider_name, model = "", provider, "unknown"
                    
                    response_id = "'" + str(response_id).zfill(5)
                    
                    # Tentar analisar o conteúdo JSON
                    parsed_content = clean_and_parse_json(content)
                    
                    # Verificar se o conteúdo analisado possui informações úteis
                    if "raw_content" in parsed_content:
                        # Tentar extrair respostas do texto bruto usando o LLM
                        parsed_content = convert_to_json_llm(parsed_content['raw_content'])
                        
                        # Check if conversion was successful
                        if "raw_content" in parsed_content:
                            # Conversion failed, add to list of unconverted files
                            unconverted_files.append(file_path)
                            print(f"Warning: Failed to convert {file_path} using LLM")
                    
                    if parsed_content:
                        # Adicionar metadados
                        if isinstance(parsed_content, list):
                            for item in parsed_content:
                                if isinstance(item, dict):  # Check if item is a dictionary
                                    item['_response_id'] = response_id
                                    item['_provider'] = provider_name
                                    item['_model'] = model
                                    item['_file'] = file
                                    # Save the parsed JSON to a file
                                    json_path = save_parsed_json(item, provider_name, model, file)
                                    if json_path:
                                        item['_json_path'] = json_path
                                    results[provider].append(item)
                        else:
                            parsed_content['_response_id'] = response_id
                            parsed_content['_provider'] = provider_name
                            parsed_content['_model'] = model
                            parsed_content['_file'] = file
                            # Save the parsed JSON to a file
                            json_path = save_parsed_json(parsed_content, provider_name, model, file)
                            if json_path:
                                parsed_content['_json_path'] = json_path
                            results[provider].append(parsed_content)
                except Exception as e:
                    print(f"Erro ao processar arquivo {file_path}: {e}")
                    unconverted_files.append(file_path)
    
    # Save log of unconverted files
    if unconverted_files:
        save_unconverted_files_log(unconverted_files)
    
    return results


def read_research_questions(yaml_path: str) -> Dict[str, str]:
    """
    Lê as perguntas de pesquisa do arquivo YAML.
    
    Args:
        yaml_path: Caminho para o arquivo YAML
        
    Returns:
        Dicionário com perguntas de pesquisa
    """
    with open(yaml_path, 'r', encoding='utf-8') as f:
        questions = yaml.safe_load(f)
    
    # Achatar as perguntas
    flat_questions = {
        'principal_research_question': questions['principal_research_question']
    }
    
    if 'additional_research_questions' in questions:
        for key, value in questions['additional_research_questions'].items():
            flat_questions[key] = value
    
    if 'supporting_questions' in questions:
        for key, value in questions['supporting_questions'].items():
            flat_questions[key] = value
    
    if 'rejection_criteria' in questions:
        for key, value in questions['rejection_criteria'].items():
            flat_questions[key] = value
    
    if 'accepted_criteria' in questions:
        for key, value in questions['accepted_criteria'].items():
            flat_questions[key] = value
            
    return flat_questions


def read_article_info(json_path: str) -> Dict[str, Dict[str, str]]:
    """
    Lê informações de artigos do arquivo JSON.
    
    Args:
        json_path: Caminho para o arquivo JSON
        
    Returns:
        Dicionário com informações de artigos indexados por ID
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    # Criar um mapeamento de ID para informações do artigo
    article_mapping = {}
    for article in articles:
        article_id = article.get('id')
        if article_id:
            article_mapping[str(article_id)] = {
                'title': article.get('title', ''),
                'abstract': article.get('abstract', ''),
                'keywords': article.get('keywords', ''),
                'doi': article.get('doi', '')  # Adicionando o campo DOI
            }
    
    return article_mapping


def flatten_json_response(response: Dict[str, Any], articles: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """
    Transforma estruturas JSON aninhadas em um dicionário plano.
    
    Args:
        response: Resposta JSON original
        articles: Informações dos artigos
        
    Returns:
        Dicionário achatado
    """
    flat_response = {}
    
    # Adicionar campos de metadados
    for meta_key in ['_response_id', '_provider', '_model', '_file']:
        if meta_key in response:
            flat_response[meta_key] = response[meta_key]
    
    # Adicionar campo ID
    if 'id' in response:
        flat_response['id'] = response['id']
        
        # Adicionar informações do artigo
        article_id = str(response['id'])
        if article_id in articles:
            flat_response['article_title'] = articles[article_id].get('title', '')
            flat_response['article_abstract'] = articles[article_id].get('abstract', '')
            flat_response['article_keywords'] = articles[article_id].get('keywords', '')
            flat_response['doi'] = articles[article_id].get('doi', '')  # Adicionando o DOI
    
    # Processar perguntas de pesquisa
    if 'research_questions' in response:
        for q_key, q_value in response['research_questions'].items():
            if isinstance(q_value, dict):
                for sub_key, sub_value in q_value.items():
                    flat_response[f'rq_{q_key}_{sub_key}'] = sub_value
            else:
                flat_response[f'rq_{q_key}'] = q_value
    
    # Processar perguntas de suporte
    if 'supporting_questions' in response:
        for q_key, q_value in response['supporting_questions'].items():
            if isinstance(q_value, dict):
                for sub_key, sub_value in q_value.items():
                    flat_response[f'sq_{q_key}_{sub_key}'] = sub_value
            else:
                flat_response[f'sq_{q_key}'] = q_value
    
    # Processar critérios de aceitação
    if 'accepted_criteria' in response:
        for c_key, c_value in response['accepted_criteria'].items():
            if isinstance(c_value, dict):
                for sub_key, sub_value in c_value.items():
                    flat_response[f'ac_{c_key}_{sub_key}'] = sub_value
            else:
                flat_response[f'ac_{c_key}'] = c_value
    
    # Processar critérios de rejeição
    if 'rejection_criteria' in response:
        for c_key, c_value in response['rejection_criteria'].items():
            if isinstance(c_value, dict):
                for sub_key, sub_value in c_value.items():
                    flat_response[f'rc_{c_key}_{sub_key}'] = sub_value
            else:
                flat_response[f'rc_{c_key}'] = c_value
    
    # Processar relevância
    if 'is_relevant' in response:
        if isinstance(response['is_relevant'], dict):
            for sub_key, sub_value in response['is_relevant'].items():
                flat_response[f'is_relevant_{sub_key}'] = sub_value
        else:
            flat_response['is_relevant'] = response['is_relevant']
    
    # Processar perguntas adicionais
    if 'additional_questions_by_article' in response:
        for aq_key, aq_value in response['additional_questions_by_article'].items():
            flat_response[f'aq_{aq_key}'] = aq_value
    
    # Processar o resto das chaves
    for key, value in response.items():
        if key not in ['_response_id', '_provider', '_model', '_file', 'id', 
                        'is_relevant', 'research_questions', 'supporting_questions', 
                        'accepted_criteria', 'rejection_criteria',
                        'additional_questions_by_article']:
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    flat_response[f'{key}_{sub_key}'] = sub_value
            elif not isinstance(value, list):  # Evitar arrays complexos
                flat_response[key] = value
    
    return flat_response


def create_excel_from_data(responses_data: Dict[str, List[Dict]], 
                            questions: Dict[str, str], 
                            articles: Dict[str, Dict[str, str]], 
                            output_path: str,
                            simple_output_path: str) -> None:
    """
    Cria arquivos Excel com múltiplas abas a partir dos dados coletados.
    
    Args:
        responses_data: Dados de respostas organizados por provedor
        questions: Perguntas de pesquisa
        articles: Informações dos artigos
        output_path: Caminho para salvar o arquivo Excel completo
        simple_output_path: Caminho para salvar o arquivo Excel simplificado
    """
    # Criar objetos writer para os dois arquivos
    writer_full = pd.ExcelWriter(output_path, engine='openpyxl')
    writer_simple = pd.ExcelWriter(simple_output_path, engine='openpyxl')
    
    # Criar uma aba para cada provedor
    for provider, responses in responses_data.items():
        if not responses:
            continue
        
        # Nomes de abas Excel têm limite de 31 caracteres
        sheet_name = provider[:31]
        
        # Normalizar os dados para lidar com estruturas aninhadas
        flattened_responses = []
        for response in responses:
            flat_response = flatten_json_response(response, articles)
            flattened_responses.append(flat_response)
            
        # Converter para DataFrame
        if flattened_responses:
            df = pd.DataFrame(flattened_responses)
            
            # Ordenar por _response_id
            if '_response_id' in df.columns:
                df = df.sort_values(by='_response_id')
            
            # Excel completo (todos os campos)
            # Reordenar colunas para colocar metadados primeiro
            meta_cols = [col for col in df.columns if col.startswith('_')]
            id_cols = ['id', 'doi', 'article_title', 'article_abstract', 'article_keywords']
            other_cols = [col for col in df.columns if col not in meta_cols and col not in id_cols]
            cols = meta_cols + id_cols + other_cols
            df_full = df[[col for col in cols if col in df.columns]]
            
            # Salvar na aba do Excel completo
            df_full.to_excel(writer_full, sheet_name=sheet_name, index=False)
            
            # Excel simplificado (campos específicos)
            required_cols = ['_response_id', '_provider', '_model', '_file', 'id', 'doi']
            
            # Filtrar colunas de perguntas e respostas, excluindo as iniciadas com aq_adq_a
            # e excluindo também as que terminam com "comment"
            question_cols = [col for col in df.columns 
                            if (col.startswith('rq_') or 
                                col.startswith('sq_') or 
                                col.startswith('ac_') or 
                                col.startswith('rc_') or
                                col.startswith('is_relevant')) and (  # Modificado para incluir todos os campos is_relevant
                                not col.startswith('aq_adq_a') and
                                not col.endswith('comment'))]
            
            simple_cols = required_cols + question_cols
            df_simple = df[[col for col in simple_cols if col in df.columns]]
            
            # Salvar na aba do Excel simplificado
            df_simple.to_excel(writer_simple, sheet_name=sheet_name, index=False)
    
    # Criar uma aba para perguntas de pesquisa em ambos os arquivos
    questions_df = pd.DataFrame({
        'question_id': list(questions.keys()),
        'question_text': list(questions.values())
    })
    questions_df.to_excel(writer_full, sheet_name='Research Questions', index=False)
    questions_df.to_excel(writer_simple, sheet_name='Research Questions', index=False)
    
    # Salvar os arquivos Excel
    writer_full.close()
    writer_simple.close()


def process_responses_to_excel(base_dir: Optional[str] = None) -> Tuple[str, str]:
    """
    Função principal para processar respostas e criar os arquivos Excel.
    
    Args:
        base_dir: Diretório base do projeto (opcional)
        
    Returns:
        Tupla com os caminhos para os arquivos Excel gerados (completo, simplificado)
    """
    # Definir caminhos
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    
    base_path = os.path.join(base_dir, ".data", "OUTPUTS", "raw_responses")
    yaml_path = os.path.join(base_dir, "Config", "research_questions.yaml")
    json_path = os.path.join(base_dir, ".data", "OUTPUTS", "select_bibs.json")
    output_dir = os.path.join(base_dir, ".data", "OUTPUTS", "processed_responses")
    output_path = os.path.join(output_dir, "combined_responses_full.xlsx")
    simple_output_path = os.path.join(output_dir, "combined_responses_simple.xlsx")
    # Garantir que o diretório de saída exista
    os.makedirs(output_dir, exist_ok=True)
    
    print("Lendo arquivos de resposta brutos...")
    responses_data = read_raw_responses(str(base_path))
    
    print("Lendo perguntas de pesquisa...")
    questions = read_research_questions(str(yaml_path))
    
    print("Lendo informações de artigos...")
    articles = read_article_info(str(json_path))
    
    print("Criando arquivos Excel...")
    create_excel_from_data(responses_data, questions, articles, str(output_path), str(simple_output_path))
    
    print(f"Arquivos Excel criados com sucesso:")
    print(f"- Arquivo completo: {output_path}")
    print(f"- Arquivo simplificado: {simple_output_path}")
    return str(output_path), str(simple_output_path)









