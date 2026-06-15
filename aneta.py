import __init__
import os
import sys
import argparse
import asyncio
import warnings
from dotenv import load_dotenv

# Suppress SyntaxWarning from third-party libraries (scholarly)
warnings.filterwarnings("ignore", category=SyntaxWarning)

from src.Search import run_search as search_run
from src.EnrichBibtex import enrich_bibtex as enrich_bibtex_sync
from src.EnrichBibtexAsync import enrich_bibtex as enrich_bibtex_async
from src.Selection import get_analyse
from src.Bibliometry import run_bibliometry as run_bibliometry_func
from src.BibliometryAsync import run_bibliometry as run_bibliometry_async_func
from src.DonwloadPapers import download_all_papers

from src.GenerativeAI.LLMSelectPapersByAbstract import run_select_bibs_filtered_by_abstract
from src.GenerativeAI.LLMSelectPapersByAbstractOneOnOne import run_select_bibs_filtered_by_abstract as run_select_bibs_filtered_by_abstract_one_on_one
from src.GenerativeAI.LLMSelectPapersByAbstractOneOnOneAsync import run_select_bibs_filtered_by_abstract as run_select_bibs_filtered_by_abstract_async
from src.GenerativeAI.LLMUtils import bibtex_to_json_schema
from src.GenerativeAI.LLMUtilExcel import process_responses_to_excel
from src.PDFReader import process_pdfs, read_pdfs_with_docling

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

def run_download(skip_validation=False):
    bib_file = os.getenv("BIB_FILE_DOWNLOAD_PDF", ".OUTPUTS/select_bibs.bib")
    folder_save_pdf = os.getenv("FOLDER_SAVE_PDF", "PDFs")
    
    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")
    
    path_directory_file_bib = path_data.replace(".bibs", bib_file)
    folder_save_pdf = path_data.replace(".bibs", folder_save_pdf)
    
    if skip_validation:
        print("\n⚠️  MODO DE DOWNLOAD RÁPIDO ATIVADO")
        print("Validações de PDF desabilitadas - arquivos serão salvos sem verificação de integridade\n")
    
    download_all_papers(path_directory_file_bib, folder_save_pdf, skip_validation=skip_validation)
    return True

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

def run_process_responses_to_excel():
    """
    Processes LLM responses into Excel files for analysis.
    
    Returns:
        bool: True if the operation was completed successfully
    """
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
    
    Filters LLM response JSON using DuckDB with configurable SQL WHERE clause,
    then matches filtered records to BibTeX entries and generates outputs.
    
    Returns:
        bool: True if the operation was completed successfully, False otherwise
    """
    from src.FilterRelevantPapers import filter_relevant_papers
    return filter_relevant_papers()

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
    group.add_argument('--download_pdf', action='store_true', help='Executa o download dos papers')
    group.add_argument('--download_pdf_fast', action='store_true', help='Executa o download dos papers SEM validação (mais rápido, menos seguro)')
    group.add_argument('--deprecated_abstract', action='store_true', help='Executa a leitura do abstract para ACM ou Spring via Web Scraping (Depreciado)')
    group.add_argument('--abstract_classifier_llm', action='store_true', help='Realiza a classificação de abstracts usando LLM')
    group.add_argument('--abstract_classifier_llm_one_on_one', action='store_true', help='Realiza a classificação de abstracts usando LLM (modo One-on-One)')
    group.add_argument('--abstract_classifier_llm_one_on_one_async', action='store_true', help='Realiza a classificação de abstracts usando LLM de forma assíncrona (modo One-on-One)')
    group.add_argument('--bibtex_to_json', action='store_true', help='Converte arquivo BibTeX para formato JSON com schema específico')
    group.add_argument('--process_responses', action='store_true', help='Processa respostas LLM para arquivos Excel')
    group.add_argument('--filter_relevant_papers', action='store_true', help='Filtra papers relevantes das respostas LLM usando critérios SQL configuráveis')
    group.add_argument('--read_pdfs', action='store_true', help='Parse PDF documents using Docling and optionally generate Markdown files')

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
    elif args.read_pdfs:
        run_pdf_reader()
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




