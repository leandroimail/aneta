import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
import yaml
import pandas as pd

# Carregar variáveis de ambiente do arquivo .env
load_dotenv(os.path.abspath(".conf"))


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
    content = content.strip()
    
    # Tentar analisar como JSON
    try:
        return json.loads(content)
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


def extract_responses_from_raw_text(file_content: str, research_questions: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Extrai respostas do texto bruto quando a análise JSON falha.
    Tenta identificar padrões de resposta para as perguntas de pesquisa com base em prefixos.
    
    Args:
        file_content: Conteúdo do arquivo de resposta
        research_questions: Dicionário com as perguntas de pesquisa (opcional)
        
    Returns:
        Dicionário com informações extraídas do texto bruto
    """
    results = {}
    
    # Primeiro, tentar encontrar o ID do artigo
    id_pattern = r'(?:id|ID|Id|article[_\s]id|artigo[_\s]id)[\s:]+(\d+)'
    id_match = re.search(id_pattern, file_content)
    if id_match:
        results['id'] = id_match.group(1).strip()
    
    # Buscar respostas baseadas em prefixos
    # Preparar o conteúdo para busca por linhas, limpando espaços extras
    lines = [line.strip() for line in file_content.split('\n') if line.strip()]
    
    # Prefixos específicos que devem ter resposta YES/NO
    yes_no_prefixes = [
        'rq_principal_', 'rq_arq', 'sq_', 'ac_ac', 'rc_rc', 'is_relevant_answer'
    ]
    
    # Processar cada linha
    for line in lines:
        # Tentar encontrar qualquer prefixo de pergunta
        prefix_match = re.search(r'^((?:rq|sq|ac|rc|is_relevant)_\w+)[\s:]+(.+)', line, re.IGNORECASE)
        
        if prefix_match:
            prefix = prefix_match.group(1).lower()
            answer = prefix_match.group(2).strip()
            
            # Verificar se é um prefixo que deve ter resposta YES/NO
            is_yes_no_prefix = any(prefix.startswith(yp) for yp in yes_no_prefixes)
            
            if is_yes_no_prefix:
                # Normalizar resposta para YES/NO
                answer_lower = answer.lower()
                if any(pos in answer_lower for pos in ['yes', 'sim', 'true', 'verdadeiro']):
                    results[prefix] = "YES"
                elif any(neg in answer_lower for neg in ['no', 'não', 'false', 'falso']):
                    results[prefix] = "NO"
            else:
                # Para outros prefixos, usar a resposta como está
                results[prefix] = answer
    
    # Buscar is_relevant (tratamento especial)
    if 'is_relevant' not in results and 'is_relevant_answer' not in results:
        relevant_patterns = [
            r'(?:is_relevant|is relevant|relevante|relevância)[\s:]+(true|false|yes|no|sim|não|verdadeiro|falso)',
            r'(?:artigo|article)[\s\w]*(?:é|is)[\s\w]*(?:relevant|relevante)[\s:]*([^.\n,]+)'
        ]
        
        for pattern in relevant_patterns:
            relevant_match = re.search(pattern, file_content, re.IGNORECASE)
            if relevant_match:
                value = relevant_match.group(1).strip().lower()
                if any(pos in value for pos in ['yes', 'sim', 'true', 'verdadeiro']):
                    results['is_relevant'] = "YES"
                    break
                elif any(neg in value for neg in ['no', 'não', 'false', 'falso']):
                    results['is_relevant'] = "NO"
                    break
    
    # Alternativa: buscar por padrões específicos se os prefixos não forem encontrados
    if not results or (len(results) == 1 and 'id' in results):
        # Gerar padrões baseados nas perguntas de pesquisa, se disponíveis
        patterns = {}
        
        if research_questions:
            # Gerar padrões para a pergunta principal
            if 'principal_research_question' in research_questions:
                key_phrases = extract_key_phrases(research_questions['principal_research_question'])
                if key_phrases:
                    pattern = r'(?:' + '|'.join(key_phrases) + r').*?[:]\s*([^#\n]+)'
                    patterns['rq_principal_research_question'] = pattern
            
            # Gerar padrões para perguntas adicionais
            for key, question in research_questions.items():
                if key.startswith('arq'):
                    key_phrases = extract_key_phrases(question)
                    if key_phrases:
                        pattern = r'(?:' + '|'.join(key_phrases) + r').*?[:]\s*([^#\n]+)'
                        patterns[f'rq_{key}'] = pattern
                        
            # Gerar padrões para perguntas de suporte
            for key, question in research_questions.items():
                if key.startswith('sq'):
                    key_phrases = extract_key_phrases(question)
                    if key_phrases:
                        pattern = r'(?:' + '|'.join(key_phrases) + r').*?[:]\s*([^#\n]+)'
                        patterns[f'sq_{key}'] = pattern
                        
            # Gerar padrões para critérios de aceitação
            for key, question in research_questions.items():
                if key.startswith('ac'):
                    key_phrases = extract_key_phrases(question)
                    if key_phrases:
                        pattern = r'(?:' + '|'.join(key_phrases) + r').*?[:]\s*([^#\n]+)'
                        patterns[f'ac_{key}'] = pattern
                        
            # Gerar padrões para critérios de rejeição
            for key, question in research_questions.items():
                if key.startswith('rc'):
                    key_phrases = extract_key_phrases(question)
                    if key_phrases:
                        pattern = r'(?:' + '|'.join(key_phrases) + r').*?[:]\s*([^#\n]+)'
                        patterns[f'rc_{key}'] = pattern
        
        # Se não há perguntas disponíveis ou falha na geração de padrões, usar padrões padrão
        if not patterns:
            patterns = {
                'rq_principal_research_question': r'(?:main\s*data\s*quality\s*problems|problemas\s*de\s*qualidade\s*de\s*dados).*?[:]\s*([^#\n]+)',
                'rq_arq1': r'(?:strategies|estratégias).*?(?:solve|resolver).*?(?:data\s*quality|qualidade\s*de\s*dados).*?[:]\s*([^#\n]+)',
                'sq_1': r'(?:new\s*technique|methodology|framework|algorithm|model|nova\s*técnica|metodologia|estrutura|algoritmo|modelo).*?[:]\s*([^#\n]+)',
                'ac_ac1': r'(?:data\s*quality\s*issues|problemas\s*de\s*qualidade\s*de\s*dados).*?[:]\s*([^#\n]+)',
                'ac_ac2': r'(?:strategy|approach|technique|methodology|algorithm|tool|estratégia|abordagem|técnica|metodologia|algoritmo|ferramenta).*?(?:improve|quality|melhora|qualidade).*?[:]\s*([^#\n]+)',
                'rc_rc1': r'(?:concerns\s*regarding\s*data\s*acquisition|preocupações\s*com\s*aquisição\s*de\s*dados).*?[:]\s*([^#\n]+)',
                'rc_rc2': r'(?:data\s*quality\s*issues|problemas\s*de\s*qualidade\s*de\s*dados).*?não.*?[:]\s*([^#\n]+)',
                'rc_rc3': r'(?:strategy|approach|technique|methodology|proposal|estratégia|abordagem|técnica|metodologia|proposta).*?improve.*?quality.*?[:]\s*([^#\n]+)',
                'rc_rc4': r'(?:context|marine\s*ecosystems|contexto|ecossistemas\s*marinhos).*?[:]\s*([^#\n]+)'
            }
        
        # Extrair respostas usando os padrões
        for key, pattern in patterns.items():
            match = re.search(pattern, file_content, re.IGNORECASE | re.DOTALL)
            if match:
                # Se for um prefixo de YES/NO, normalizar resposta
                if any(key.startswith(yp) for yp in yes_no_prefixes):
                    value = match.group(1).strip().lower()
                    if any(pos in value for pos in ['yes', 'sim', 'true', 'verdadeiro']):
                        results[key] = "YES"
                    elif any(neg in value for neg in ['no', 'não', 'false', 'falso']):
                        results[key] = "NO"
                else:
                    # Para outros padrões, usar a resposta como está
                    results[key] = match.group(1).strip()
    
    # Se conseguimos encontrar pelo menos algumas informações, retornar o resultado
    return results if results else {"raw_content": file_content.strip()}


def extract_key_phrases(text: str) -> List[str]:
    """
    Extrai frases-chave de uma pergunta para criar padrões de busca,
    utilizando abordagem baseada na estrutura do texto sem termos predefinidos.
    
    Args:
        text: Texto da pergunta
        
    Returns:
        Lista de frases-chave
    """
    # Limpar o texto
    text = text.lower().strip()
    keywords = []
    
    # 1. Extrair palavras longas (geralmente substantivos ou palavras-chave)
    words = re.findall(r'\b\w{4,}\b', text)
    if words:
        # Ordenar por tamanho, palavras mais longas tendem a ser mais informativas
        long_words = sorted(set(words), key=len, reverse=True)
        # Adicionar as palavras mais longas (até 5)
        keywords.extend(long_words[:5])
    
    # 2. Extrair possíveis frases nominais (substantivo + adjetivo)
    noun_phrases = re.findall(r'\b\w{3,}\s+\w{3,}\b', text)
    if noun_phrases:
        # Adicionar até 3 frases nominais mais longas
        sorted_phrases = sorted(set(noun_phrases), key=len, reverse=True)
        keywords.extend(sorted_phrases[:3])
    
    # 3. Identificar termos de questão (começam com o quê, quais, como)
    question_terms = re.findall(r'\b(what|which|how|who|where|quando|como|quais|qual|quem|onde)\s+\w+\s+\w+', text)
    if question_terms:
        keywords.extend(question_terms[:2])
    
    # 4. Capturar possíveis tópicos entre aspas
    quotes = re.findall(r'"([^"]+)"', text)
    if quotes:
        keywords.extend(quotes)
    
    # Remover duplicatas e preservar a ordem
    unique_keywords = []
    for kw in keywords:
        if kw not in unique_keywords:
            unique_keywords.append(kw)
    
    # Se não encontramos palavras-chave suficientes, usar o início da frase
    if len(unique_keywords) < 2:
        words = text.split()
        if len(words) > 5:
            # Usar as primeiras 5 palavras da pergunta
            start_phrase = ' '.join(words[:5])
            unique_keywords.append(start_phrase)
    
    # Escapar caracteres especiais para regex
    escaped_keywords = [re.escape(kw) for kw in unique_keywords]
    
    # Se ainda não temos palavras-chave, dividir em tokens e usar os primeiros
    if not escaped_keywords:
        tokens = re.findall(r'\b\w+\b', text)
        if tokens:
            escaped_keywords = [re.escape(tokens[0])]
            if len(tokens) > 1:
                escaped_keywords.append(re.escape(tokens[1]))
    
    return escaped_keywords


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
                    if parsed_content and not (len(parsed_content) == 1 and "raw_content" in parsed_content):
                        # Conteúdo JSON válido encontrado
                        pass
                    else:
                        # Tentar extrair respostas do texto bruto usando as perguntas de pesquisa
                        parsed_content = extract_responses_from_raw_text(content, research_questions)
                    
                    if parsed_content:
                        # Adicionar metadados
                        if isinstance(parsed_content, list):
                            for item in parsed_content:
                                item['_response_id'] = response_id
                                item['_provider'] = provider_name
                                item['_model'] = model
                                item['_file'] = file
                                results[provider].append(item)
                        else:
                            parsed_content['_response_id'] = response_id
                            parsed_content['_provider'] = provider_name
                            parsed_content['_model'] = model
                            parsed_content['_file'] = file
                            results[provider].append(parsed_content)
                except Exception as e:
                    print(f"Erro ao processar arquivo {file_path}: {e}")
    
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


def process_responses_to_excel(base_dir: str = None) -> Tuple[str, str]:
    """
    Função principal para processar respostas e criar os arquivos Excel.
    
    Args:
        base_dir: Diretório base do projeto (opcional)
        
    Returns:
        Tupla com os caminhos para os arquivos Excel gerados (completo, simplificado)
    """
    # Definir caminhos
    if base_dir is None:
        base_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    else:
        base_dir = Path(base_dir)
    
    base_path = base_dir / ".data/OUTPUTS/raw_responses"
    yaml_path = base_dir / "Config/research_questions.yaml"
    json_path = base_dir / ".data/OUTPUTS/select_bibs.json"
    output_dir = base_dir / ".data/OUTPUTS/processed_responses"
    output_path = output_dir / "combined_responses_full.xlsx"
    simple_output_path = output_dir / "combined_responses_simple.xlsx"
    
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


if __name__ == "__main__":
    process_responses_to_excel()









