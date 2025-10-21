"""
Ferramenta de linha de comando para padronizar nomes de PDFs baseados em DOI.

Lê todos os arquivos PDF de uma pasta de origem, converte o nome do arquivo
para o mesmo formato utilizado em `src/DonwloadPapers.py` e copia os arquivos
para a pasta de destino. Caso o arquivo já exista na pasta de destino, ele é
sobrescrito.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from urllib.parse import quote


# Ajuste os caminhos padrão conforme necessário para o seu ambiente.
DEFAULT_PDF_PATH_SOURCE = Path(".data/PDFs/manual")
DEFAULT_PDF_PATH_TARGET = Path(".data/PDFs")


def sanitize_doi_filename(doi: str) -> str:
    """
    Replica a lógica de `sanitize_filename` em `src/DonwloadPapers.py`.

    Remove o prefixo padrão de DOI e codifica caracteres não permitidos para
    nomes de arquivos usando percent-encoding.
    """
    normalized = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    return quote(normalized, safe="")


def copy_and_standardize_pdfs(pdf_path_source: Path, pdf_path_target: Path) -> int:
    """
    Copia PDFs da pasta de origem para a pasta de destino utilizando nomes
    padronizados.

    Args:
        pdf_path_source: Pasta onde os PDFs estão originalmente.
        pdf_path_target: Pasta final onde os PDFs renomeados serão salvos.

    Returns:
        Quantidade de arquivos copiados.
    """
    if not pdf_path_source.exists() or not pdf_path_source.is_dir():
        raise ValueError(f"Pasta de origem inválida: {pdf_path_source}")

    pdf_path_target.mkdir(parents=True, exist_ok=True)

    copied = 0
    for pdf_file in sorted(pdf_path_source.iterdir()):
        if not pdf_file.is_file() or pdf_file.suffix.lower() != ".pdf":
            continue

        doi_name = pdf_file.stem
        sanitized_name = sanitize_doi_filename(doi_name)

        if not sanitized_name:
            print(f"Aviso: arquivo ignorado por DOI inválido -> {pdf_file.name}")
            continue

        target_file = pdf_path_target / f"{sanitized_name}.pdf"

        # copy2 mantém metadados básicos (data de modificação, por exemplo)
        shutil.copy2(pdf_file, target_file)
        copied += 1
        print(f"{pdf_file.name} -> {target_file.name}")

    if copied == 0:
        print("Nenhum arquivo PDF encontrado para processar.")
    else:
        print(f"Total de arquivos processados: {copied}")

    return copied


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Padroniza nomes de PDFs (DOI) e copia arquivos para outra pasta."
    )
    parser.add_argument(
        "pdf_path_source",
        nargs="?",
        type=Path,
        default=None,
        help="Pasta de origem contendo PDFs nomeados por DOI",
    )
    parser.add_argument(
        "pdf_path_target",
        nargs="?",
        type=Path,
        default=None,
        help="Pasta de destino para salvar os PDFs padronizados",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.pdf_path_source or DEFAULT_PDF_PATH_SOURCE
    target = args.pdf_path_target or DEFAULT_PDF_PATH_TARGET
    copy_and_standardize_pdfs(source, target)


if __name__ == "__main__":
    main()
