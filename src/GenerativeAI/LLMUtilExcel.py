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

    def _unwrap_single_id(parsed: Any) -> Any:
        # Se vier {"<id>": {...}} sem chave "id", promove a chave a campo "id".
        if isinstance(parsed, dict) and len(parsed) == 1 and "id" not in parsed:
            new_dict: Dict[str, Any] = {}
            for key, value in parsed.items():
                new_dict["id"] = key
                if isinstance(value, dict):
                    new_dict = new_dict | value
            return new_dict
        return parsed

    # 1) Tentativa direta.
    try:
        return _unwrap_single_id(json.loads(content))
    except json.JSONDecodeError:
        pass

    # 2) Lidar com vírgulas finais (",}" / ",]").
    try:
        fixed = re.sub(r',\s*]', ']', re.sub(r',\s*}', '}', content))
        return _unwrap_single_id(json.loads(fixed))
    except json.JSONDecodeError:
        pass

    # 3) Lidar com "Extra data" — lixo após um objeto JSON válido (ex.: um '}' extra que
    #    o gemini às vezes emite). raw_decode lê o primeiro valor JSON válido e ignora o
    #    restante, salvando a resposta sem precisar de conversão via LLM.
    try:
        decoded, _end = json.JSONDecoder().raw_decode(content.lstrip())
        return _unwrap_single_id(decoded)
    except json.JSONDecodeError as e:
        first_error = e

    # 4) Último recurso: reparo robusto de JSON de LLM (aspas/vírgulas/caracteres de
    #    controle faltando) via json_repair. Determinístico e sem chamar LLM. O import é
    #    protegido: se a lib não estiver instalada, cai no fallback de conteúdo bruto.
    try:
        import json_repair
        repaired = json_repair.loads(content)
        if isinstance(repaired, dict) and repaired:
            return _unwrap_single_id(repaired)
    except Exception:
        pass

    print(f"Falha ao analisar JSON: {first_error}")
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
    Prioriza leitura de JSONs já processados em final_json para evitar reprocessamento.
    
    Args:
        base_path: Caminho base dos arquivos de resposta
        
    Returns:
        Dicionário com os dados extraídos organizados por provedor
    """
    # Determinar diretório base do projeto
    # base_path é .data/OUTPUTS/raw_responses
    # Precisamos .data/OUTPUTS/processed_responses/final_json
    outputs_dir = os.path.dirname(base_path)  # .data/OUTPUTS
    processed_json_base = os.path.join(outputs_dir, "processed_responses", "final_json")
    
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
    reused_count = 0  # Track how many JSONs were reused
    processed_count = 0  # Track how many files were processed
    
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
                    
                    response_id_formatted = "'" + str(response_id).zfill(5)
                    
                    # NOVA LÓGICA: Verificar se já existe JSON processado
                    json_filename = file.replace("_raw.txt", ".json")
                    processed_json_path = os.path.join(processed_json_base, provider_name, model, json_filename)
                    
                    parsed_content = None
                    
                    # Tentar ler JSON já processado primeiro
                    if os.path.exists(processed_json_path):
                        try:
                            with open(processed_json_path, 'r', encoding='utf-8') as f:
                                parsed_content = json.load(f)
                            reused_count += 1
                            # print(f"Reusando JSON processado: {json_filename}")
                        except Exception as e:
                            print(f"Erro ao ler JSON processado {processed_json_path}: {e}")
                            parsed_content = None
                    
                    # Se não encontrou JSON processado, processar o raw
                    if parsed_content is None:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
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
                        
                        processed_count += 1
                        
                        # Salvar o JSON processado para reuso futuro
                        if parsed_content and "raw_content" not in parsed_content and "error" not in parsed_content:
                            save_parsed_json(parsed_content, provider_name, model, file)
                    
                    if parsed_content:
                        # Adicionar metadados
                        if isinstance(parsed_content, list):
                            for item in parsed_content:
                                if isinstance(item, dict):  # Check if item is a dictionary
                                    item['_response_id'] = response_id_formatted
                                    item['_provider'] = provider_name
                                    item['_model'] = model
                                    item['_file'] = file
                                    item['_json_path'] = processed_json_path
                                    results[provider].append(item)
                        else:
                            parsed_content['_response_id'] = response_id_formatted
                            parsed_content['_provider'] = provider_name
                            parsed_content['_model'] = model
                            parsed_content['_file'] = file
                            parsed_content['_json_path'] = processed_json_path
                            results[provider].append(parsed_content)
                except Exception as e:
                    print(f"Erro ao processar arquivo {file_path}: {e}")
                    unconverted_files.append(file_path)
    
    # Save log of unconverted files
    if unconverted_files:
        save_unconverted_files_log(unconverted_files)
    
    # Imprimir estatísticas de reuso
    total_files = reused_count + processed_count
    if total_files > 0:
        print(f"\nEstatísticas de processamento:")
        print(f"  - JSONs reutilizados: {reused_count}/{total_files} ({100*reused_count//total_files if total_files > 0 else 0}%)")
        print(f"  - Arquivos processados: {processed_count}/{total_files} ({100*processed_count//total_files if total_files > 0 else 0}%)")
    
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
                    flat_response[f'{q_key}_{sub_key}'] = sub_value
            else:
                flat_response[f'{q_key}'] = q_value
    
    # Processar perguntas de suporte
    if 'supporting_questions' in response:
        for q_key, q_value in response['supporting_questions'].items():
            if isinstance(q_value, dict):
                for sub_key, sub_value in q_value.items():
                    flat_response[f'{q_key}_{sub_key}'] = sub_value
            else:
                flat_response[f'{q_key}'] = q_value
    
    # Processar critérios de aceitação
    if 'accepted_criteria' in response:
        for c_key, c_value in response['accepted_criteria'].items():
            if isinstance(c_value, dict):
                for sub_key, sub_value in c_value.items():
                    flat_response[f'{c_key}_{sub_key}'] = sub_value
            else:
                flat_response[f'{c_key}'] = c_value
    
    # Processar critérios de rejeição
    if 'rejection_criteria' in response:
        for c_key, c_value in response['rejection_criteria'].items():
            if isinstance(c_value, dict):
                for sub_key, sub_value in c_value.items():
                    flat_response[f'{c_key}_{sub_key}'] = sub_value
            else:
                flat_response[f'{c_key}'] = c_value
    
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


def classify_answer(value: Any) -> str:
    """
    Classifica um valor de resposta em: 'positive', 'negative' ou 'other'.
    
    Args:
        value: Valor a ser verificado
        
    Returns:
        String indicando o tipo de resposta: 'positive', 'negative' ou 'other'
    """
    if not isinstance(value, str):
        return 'other'
    
    normalized_value = value.lower().strip()
    
    # Respostas positivas
    if normalized_value in ['yes', 'sim']:
        return 'positive'
    
    # Respostas negativas
    if normalized_value in ['no', 'não', 'nao']:
        return 'negative'
    
    # Outras respostas (not sure, maybe, etc.)
    return 'other'


def is_positive_answer(value: Any) -> bool:
    """
    Verifica se um valor representa uma resposta positiva.
    Mantida para compatibilidade, mas usa classify_answer internamente.
    
    Args:
        value: Valor a ser verificado
        
    Returns:
        True se o valor for uma resposta positiva, False caso contrário
    """
    return classify_answer(value) == 'positive'


def consolidate_responses_by_doi(responses_data: Dict[str, List[Dict]], 
                                  articles: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Consolida respostas por _response_id, somando contagens de todos os modelos.
    
    Args:
        responses_data: Dados de respostas organizados por provedor
        articles: Informações dos artigos
        
    Returns:
        Lista de dicionários consolidados por _response_id com somatória de todos os modelos
    """
    # Dicionário para agrupar respostas por _response_id
    consolidated: Dict[str, Dict[str, Any]] = {}
    
    # Coletar todos os campos de resposta (answer) existentes
    all_answer_fields = set()
    
    # Primeira passagem: identificar todos os campos answer
    for provider, responses in responses_data.items():
        for response in responses:
            flat_response = flatten_json_response(response, articles)
            
            # Coletar campos answer
            for key in flat_response.keys():
                if key.endswith('_answer'):
                    # Extrair o prefixo do campo (ex: rq_principal_research_question, is_relevant)
                    field_prefix = key.replace('_answer', '')
                    all_answer_fields.add(field_prefix)
    
    # Segunda passagem: consolidar respostas por _response_id
    for provider, responses in responses_data.items():
        for response in responses:
            flat_response = flatten_json_response(response, articles)
            
            # Obter identificadores
            response_id = flat_response.get('_response_id', '')
            if not response_id:
                continue
            
            # Usar _response_id como chave única
            key = response_id
            
            # Inicializar entrada se não existir
            if key not in consolidated:
                consolidated[key] = {
                    '_response_id': response_id,
                    'id': flat_response.get('id', ''),
                    'doi': flat_response.get('doi', ''),
                    'article_title': flat_response.get('article_title', ''),
                    'article_abstract': flat_response.get('article_abstract', ''),
                    'article_keywords': flat_response.get('article_keywords', ''),
                    'total_responses': 0,
                    'providers': set(),
                    'models': set()
                }
                
                # Inicializar contadores para cada campo de resposta (sem prefixo de modelo)
                for field_prefix in all_answer_fields:
                    consolidated[key][f'{field_prefix}_yes_count'] = 0
                    consolidated[key][f'{field_prefix}_no_count'] = 0
                    consolidated[key][f'{field_prefix}_other_count'] = 0
                    consolidated[key][f'{field_prefix}_total_count'] = 0
                    consolidated[key][f'{field_prefix}_yes_percent'] = 0.0
                    consolidated[key][f'{field_prefix}_no_percent'] = 0.0
                    consolidated[key][f'{field_prefix}_other_percent'] = 0.0
            else:
                # Atualizar id e doi se estiverem vazios e agora temos valores
                if not consolidated[key]['id'] and flat_response.get('id'):
                    consolidated[key]['id'] = flat_response.get('id', '')
                if not consolidated[key]['doi'] and flat_response.get('doi'):
                    consolidated[key]['doi'] = flat_response.get('doi', '')
                if not consolidated[key]['article_title'] and flat_response.get('article_title'):
                    consolidated[key]['article_title'] = flat_response.get('article_title', '')
                if not consolidated[key]['article_abstract'] and flat_response.get('article_abstract'):
                    consolidated[key]['article_abstract'] = flat_response.get('article_abstract', '')
                if not consolidated[key]['article_keywords'] and flat_response.get('article_keywords'):
                    consolidated[key]['article_keywords'] = flat_response.get('article_keywords', '')
            
            # Atualizar contadores gerais
            consolidated[key]['total_responses'] += 1
            consolidated[key]['providers'].add(flat_response.get('_provider', 'unknown'))
            
            # Obter modelo da resposta
            model = flat_response.get('_model', 'unknown')
            consolidated[key]['models'].add(model)
            
            # Contar respostas (positivas, negativas, outras) para cada campo answer
            # Soma de todos os modelos (sem prefixo de modelo)
            for field_prefix in all_answer_fields:
                answer_key = f'{field_prefix}_answer'
                if answer_key in flat_response:
                    answer_value = flat_response[answer_key]
                    consolidated[key][f'{field_prefix}_total_count'] += 1
                    
                    # Classificar resposta
                    answer_type = classify_answer(answer_value)
                    if answer_type == 'positive':
                        consolidated[key][f'{field_prefix}_yes_count'] += 1
                    elif answer_type == 'negative':
                        consolidated[key][f'{field_prefix}_no_count'] += 1
                    else:
                        consolidated[key][f'{field_prefix}_other_count'] += 1
    
    # Converter sets para strings, calcular percentuais e preparar resultado final
    result = []
    for key, data in consolidated.items():
        data['providers'] = ', '.join(sorted(data['providers']))
        data['models'] = ', '.join(sorted(data['models']))
        
        # Calcular percentuais para cada campo
        for field_prefix in all_answer_fields:
            total = data[f'{field_prefix}_total_count']
            if total > 0:
                data[f'{field_prefix}_yes_percent'] = round((data[f'{field_prefix}_yes_count'] / total) * 100, 2)
                data[f'{field_prefix}_no_percent'] = round((data[f'{field_prefix}_no_count'] / total) * 100, 2)
                data[f'{field_prefix}_other_percent'] = round((data[f'{field_prefix}_other_count'] / total) * 100, 2)
        
        result.append(data)
    
    # Ordenar por _response_id
    result.sort(key=lambda x: x.get('_response_id', ''))
    
    return result


def create_consolidated_excel(consolidated_data: List[Dict[str, Any]], 
                               output_path: str,
                               questions: Optional[Dict[str, str]] = None) -> None:
    """
    Cria arquivo Excel consolidado com contagens de respostas por _response_id (somatória de todos os modelos).
    
    Args:
        consolidated_data: Dados consolidados por _response_id
        output_path: Caminho para salvar o arquivo Excel consolidado
        questions: Dicionário com siglas e perguntas de pesquisa (opcional)
    """
    if not consolidated_data:
        print("Nenhum dado consolidado para gerar Excel")
        return
    
    # Converter para DataFrame
    df = pd.DataFrame(consolidated_data)
    
    # Reordenar colunas para melhor legibilidade
    # Colunas básicas primeiro
    basic_cols = ['_response_id', 'id', 'doi', 'article_title', 'article_abstract', 'article_keywords', 
                  'total_responses', 'providers', 'models']
    
    # Colunas de contagem (sem prefixo de modelo)
    count_cols = [col for col in df.columns if col not in basic_cols]
    
    # Extrair campos únicos
    fields = set()
    for col in count_cols:
        # Remover sufixos para encontrar o campo base
        for suffix in ['_total_count', '_yes_count', '_no_count', '_other_count',
                      '_yes_percent', '_no_percent', '_other_percent']:
            if col.endswith(suffix):
                field = col.replace(suffix, '')
                fields.add(field)
                break
    
    # Separar campos prioritários
    priority_fields = []
    other_fields = []
    
    # Primeiro adicionar is_relevant e principal_research_question se existirem
    if 'is_relevant' in fields:
        priority_fields.append('is_relevant')
    if 'principal_research_question' in fields:
        priority_fields.append('principal_research_question')
    
    # Adicionar outros campos em ordem alfabética
    for field in sorted(fields):
        if field not in priority_fields:
            other_fields.append(field)
    
    # Ordenar colunas: campos prioritários primeiro, depois outros campos ordenados
    count_cols_sorted = []
    for field in priority_fields + other_fields:
        for suffix in ['_total_count', '_yes_count', '_no_count', '_other_count',
                      '_yes_percent', '_no_percent', '_other_percent']:
            col_name = f'{field}{suffix}'
            if col_name in count_cols:
                count_cols_sorted.append(col_name)
    
    # Adicionar colunas que não foram processadas
    for col in count_cols:
        if col not in count_cols_sorted:
            count_cols_sorted.append(col)
    
    # Combinar todas as colunas na ordem desejada
    ordered_cols = [col for col in basic_cols if col in df.columns] + count_cols_sorted
    df = df[ordered_cols]
    
    # Criar arquivo Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Consolidated', index=False)
        
        # Adicionar aba Research Questions se fornecida
        if questions:
            questions_df = pd.DataFrame({
                'question_id': list(questions.keys()),
                'question_text': list(questions.values())
            })
            questions_df.to_excel(writer, sheet_name='Research Questions', index=False)
        
        # Ajustar largura das colunas (opcional, para melhor visualização)
        worksheet = writer.sheets['Consolidated']
        from openpyxl.utils import get_column_letter
        for idx, col in enumerate(df.columns, 1):
            max_length = max(
                df[col].astype(str).apply(len).max(),
                len(col)
            )
            # Limitar largura máxima para evitar colunas muito largas
            max_length = min(max_length, 50)
            worksheet.column_dimensions[get_column_letter(idx)].width = max_length + 2
    
    print(f"Arquivo Excel consolidado criado: {output_path}")
    
    # Exportar também para JSON
    json_output_path = output_path.replace('.xlsx', '.json')
    df.to_json(json_output_path, orient='records', indent=2, force_ascii=False)
    print(f"Arquivo JSON consolidado criado: {json_output_path}")


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
            
            # Filtrar colunas de perguntas e respostas
            # Agora os campos não têm mais prefixos duplicados (ex: ac1_answer em vez de ac_ac1_answer)
            # Incluir campos que começam com padrões conhecidos ou is_relevant
            question_cols = [col for col in df.columns 
                            if ((col.startswith('principal_research_question') or 
                                 col.startswith('arq') or
                                 col.startswith('sq') or 
                                 col.startswith('ac') or 
                                 col.startswith('rc') or
                                 col.startswith('is_relevant')) and 
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


def process_responses_to_excel(base_dir: Optional[str] = None) -> Tuple[str, str, str]:
    """
    Função principal para processar respostas e criar os arquivos Excel.
    
    Args:
        base_dir: Diretório base do projeto (opcional)
        
    Returns:
        Tupla com os caminhos para os arquivos Excel gerados (completo, simplificado, consolidado)
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
    consolidated_output_path = os.path.join(output_dir, "combined_responses_consolidated.xlsx")
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
    
    print("Criando arquivo Excel consolidado...")
    consolidated_data = consolidate_responses_by_doi(responses_data, articles)
    create_consolidated_excel(consolidated_data, str(consolidated_output_path), questions)
    
    print(f"Arquivos Excel criados com sucesso:")
    print(f"- Arquivo completo: {output_path}")
    print(f"- Arquivo simplificado: {simple_output_path}")
    print(f"- Arquivo consolidado: {consolidated_output_path}")
    return str(output_path), str(simple_output_path), str(consolidated_output_path)









