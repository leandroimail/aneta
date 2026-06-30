import __init__
import os
import sys
import argparse
import asyncio
import warnings
from dotenv import load_dotenv

# Suppress SyntaxWarning from third-party libraries (scholarly)
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Saída SEM BUFFER (line-buffered): o PYTHONUNBUFFERED em env só vale antes do processo
# iniciar, então reconfiguramos stdout/stderr aqui para o progresso aparecer em tempo real
# mesmo quando a saída é redirecionada para arquivo/pipe (ex.: rodando em background).
os.environ.setdefault("PYTHONUNBUFFERED", "1")  # afeta subprocessos lançados pelo Aneta
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except (AttributeError, ValueError):
    pass

from src.Search import run_search as search_run
from src.EnrichBibtex import enrich_bibtex as enrich_bibtex_sync
from src.EnrichBibtexAsync import enrich_bibtex as enrich_bibtex_async
from src.Selection import get_analyse
from src.Bibliometry import run_bibliometry as run_bibliometry_func
from src.BibliometryAsync import run_bibliometry as run_bibliometry_async_func
from src.DonwloadPapers import download_all_papers, download_assisted
from src.PipelineReport import record_stage_auto, generate_report

from src.GenerativeAI.LLMSelectPapersByAbstract import run_select_bibs_filtered_by_abstract
from src.GenerativeAI.LLMSelectPapersByAbstractOneOnOne import run_select_bibs_filtered_by_abstract as run_select_bibs_filtered_by_abstract_one_on_one
from src.GenerativeAI.LLMSelectPapersByAbstractOneOnOneAsync import run_select_bibs_filtered_by_abstract as run_select_bibs_filtered_by_abstract_async
from src.GenerativeAI.LLMUtils import bibtex_to_json_schema
from src.GenerativeAI.LLMUtilExcel import process_responses_to_excel
from src.GenerativeAI.LLMSelectPapersByFullTextAsync import run_fulltext_classification
# Obs.: src.PDFReader puxa o docling (stack pesado de ML) e só é usado por --read_pdfs.
# O import é feito de forma lazy dentro de run_pdf_reader() para não exigir docling nos
# demais comandos (busca, enriquecimento, classificação, seleção por abstract).

def setup_environment():
    load_dotenv(os.path.abspath(".conf"))
    load_dotenv(os.path.abspath("config/.env"))
    global PROJECT_PATH
    PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
    os.environ["PROJECT_PATH"] = PROJECT_PATH

def run_search():
    search_run()
    return True

def run_enrich():
    enrich_bibtex_sync()
    return True

def run_enrich_async():
    asyncio.run(enrich_bibtex_async())
    return True

def run_selection():
    get_analyse()
    return True

def run_bibliometry_function():
    run_bibliometry_func()
    return True

def run_bibliometry_async():
    run_bibliometry_async_func()
    return True

def run_download(skip_validation=False, max_workers=None):
    bib_file = os.getenv("BIB_FILE_DOWNLOAD_PDF", ".OUTPUTS/select_bibs.bib")
    folder_save_pdf = os.getenv("FOLDER_SAVE_PDF", "PDFs")

    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")

    path_directory_file_bib = path_data.replace(".bibs", bib_file)
    folder_save_pdf = path_data.replace(".bibs", folder_save_pdf)

    if skip_validation:
        print("\n⚠️  MODO DE DOWNLOAD RÁPIDO ATIVADO")
        print("Validações de PDF desabilitadas - arquivos serão salvos sem verificação de integridade\n")

    download_all_papers(path_directory_file_bib, folder_save_pdf,
                        skip_validation=skip_validation, max_workers=max_workers)
    return True

def run_download_assisted():
    """
    Download ASSISTIDO dos artigos ainda não baixados: abre um navegador visível e pede
    ajuda manual para passar pelo Cloudflare (1x por site). Pergunta no terminal antes de
    iniciar; se você recusar, fica para depois. Interativo — rode no seu terminal.
    """
    bib_file = os.getenv("BIB_FILE_DOWNLOAD_PDF", ".OUTPUTS/select_bibs.bib")
    folder_save_pdf = os.getenv("FOLDER_SAVE_PDF", "PDFs")

    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")

    path_directory_file_bib = path_data.replace(".bibs", bib_file)
    folder_save_pdf = path_data.replace(".bibs", folder_save_pdf)

    return download_assisted(path_directory_file_bib, folder_save_pdf)

def run_download_async(skip_validation=False):
    """
    Download dos PDFs de forma CONCORRENTE (I/O-bound -> ThreadPoolExecutor).

    O nível de concorrência vem de DOWNLOAD_MAX_CONCURRENT (default 8). Reaproveita toda
    a lógica de fontes (url -> DOI direto -> Crossref -> Unpaywall) e pula PDFs já baixados.
    """
    try:
        workers = int(os.getenv("DOWNLOAD_MAX_CONCURRENT", "8"))
    except (TypeError, ValueError):
        workers = 8
    workers = max(2, workers)
    print(f"\n⚡ DOWNLOAD CONCORRENTE — {workers} downloads simultâneos\n")
    return run_download(skip_validation=skip_validation, max_workers=workers)

def deprecated_abstract():
    if not os.getenv("RUN_DEPRECATED_JOBS", 0):
        print("A variável de ambiente RUN_DEPRECATED_JOBS não foi definida como 1")
        print("Por favor, defina a variável de ambiente RUN_DEPRECATED_JOBS=1 para rodar a função de leitura do abstract")
        return False
    if not os.getenv("PATH_SPRINGER") and not os.getenv("PATH_ACM"):
        print("A variável de ambiente PATH_SPRINGER ou PATH_ACM não foi definida")
        print("Por favor, defina a variável de ambiente PATH_SPRINGER ou PATH_ACM para rodar a função de leitura do abstract")
        return False
        
    from src.Deprecated.Abstract import get_abstract
    from src.Config import path_SPRINGER, path_ACM
    if path_SPRINGER:
        get_abstract(path_SPRINGER, "SPRINGER")
    if path_ACM:
        get_abstract(path_ACM, "ACM")
    return True

def run_abstract_classifier_llm(selected=None):
    bib_file = os.getenv("BIB_FILE", ".OUTPUTS/select_bibs.bib")

    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")

    path_directory_file_bib = path_data.replace(".bibs", bib_file)

    # Chamando a função com um caminho único de arquivo BibTeX
    run_select_bibs_filtered_by_abstract(path_directory_file_bib, selected=selected)
    return True

def run_abstract_classifier_llm_one_on_one(selected=None):
    bib_file = os.getenv("BIB_FILE", ".OUTPUTS/select_bibs.bib")

    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")

    path_directory_file_bib = path_data.replace(".bibs", bib_file)

    # Chamando a função one-on-one com um caminho único de arquivo BibTeX
    run_select_bibs_filtered_by_abstract_one_on_one(path_directory_file_bib, selected=selected)
    return True

def run_abstract_classifier_llm_one_on_one_async(selected=None):
    """
    Executa a classificação de abstracts usando LLM de forma assíncrona (modo One-on-One).

    Args:
        selected: se informado, roda apenas o(s) LLM(s) cujo id/name/model casar
            (ex.: "gpt-5.4-nano"). None => roda todos os LLMs configurados.

    Returns:
        bool: True se a operação foi concluída com sucesso
    """
    bib_file = os.getenv("BIB_FILE", ".OUTPUTS/select_bibs.bib")

    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")

    path_directory_file_bib = path_data.replace(".bibs", bib_file)

    # Chamando a função assíncrona com asyncio.run
    asyncio.run(run_select_bibs_filtered_by_abstract_async(path_directory_file_bib, selected=selected))
    return True

def run_bibtex_to_json_schema():
    """
    Executa a conversão de um arquivo BibTeX para o formato JSON seguindo um schema específico.
    
    Returns:
        bool: True se a operação foi concluída com sucesso
    """
    bib_file = os.getenv("BIB_FILE", ".OUTPUTS/select_bibs.bib")
    
    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")
    
    path_directory_file_bib = path_data.replace(".bibs", bib_file)
    
    # Define o caminho de saída para o arquivo JSON
    output_dir = os.path.join(os.path.dirname(path_data), "OUTPUTS")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "select_bibs.json")
    
    # Chamando a função de conversão com os caminhos configurados
    bibtex_to_json_schema(path_directory_file_bib, output_path)
    return True

def _raw_responses_dir():
    """Caminho dos resultados brutos da classificação por abstract (.data/OUTPUTS/raw_responses)."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, ".data", "OUTPUTS", "raw_responses")

def _has_raw_responses(raw_dir):
    """True se houver pelo menos um arquivo response_*_raw.txt em qualquer subpasta de LLM."""
    if not os.path.isdir(raw_dir):
        return False
    for _root, _dirs, files in os.walk(raw_dir):
        if any(f.startswith("response_") and f.endswith("_raw.txt") for f in files):
            return True
    return False

def run_process_responses_to_excel():
    """
    Processes LLM responses into Excel files for analysis.

    Etapa "planilha" do pipeline de seleção: lê os resultados brutos da classificação
    por abstract e gera as planilhas de notas (incluindo a consolidada que alimenta o
    filtro). Valida que existem respostas antes de prosseguir.

    Returns:
        bool: True if the operation was completed successfully, False caso não haja
              respostas para processar.
    """
    raw_dir = _raw_responses_dir()
    if not _has_raw_responses(raw_dir):
        print("✗ Nenhuma resposta de LLM encontrada em:")
        print(f"  {raw_dir}")
        print("  → Rode a classificação por abstract antes, por exemplo:")
        print("    python aneta.py --abstract_classifier_llm_one_on_one_async")
        return False

    # Call the process_responses_to_excel function
    full_path, simple_path, consolidated_path = process_responses_to_excel()

    print(f"Excel files created successfully:")
    print(f"- Full Excel file: {full_path}")
    print(f"- Simple Excel file: {simple_path}")
    print(f"- Consolidated Excel file: {consolidated_path}")
    return True

def run_filter_relevant_papers():
    """
    Execute filtering of LLM-classified papers using SQL criteria.

    Etapa "filtro" do pipeline de seleção: lê a planilha consolidada de notas, aplica o
    filtro SQL (config/filter_accept_results_llm.yaml) e grava a planilha de decisão
    (selection_decisions.xlsx) com a motivação por artigo, além de relevant/unrelevant
    JSON, BibTeX e relatório. Valida que a planilha consolidada existe.

    Returns:
        bool: True if the operation was completed successfully, False otherwise
    """
    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    consolidated_rel = os.getenv(
        "FILTER_LLM_RESPONSES_ABSTRACT_PATH",
        "OUTPUTS/processed_responses/combined_responses_consolidated.json",
    )
    consolidated_path = os.path.join(path_data, consolidated_rel)
    if not os.path.exists(consolidated_path):
        print("✗ Planilha consolidada de notas não encontrada em:")
        print(f"  {consolidated_path}")
        print("  → Rode a etapa de planilha antes:")
        print("    python aneta.py --process_responses")
        return False

    from src.FilterRelevantPapers import filter_relevant_papers
    return filter_relevant_papers()

def run_select_abstracts():
    """
    Atalho do pipeline de seleção por abstract: planilha → filtro, em sequência.

    Roda --process_responses (gera as planilhas de notas) e, em seguida,
    --filter_relevant_papers (gera a planilha de decisão com a motivação por artigo).
    NÃO inclui a classificação por LLM (etapa cara), que deve ser rodada antes.

    Returns:
        bool: True se ambas as etapas concluíram com sucesso, False caso contrário.
    """
    print("\n" + "=" * 70)
    print("=== SELEÇÃO POR ABSTRACT: PLANILHA → FILTRO ===")
    print("=" * 70)

    print("\n[Etapa 1/2] Gerando planilhas de notas (--process_responses)...")
    if not run_process_responses_to_excel():
        print("\n✗ Pipeline interrompido: falha ao gerar as planilhas de notas.")
        return False

    print("\n[Etapa 2/2] Filtrando e gerando a planilha de decisão (--filter_relevant_papers)...")
    if not run_filter_relevant_papers():
        print("\n✗ Pipeline interrompido: falha na filtragem.")
        return False

    print("\n✓ Seleção por abstract concluída (planilhas + decisão geradas).")
    return True

def run_pdf_reader():
    """
    Execute PDF reading using new async process_pdfs() function.
    
    Processes PDFs from configured folders using async batch processing with
    concurrency control. Returns structured data in memory without creating
    markdown files.
    
    Returns:
        bool: True if the operation was completed successfully, False otherwise
    """
    try:
        # Import lazy: só carrega o docling quando o leitor de PDF é realmente usado.
        from src.PDFReader import process_pdfs

        # Log start
        print("=" * 80)
        print("PDF READER - Async Batch Processing")
        print("=" * 80)

        # Call the new process_pdfs() orchestrator
        # This will read configuration from .conf automatically
        results = process_pdfs()
        
        # Extract results
        pre_results = results.get("pre", [])
        post_results = results.get("post", [])
        
        # Calculate statistics
        total_pdfs = len(pre_results) + len(post_results)
        successful_pre = sum(1 for r in pre_results if r.get("success", False))
        successful_post = sum(1 for r in post_results if r.get("success", False))
        total_successful = successful_pre + successful_post
        
        failed_pre = len(pre_results) - successful_pre
        failed_post = len(post_results) - successful_post
        total_failed = failed_pre + failed_post
        
        # Log summary
        print("\n" + "=" * 80)
        print("PROCESSING SUMMARY")
        print("=" * 80)
        print(f"Total PDFs processed: {total_pdfs}")
        print(f"  - Pre-selection: {len(pre_results)} PDFs ({successful_pre} successful, {failed_pre} failed)")
        print(f"  - Post-selection: {len(post_results)} PDFs ({successful_post} successful, {failed_post} failed)")
        print(f"\nOverall success rate: {total_successful}/{total_pdfs} ({100*total_successful//total_pdfs if total_pdfs > 0 else 0}%)")
        
        # Log failures if any
        if total_failed > 0:
            print(f"\n⚠️  Warning: {total_failed} PDFs failed to process")
            print("\nFailed PDFs:")
            for result in pre_results + post_results:
                if not result.get("success", False):
                    print(f"  - {result.get('filename', 'unknown')}: {result.get('error', 'Unknown error')}")
        
        # Determine success
        success = total_successful > 0
        
        if success:
            print("\n✅ PDF processing completed successfully!")
        else:
            print("\n❌ PDF processing failed for all PDFs.")
        
        print("=" * 80)
        
        return success
        
    except ValueError as e:
        # Configuration or validation errors
        print(f"\n❌ Configuration Error: {str(e)}")
        print("Please check your .conf file settings.")
        return False
        
    except FileNotFoundError as e:
        # Base path or folder not found
        print(f"\n❌ File Not Found Error: {str(e)}")
        print("Please ensure the configured paths exist.")
        return False
        
    except RuntimeError as e:
        # All PDFs failed to process
        print(f"\n❌ Processing Error: {str(e)}")
        print("All PDFs failed to process. Check logs for details.")
        return False
        
    except Exception as e:
        # Unexpected errors
        print(f"\n❌ Unexpected Error: {str(e)}")
        import traceback
        print("\nTraceback:")
        print(traceback.format_exc())
        return False

def run_fulltext_classifier_async(selected=None):
    """
    Classificação por TEXTO COMPLETO (full-text screening), multi-LLM assíncrona.
    Lê os aprovados no abstract (relevant_abstract_papers.bib), extrai o texto dos PDFs
    e classifica com o grupo FULL_TEXT.
    """
    bib_file = os.getenv("RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT", "OUTPUTS/relevant_abstract_papers.bib")
    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")
    bib_path = path_data.replace(".bibs", bib_file)
    if not os.path.exists(bib_path):
        print("✗ BibTeX dos aprovados no abstract não encontrado:")
        print(f"  {bib_path}")
        print("  → rode a triagem por abstract antes: python aneta.py --select_abstracts")
        return False
    asyncio.run(run_fulltext_classification(bib_path, selected=selected))
    return True

def run_process_responses_fulltext():
    """Consolida as respostas de full-text (raw_responses_fulltext) numa planilha de notas."""
    raw_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           ".data", "OUTPUTS", "raw_responses_fulltext")
    if not _has_raw_responses(raw_dir):
        print("✗ Nenhuma resposta de full-text encontrada em:")
        print(f"  {raw_dir}")
        print("  → rode a classificação antes: python aneta.py --fulltext_classifier_llm_async")
        return False
    full_path, simple_path, consolidated_path = process_responses_to_excel(
        raw_subdir="raw_responses_fulltext",
        article_info="select_bibs_fulltext.json",
        out_prefix="combined_responses_fulltext",
    )
    print("Planilhas full-text criadas:")
    print(f"- Consolidada: {consolidated_path}")
    return True

def run_filter_final_papers():
    """Filtro FINAL (texto completo) → final_papers.* + selection_decisions_fulltext.xlsx."""
    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    cons_rel = os.getenv("FILTER_LLM_RESPONSES_FULLTEXT_PATH",
                         "OUTPUTS/processed_responses/combined_responses_fulltext_consolidated.json")
    cons_path = os.path.join(path_data, cons_rel)
    if not os.path.exists(cons_path):
        print("✗ Consolidado de full-text não encontrado:")
        print(f"  {cons_path}")
        print("  → rode a etapa de planilha antes: python aneta.py --process_responses_fulltext")
        return False
    from src.FilterRelevantPapers import filter_final_papers
    return filter_final_papers()

def run_select_fulltext():
    """Atalho da triagem final: consolida (full-text) → filtra. NÃO inclui a classificação LLM."""
    print("\n" + "=" * 70)
    print("=== TRIAGEM FINAL (TEXTO COMPLETO): CONSOLIDA → FILTRA ===")
    print("=" * 70)
    print("\n[Etapa 1/2] Consolidando respostas de full-text...")
    if not run_process_responses_fulltext():
        print("\n✗ Pipeline interrompido: falha ao consolidar.")
        return False
    print("\n[Etapa 2/2] Aplicando filtro final...")
    if not run_filter_final_papers():
        print("\n✗ Pipeline interrompido: falha na filtragem final.")
        return False
    print("\n✓ Triagem final concluída (final_papers + selection_decisions_fulltext gerados).")
    return True

def run_pipeline_report():
    """
    Gera o relatório consolidado do pipeline (funil completo do SLR): lê o estado incremental
    das etapas e calcula o que faltar a partir dos artefatos. Saídas: pipeline_report.md,
    pipeline_funnel.csv e pipeline_metrics.json em .data/OUTPUTS/.
    """
    generate_report()
    return True

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Executa diferentes funcionalidades do projeto ASRL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Exemplos de uso:
                        python aneta.py --search
                        python aneta.py --enrich
                        python aneta.py --selection
        ''')
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--search', action='store_true', help='Executa a busca no banco de dados acadêmicos')
    group.add_argument('--enrich', action='store_true', help='Executa o enriquecimento dos bibtex')
    group.add_argument('--enrich_async', action='store_true', help='Executa o enriquecimento dos bibtex de forma assíncrona')
    group.add_argument('--selection', action='store_true', help='Executa a seleção dos bibtex')
    group.add_argument('--bibliometry', action='store_true', help='Executa a bibliometria completa do bibtex selecionado')
    group.add_argument('--bibliometry_async', action='store_true', help='Executa de forma assíncrona a bibliometria completa do bibtex selecionado')
    group.add_argument('--download_pdf', action='store_true', help='Executa o download dos papers (sequencial)')
    group.add_argument('--download_pdf_async', action='store_true', help='Executa o download dos papers de forma CONCORRENTE (mais rápido; DOWNLOAD_MAX_CONCURRENT, default 8)')
    group.add_argument('--download_pdf_assisted', action='store_true', help='Download ASSISTIDO dos faltantes: navegador visível + você resolve o Cloudflare na mão (pergunta antes de iniciar)')
    group.add_argument('--download_pdf_fast', action='store_true', help='Executa o download dos papers SEM validação (mais rápido, menos seguro)')
    group.add_argument('--deprecated_abstract', action='store_true', help='Executa a leitura do abstract para ACM ou Spring via Web Scraping (Depreciado)')
    group.add_argument('--abstract_classifier_llm', action='store_true', help='Realiza a classificação de abstracts usando LLM')
    group.add_argument('--abstract_classifier_llm_one_on_one', action='store_true', help='Realiza a classificação de abstracts usando LLM (modo One-on-One)')
    group.add_argument('--abstract_classifier_llm_one_on_one_async', action='store_true', help='Realiza a classificação de abstracts usando LLM de forma assíncrona (modo One-on-One)')
    group.add_argument('--bibtex_to_json', action='store_true', help='Converte arquivo BibTeX para formato JSON com schema específico')
    group.add_argument('--process_responses', action='store_true', help='[Seleção 1/2] Processa respostas LLM e gera as planilhas de notas (consolidada)')
    group.add_argument('--filter_relevant_papers', action='store_true', help='[Seleção 2/2] Aplica o filtro SQL e gera a planilha de decisão (selection_decisions.xlsx) com a motivação por artigo')
    group.add_argument('--select_abstracts', action='store_true', help='[Seleção] Atalho: roda --process_responses e depois --filter_relevant_papers em sequência (sem a classificação LLM)')
    group.add_argument('--fulltext_classifier_llm', action='store_true', help='[Full-text] Classifica os papers pelo TEXTO COMPLETO usando LLM (grupo FULL_TEXT)')
    group.add_argument('--fulltext_classifier_llm_async', action='store_true', help='[Full-text] Classificação por texto completo, multi-LLM assíncrona (grupo FULL_TEXT)')
    group.add_argument('--process_responses_fulltext', action='store_true', help='[Full-text] Consolida as respostas de texto completo numa planilha de notas')
    group.add_argument('--filter_final_papers', action='store_true', help='[Full-text] Filtro FINAL: gera final_papers + selection_decisions_fulltext.xlsx')
    group.add_argument('--select_fulltext', action='store_true', help='[Full-text] Atalho: --process_responses_fulltext + --filter_final_papers em sequência')
    group.add_argument('--read_pdfs', action='store_true', help='Parse PDF documents using Docling and optionally generate Markdown files')
    group.add_argument('--pipeline_report', action='store_true', help='Gera o relatório consolidado do pipeline (funil do SLR): pipeline_report.md + pipeline_funnel.csv + pipeline_metrics.json')

    # Opção (fora do grupo mutuamente exclusivo): seleciona UM LLM específico para a
    # classificação de abstract, pelo nome do modelo, id ou name do cliente.
    parser.add_argument('--llm', metavar='MODELO_OU_ID', default=None,
                        help='Roda a classificação de abstract usando APENAS o LLM informado '
                             '(nome do modelo, id ou name do cliente; ex.: --llm gpt-5.4-nano). '
                             'Sem esta opção, roda todos os LLMs de LLM_CLIENTS_ABSTRACT.')

    return parser.parse_args(), parser


if __name__ == "__main__":
    ###################  Variáveis de configuração (modo script)
    run_search_database = False
    run_enrich_bibtex = False
    run_enrich_bibtex_async = False
    run_selection_bibtex = False
    run_bibliometry_async_var = False
    run_bibliometry = False
    run_download_papers = False
    run_deprecated_abstract = False
    run_convert_bibtex_to_json = False
    run_abstract_llm = False
    run_abstract_llm_one_on_one = False
    run_abstract_llm_one_on_one_async = False
    run_process_excel = False
    run_filter_relevant_papers_var = False
    run_pdf_reader_var = False  

    setup_environment()
    
    # Verifica se há argumentos de linha de comando
    args, parser = parse_arguments()
    
    # Prioriza argumentos de linha de comando sobre as variáveis do script
    if args.search:
        run_search()
    elif args.enrich:
        run_enrich()
    elif args.enrich_async:
        run_enrich_async()
    elif args.bibliometry_async:
        run_bibliometry_async()
    elif args.selection:
        run_selection()
    elif args.bibliometry:
        run_bibliometry_function()
    elif args.download_pdf:
        run_download()
    elif args.download_pdf_async:
        run_download_async()
    elif args.download_pdf_assisted:
        run_download_assisted()
    elif args.download_pdf_fast:
        run_download(skip_validation=True)
    elif args.deprecated_abstract:
        deprecated_abstract()
    elif args.abstract_classifier_llm:
        run_abstract_classifier_llm(selected=args.llm)
    elif args.abstract_classifier_llm_one_on_one:
        run_abstract_classifier_llm_one_on_one(selected=args.llm)
    elif args.abstract_classifier_llm_one_on_one_async:  # Add new CLI argument handler
        run_abstract_classifier_llm_one_on_one_async(selected=args.llm)
    elif args.bibtex_to_json:
        run_bibtex_to_json_schema()
    elif args.process_responses:  # Add new command line argument handler
        run_process_responses_to_excel()
    elif args.filter_relevant_papers:
        run_filter_relevant_papers()
    elif args.select_abstracts:
        run_select_abstracts()
    elif args.fulltext_classifier_llm:
        run_fulltext_classifier_async(selected=args.llm)
    elif args.fulltext_classifier_llm_async:
        run_fulltext_classifier_async(selected=args.llm)
    elif args.process_responses_fulltext:
        run_process_responses_fulltext()
    elif args.filter_final_papers:
        run_filter_final_papers()
    elif args.select_fulltext:
        run_select_fulltext()
    elif args.read_pdfs:
        run_pdf_reader()
    elif args.pipeline_report:
        run_pipeline_report()
    elif run_search_database:
        run_search()
    elif run_enrich_bibtex:
        run_enrich()
    elif run_enrich_bibtex_async:
        run_enrich_async()
    elif run_bibliometry_async_var:
        run_bibliometry_async()
    elif run_selection_bibtex:
        run_selection()
    elif run_bibliometry:
        run_bibliometry_function()
    elif run_download_papers:
        run_download()
    elif run_deprecated_abstract:
        deprecated_abstract()
    elif run_abstract_llm:
        run_abstract_classifier_llm()
    elif run_abstract_llm_one_on_one:
        run_abstract_classifier_llm_one_on_one()
    elif run_abstract_llm_one_on_one_async:  # Add script mode handler
        run_abstract_classifier_llm_one_on_one_async()
    elif run_convert_bibtex_to_json:
        run_bibtex_to_json_schema()
    elif run_process_excel:  # Add script mode handler for new function
        run_process_responses_to_excel()
    elif run_filter_relevant_papers_var:
        run_filter_relevant_papers()
    elif run_pdf_reader_var:
        run_pdf_reader()
    else:
        parser.print_help()
        sys.exit(1)

    # Registro incremental de métricas da etapa executada (best-effort; nunca quebra o fluxo).
    _STAGE_BY_ARG = {
        "search": "busca",
        "enrich": "enriquecimento", "enrich_async": "enriquecimento",
        "selection": "selecao_metadados",
        "abstract_classifier_llm": "classificacao_llm",
        "abstract_classifier_llm_one_on_one": "classificacao_llm",
        "abstract_classifier_llm_one_on_one_async": "classificacao_llm",
        "process_responses": "consolidacao",
        "filter_relevant_papers": "filtro",
        "download_pdf": "download", "download_pdf_async": "download",
        "download_pdf_assisted": "download", "download_pdf_fast": "download",
        "read_pdfs": "leitura_pdf",
    }
    for _arg, _stage in _STAGE_BY_ARG.items():
        if getattr(args, _arg, False):
            record_stage_auto(_stage)
    if getattr(args, "select_abstracts", False):
        record_stage_auto("consolidacao")
        record_stage_auto("filtro")




