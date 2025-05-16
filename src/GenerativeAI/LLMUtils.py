import os
import json
from src.BibTex import read_bibtex, write_bibtex
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import yaml

# Carregar variáveis de ambiente do arquivo .env
load_dotenv(os.path.abspath(".conf"))

def read_bibtex_file(bibtex_path: str) -> List[Dict[str, Any]]:
    """
    Lê um único arquivo BibTex e retorna uma lista com seus registros.
    
    Args:
        bibtex_path (str): Caminho para o arquivo BibTex
        
    Returns:
        List[Dict[str, Any]]: Lista contendo os registros BibTex
    """
    try:
        entries = read_bibtex(bibtex_path)
        if entries:
            print(f"Lidos {len(entries)} registros do arquivo {bibtex_path}")
            return entries
        else:
            print(f"Nenhum registro encontrado no arquivo {bibtex_path}")
            return []
    except Exception as e:
        print(f"Erro ao ler o arquivo BibTex {bibtex_path}: {e}")
        return []

def convert_bibtex_to_json_schema(bibtex_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Converte entradas BibTex para o formato JSON conforme o schema definido.
    
    Args:
        bibtex_entries (List[Dict[str, Any]]): Lista de entradas BibTex de um arquivo
        
    Returns:
        List[Dict[str, Any]]: Lista de dicionários no formato do schema JSON
    """
    json_entries = []
    
    for entry in bibtex_entries:
        title = entry.get('title', '').strip('{').strip('}')
        doi = entry.get('doi', entry.get('DOI', title.replace(' ', '_')))
        id = entry.get('ID', doi)
        
        # Criar a estrutura JSON conforme o schema
        json_entry = {
            "id": id,
            "doi": doi,
            "title": title,
            "abstract": entry.get('abstract', ''),
            "keywords": entry.get('author_keywords', entry.get('keywords', '')),
            
        }
        json_entries.append(json_entry)
    
    print(f"Convertidos {len(json_entries)} registros para o formato JSON")
    return json_entries

def save_json_to_file(json_data: List[Dict[str, Any]], output_path: str) -> None:
    """
    Salva os dados JSON em um arquivo.
    
    Args:
        json_data (List[Dict[str, Any]]): Dados a serem salvos
        output_path (str): Caminho completo para o arquivo de saída
    """
    try:
        # Garantir que o diretório exista
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # Salvar o arquivo JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"Arquivo JSON salvo com sucesso em {output_path}")
    except Exception as e:
        print(f"Erro ao salvar o arquivo JSON: {e}")

def save_prompt_base(prompt_txt: str, output_path: Optional[str] = None) -> None:
    """
    Salva o prompt base em um arquivo de texto.

    Args:
        prompt_txt (str): O texto do prompt a ser salvo
        output_path (str, optional): Caminho para salvar o arquivo de texto. Se None,
                                    usa o caminho padrão em PATH_DATA/OUTPUTS/select_bibs_prompt_base.txt
    """
    try:
        if not output_path:
            output_path = os.path.join(os.getenv("PATH_DATA", ".data"), "OUTPUTS", "select_bibs_prompt_base.md") 
        
        # Garantir que o diretório exista
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        # Salvar o arquivo de texto
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(prompt_txt)

        print(f"Arquivo de texto salvo com sucesso em {output_path}")
    except Exception as e:
        print(f"Erro ao salvar o arquivo de texto: {e}")

def bibtex_to_json_schema(bibtex_path: str, output_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Função principal que processa um arquivo BibTex e gera JSON conforme o schema.
    
    Args:
        bibtex_path (str): Caminho para o arquivo BibTex
        output_path (Optional[str]): Caminho para salvar o arquivo JSON. Se None,
                                    usa o caminho padrão em PATH_DATA/OUTPUTS/
        
    Returns:
        List[Dict[str, Any]]: Lista de registros no formato JSON
    """
    # Ler o arquivo BibTex
    bibtex_entries = read_bibtex_file(bibtex_path)
    
    # Converter para o formato JSON conforme o schema
    json_entries = convert_bibtex_to_json_schema(bibtex_entries)
    
    # Definir o caminho de saída se não fornecido
    if output_path is None:
        path_data = os.getenv("PATH_DATA", ".data")
        output_dir = os.path.join(path_data, "OUTPUTS")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.abspath(os.path.join(output_dir, "select_bibs.json"))
    
    # Salvar o JSON
    save_json_to_file(json_entries, output_path)
    
    return json_entries

def prepare_base_prompt(select_bib_json: List[Dict[str, Any]]) -> str:
    """
    Prepara o prompt base lendo os arquivos de configuração e preenchendo o template
    com as informações coletadas e os abstracts de artigos.
    
    Args:
        select_bib_json (List[Dict[str, Any]]): Lista de dicionários com dados de artigos
    
    Returns:
        str: O prompt base preenchido com todas as informações
    """
    # Definir caminhos dos arquivos de configuração
    base_path = os.getenv("PROJECT_PATH", os.path.dirname(os.path.abspath(__file__)))
    base_path = os.path.abspath(base_path)    
    research_questions_path = os.path.join(base_path, 'Config', 'research_questions.yaml')
    search_config_path = os.path.join(base_path, 'Config', 'search_config.yaml')
    prompt_template_path = os.path.join(base_path, 'src', 'GenerativeAI', 'abstract_base_prompts.yaml')
    
    # Ler arquivos de configuração
    try:
        # Ler as perguntas de pesquisa
        with open(research_questions_path, 'r', encoding='utf-8') as file:
            research_questions = yaml.safe_load(file)
        
        # Ler a configuração de busca
        with open(search_config_path, 'r', encoding='utf-8') as file:
            search_config = yaml.safe_load(file)
        
        # Ler o template do prompt
        with open(prompt_template_path, 'r', encoding='utf-8') as file:
            prompt_template = yaml.safe_load(file)['base_prompt']
            
    except Exception as e:
        print(f"Erro ao ler arquivos de configuração: {e}")
        return ""
    
    # Formatar as perguntas de pesquisa
    questions_formatted = f"principal_research_question: {research_questions['principal_research_question']}\n"
    for key, question in research_questions.get('additional_research_questions', {}).items():
        questions_formatted += f"{key}: {question}\n"
    
    # Formatar as perguntas de suporte (supporting questions)
    supporting_questions_formatted = ""
    for key, question in research_questions.get('supporting_questions', {}).items():
        supporting_questions_formatted += f"{key}: {question}\n"
    
    # Formatar os critérios de rejeição
    rejection_criteria_formatted = ""
    for key, criteria in research_questions.get('rejection_criteria', {}).items():
        rejection_criteria_formatted += f"{key}: {criteria}\n"
    
    # Formatar os critérios de aceitação
    accepted_criteria_formatted = ""
    for key, criteria in research_questions.get('accepted_criteria', {}).items():
        accepted_criteria_formatted += f"{key}: {criteria}\n"
    
    # Converter os abstracts para string JSON formatada
    # articles_abstracts_json = json.dumps(select_bib_json, ensure_ascii=False, indent=2)
    articles_abstracts_json = ""
    for entry in select_bib_json:
        articles_abstracts_json += f' - Title: "{entry['title']}"\n'
        articles_abstracts_json += f' - Abstract: "{entry['abstract']}"\n'
        articles_abstracts_json += f' - Keywords: "{entry['keywords']}"\n'
        articles_abstracts_json += f' - ID: "{entry['id']}"\n---\n\n'
    articles_abstracts_json = articles_abstracts_json.strip()
    
    # Preencher o template com as informações coletadas
    filled_prompt = prompt_template.replace("{{query}}", search_config['search_string'])
    filled_prompt = filled_prompt.replace("{{questions}}", questions_formatted)
    filled_prompt = filled_prompt.replace("{{supporting_questions}}", supporting_questions_formatted)
    filled_prompt = filled_prompt.replace("{{rejection_criteria}}", rejection_criteria_formatted)
    filled_prompt = filled_prompt.replace("{{accepted_criteria}}", accepted_criteria_formatted)
    filled_prompt = filled_prompt.replace("{{principal_research_question}}", research_questions['principal_research_question'])
    filled_prompt = filled_prompt.replace("{{json_articles_abstracts}}", articles_abstracts_json)
    
    save_prompt_base(filled_prompt)
    
    return filled_prompt

def prepare_single_article_prompt(article: Dict[str, Any]) -> str:
    """
    Prepara o prompt base para um único artigo, lendo os arquivos de configuração e preenchendo o template
    com as informações coletadas e o abstract do artigo específico.
    
    Args:
        article (Dict[str, Any]): Dicionário contendo os dados de um único artigo
    
    Returns:
        str: O prompt base preenchido com as informações do artigo
    """
    # Definir caminhos dos arquivos de configuração
    base_path = os.getenv("PROJECT_PATH", os.path.dirname(os.path.abspath(__file__)))
    base_path = os.path.abspath(base_path)    
    research_questions_path = os.path.join(base_path, 'Config', 'research_questions.yaml')
    search_config_path = os.path.join(base_path, 'Config', 'search_config.yaml')
    prompt_template_path = os.path.join(base_path, 'src', 'GenerativeAI', 'abstract_base_prompts_one_on_one.yaml')
    
    # Ler arquivos de configuração
    try:
        # Ler as perguntas de pesquisa
        with open(research_questions_path, 'r', encoding='utf-8') as file:
            research_questions = yaml.safe_load(file)
        
        # Ler a configuração de busca
        with open(search_config_path, 'r', encoding='utf-8') as file:
            search_config = yaml.safe_load(file)
        
        # Ler o template do prompt
        with open(prompt_template_path, 'r', encoding='utf-8') as file:
            prompt_template = yaml.safe_load(file)['base_prompt']
            
    except Exception as e:
        print(f"Erro ao ler arquivos de configuração: {e}")
        return ""
    
    # Formatar as perguntas de pesquisa
    questions_formatted = f"principal_research_question: {research_questions['principal_research_question']}\n"
    for key, question in research_questions.get('additional_research_questions', {}).items():
        questions_formatted += f"{key}: {question}\n"
    
    # Formatar as perguntas de suporte (supporting questions)
    supporting_questions_formatted = ""
    for key, question in research_questions.get('supporting_questions', {}).items():
        supporting_questions_formatted += f"{key}: {question}\n"
    
    # Formatar os critérios de rejeição
    rejection_criteria_formatted = ""
    for key, criteria in research_questions.get('rejection_criteria', {}).items():
        rejection_criteria_formatted += f"{key}: {criteria}\n"
    
    # Formatar os critérios de aceitação
    accepted_criteria_formatted = ""
    for key, criteria in research_questions.get('accepted_criteria', {}).items():
        accepted_criteria_formatted += f"{key}: {criteria}\n"
    
    # Formatar o artigo individual
    article_formatted = f' - Title: "{article["title"]}"\n'
    article_formatted += f' - Abstract: "{article["abstract"]}"\n'
    article_formatted += f' - Keywords: "{article["keywords"]}"\n'
    article_formatted += f' - ID: "{article["id"]}"\n'
    
    # Preencher o template com as informações coletadas
    filled_prompt = prompt_template.replace("{{query}}", search_config['search_string'])
    filled_prompt = filled_prompt.replace("{{questions}}", questions_formatted)
    filled_prompt = filled_prompt.replace("{{supporting_questions}}", supporting_questions_formatted)
    filled_prompt = filled_prompt.replace("{{rejection_criteria}}", rejection_criteria_formatted)
    filled_prompt = filled_prompt.replace("{{accepted_criteria}}", accepted_criteria_formatted)
    filled_prompt = filled_prompt.replace("{{principal_research_question}}", research_questions['principal_research_question'])
    filled_prompt = filled_prompt.replace("{{json_articles_abstracts}}", article_formatted)
    
    return filled_prompt

def run_prepare_base_prompt(input_bibtex_path: Optional[str] = None, 
                            output_path: Optional[str] = None) -> str:
    """
    Função principal para classificar abstracts usando processamento de bibtex para JSON.
    
    Args:
        input_bibtex_path (Optional[str]): Caminho para um único arquivo BibTeX.
                                            Se None, usa o caminho padrão.
        output_path (Optional[str]): Caminho para salvar o arquivo JSON.
                                        Se None, usa o caminho padrão.
    
    Returns:
        str: O prompt base gerado a partir dos dados JSON
    """
    # Configuração do PATH_DATA
    path_data = os.getenv("PATH_DATA", ".data")
    
    # Definir diretório de saída padrão
    default_output_dir = os.path.join(path_data, "OUTPUTS")
    os.makedirs(default_output_dir, exist_ok=True)
    
    # Definir caminho de saída padrão se não fornecido
    if output_path is None:
        output_path = os.path.abspath(os.path.join(default_output_dir, "select_bibs.json"))
    
    # Processar caminho de entrada
    if input_bibtex_path is None:
        # Se nenhum caminho for fornecido, tentar usar um caminho padrão
        bib_file = os.getenv("BIB_FILE", ".OUTPUTS/select_bibs.bib")
        input_bibtex_path = os.path.join(path_data, bib_file)
        print(f"Nenhum caminho de entrada especificado, usando o padrão: {input_bibtex_path}")
    
    # Converter BibTex para JSON e salvar
    json_data = bibtex_to_json_schema(input_bibtex_path, output_path)
    
    if not json_data:
        print("Erro ao converter BibTex para JSON.")
        raise ValueError("Nenhum dado JSON foi gerado.")
    
    # Preparar o prompt base
    prompt = prepare_base_prompt(json_data)
    if not prompt:
        print("Erro ao preparar o prompt base.")
        raise ValueError("Nenhum prompt base foi gerado.")
    
    return prompt

def run_prepare_base_prompt_list(input_bibtex_path: Optional[str] = None, 
                                output_path: Optional[str] = None) -> List[str]:
    """
    Função que gera uma lista de prompts, um para cada artigo do arquivo BibTeX,
    e salva todos em um único arquivo markdown.
    
    Args:
        input_bibtex_path (Optional[str]): Caminho para um único arquivo BibTeX.
                                            Se None, usa o caminho padrão.
        output_path (Optional[str]): Caminho para salvar o arquivo markdown com todos os prompts.
                                        Se None, usa o caminho padrão.
    
    Returns:
        List[str]: Lista de prompts, um para cada artigo
    """
    # Configuração do PATH_DATA
    path_data = os.getenv("PATH_DATA", ".data")
    
    # Definir diretório de saída padrão
    default_output_dir = os.path.join(path_data, "OUTPUTS")
    os.makedirs(default_output_dir, exist_ok=True)
    
    # Definir caminho de saída padrão para o JSON se não fornecido
    json_output_path = None
    if output_path is None:
        json_output_path = os.path.abspath(os.path.join(default_output_dir, "select_bibs.json"))
    else:
        json_output_path = output_path
    
    # Definir caminho para o arquivo markdown com todos os prompts
    all_prompts_md_path = os.path.join(default_output_dir, "all_article_prompts.md")
    
    # Processar caminho de entrada
    if input_bibtex_path is None:
        # Se nenhum caminho for fornecido, tentar usar um caminho padrão
        bib_file = os.getenv("BIB_FILE", ".OUTPUTS/select_bibs.bib")
        input_bibtex_path = os.path.join(path_data, bib_file)
        print(f"Nenhum caminho de entrada especificado, usando o padrão: {input_bibtex_path}")
    
    # Converter BibTex para JSON
    json_data = bibtex_to_json_schema(input_bibtex_path, json_output_path)
    
    if not json_data:
        print("Erro ao converter BibTex para JSON.")
        raise ValueError("Nenhum dado JSON foi gerado.")
    
    # Lista para armazenar os prompts individuais
    prompts_list = []
    
    # Conteúdo do arquivo markdown
    markdown_content = "# Prompts para Análise Individual de Artigos\n\n"
    
    # Gerar um prompt para cada artigo
    for idx, article in enumerate(json_data):
        # Gerar prompt para o artigo atual
        prompt = prepare_single_article_prompt(article)
        if not prompt:
            print(f"Erro ao preparar o prompt para o artigo {article['id']}")
            continue
        
        prompts_list.append(prompt)
        
        # Adicionar o prompt ao conteúdo markdown
        markdown_content += f"## Artigo {idx+1}: {article['id']}\n\n"
        markdown_content += "```\n"
        markdown_content += prompt
        markdown_content += "\n```\n\n"
        markdown_content += "---\n\n"
    
    # Salvar todos os prompts em um único arquivo markdown
    try:
        with open(all_prompts_md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"Arquivo com todos os prompts salvo com sucesso em {all_prompts_md_path}")
    except Exception as e:
        print(f"Erro ao salvar o arquivo markdown com todos os prompts: {e}")
    
    print(f"Gerados {len(prompts_list)} prompts individuais")
    
    return prompts_list
