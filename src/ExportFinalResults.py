"""
Exporta os RESULTADOS FINAIS do SLR para uma pasta única (cópia), pronta para entrega:
  - PDFs dos artigos SELECIONADOS no final (texto completo) → <pasta>/pdfs/
  - BibTeX final (final_papers.bib) e final_papers.json
  - Relatório final do filtro (final_papers_report.md) e as planilhas de decisão/notas
  - Relatório do pipeline (funil PRISMA): pipeline_report.md/.csv + pipeline_metrics.json
  - LEIA-ME.md com o resumo do que foi exportado

Robusto a OneDrive on-demand: cópia com timeout (arquivos só-na-nuvem que pendurariam são
pulados com aviso, em vez de travar a exportação).
"""
import os
import re
import json
import shutil
import urllib.parse
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv(os.path.abspath(".conf"))

from src.PipelineReport import generate_report


def _base() -> str:
    return os.path.abspath(os.getenv("PATH_DATA", ".data"))


def _j(rel: str) -> str:
    return os.path.join(_base(), rel)


def _sanitize(doi: str) -> str:
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    return urllib.parse.quote(doi, safe="")


def _run_with_timeout(fn, timeout: float):
    """Roda fn() numa thread DAEMON com timeout REAL — protege contra leituras só-na-nuvem
    (OneDrive). Usa thread daemon + join(timeout); NÃO usa ThreadPoolExecutor com 'with'
    (que faria shutdown(wait=True) e bloquearia esperando a thread travada, anulando o
    timeout). Em timeout, a thread é abandonada (daemon → morre no fim do processo)."""
    import threading
    box = {}

    def _runner():
        try:
            box["value"] = fn()
        except Exception:
            box["value"] = None

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None  # timeout: não espera a thread (que pode estar travada na leitura)
    return box.get("value")


def _copy_guarded(src: str, dst: str, timeout: float = 40.0) -> bool:
    """Cópia binária com timeout. Lê tudo numa thread; só grava se a leitura concluiu
    (evita arquivo parcial e não pendura em arquivo só-na-nuvem)."""
    if not src or not os.path.exists(src):
        return False

    def _read():
        with open(src, "rb") as f:
            return f.read()

    data = _run_with_timeout(_read, timeout)
    if data is None:
        return False
    try:
        with open(dst, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


def _selected_dois(final_json: str, final_bib: str) -> List[str]:
    """DOIs dos selecionados — do final_papers.json (campo doi) ou, em fallback, do .bib."""
    dois: List[str] = []
    if os.path.exists(final_json):
        try:
            with open(final_json, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for r in data:
                    if isinstance(r, dict):
                        d = (r.get("doi") or r.get("DOI") or "").strip()
                        if d:
                            dois.append(d)
        except Exception:
            pass
    if not dois and os.path.exists(final_bib):
        try:
            with open(final_bib, encoding="utf-8", errors="ignore") as f:
                txt = f.read()
            dois = [m.group(1).strip()
                    for m in re.finditer(r'(?i)doi\s*=\s*[{"]([^}"]+)[}"]', txt)]
        except Exception:
            pass
    # de-dup preservando ordem
    seen, out = set(), []
    for d in dois:
        k = d.lower()
        if k not in seen:
            seen.add(k)
            out.append(d)
    return out


def export_final_results(dest: Optional[str] = None) -> Optional[str]:
    """
    Monta a pasta de entrega com os resultados finais. Gera antes o pipeline-report
    (para incluí-lo atualizado). Retorna o caminho da pasta, ou None se não há final.
    """
    print("\n" + "=" * 70)
    print("=== EXPORTAR RESULTADOS FINAIS ===")
    print("=" * 70 + "\n")

    final_json = _j(os.getenv("FINAL_PAPERS_OUTPUT", "OUTPUTS/processed_responses/final_papers.json"))
    final_bib = _j(os.getenv("FINAL_PAPERS_BIBs_OUTPUT", "OUTPUTS/final_papers.bib"))
    pdfs_dir = _j(os.getenv("FOLDER_SAVE_PDF", "PDFs"))

    if not os.path.exists(final_json) and not os.path.exists(final_bib):
        print("✗ Resultados finais não encontrados (final_papers.json / final_papers.bib).")
        print("  → rode a triagem final antes: python aneta.py --select_fulltext")
        return None

    dest = dest or _j(os.getenv("FINAL_RESULTS_FOLDER", "OUTPUTS/final_results"))
    pdfs_dest = os.path.join(dest, "pdfs")
    # Idempotência: limpa a pasta de entrega antes, para não deixar PDFs/artefatos órfãos
    # de uma execução anterior (ex.: se a seleção final diminuiu entre rodadas).
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(pdfs_dest, exist_ok=True)

    # 1) Gera o pipeline-report atualizado (para entrar na pasta).
    print("[1/3] Gerando o relatório do pipeline (funil)...")
    try:
        generate_report()
    except Exception as e:
        print(f"  (aviso: falha ao gerar o pipeline-report: {e})")

    # 2) Copia os artefatos finais (relatórios, bib, planilhas).
    print("\n[2/3] Copiando relatórios, BibTeX e planilhas...")
    artifacts = [
        final_bib,
        final_json,
        _j("OUTPUTS/processed_responses/final_papers_report.md"),
        _j(os.getenv("FINAL_EXCLUDED_PAPERS_OUTPUT",
                     "OUTPUTS/processed_responses/final_excluded_papers.json")),
        _j(os.getenv("SELECTION_DECISIONS_FULLTEXT_EXCEL_OUTPUT",
                     "OUTPUTS/processed_responses/selection_decisions_fulltext.xlsx")),
        _j("OUTPUTS/processed_responses/combined_responses_fulltext_consolidated.xlsx"),
        _j("OUTPUTS/pipeline_report.md"),
        _j("OUTPUTS/pipeline_funnel.csv"),
        _j("OUTPUTS/pipeline_metrics.json"),
    ]
    copied_artifacts = []
    for src in artifacts:
        if os.path.exists(src):
            dst = os.path.join(dest, os.path.basename(src))
            if _copy_guarded(src, dst, timeout=30.0):
                copied_artifacts.append(os.path.basename(src))
            else:
                print(f"  (aviso: não foi possível copiar {os.path.basename(src)})")
    print(f"  ✓ {len(copied_artifacts)} arquivo(s) copiado(s).")

    # 3) Copia os PDFs dos selecionados.
    print("\n[3/3] Copiando os PDFs dos artigos selecionados...")
    dois = _selected_dois(final_json, final_bib)
    have, missing = [], []
    for doi in dois:
        src = os.path.join(pdfs_dir, _sanitize(doi) + ".pdf")
        dst = os.path.join(pdfs_dest, _sanitize(doi) + ".pdf")
        if _copy_guarded(src, dst, timeout=40.0):
            have.append(doi)
        else:
            missing.append(doi)
    print(f"  ✓ {len(have)}/{len(dois)} PDFs copiados" +
          (f" · {len(missing)} ausentes/indisponíveis" if missing else ""))

    # 4) Copia os artefatos de bibliometria (se existirem).
    biblio_src = _j("OUTPUTS/BIBLIOMETRY")
    biblio_dest = os.path.join(dest, "bibliometry")
    biblio_copied = 0
    if os.path.exists(biblio_src):
        os.makedirs(biblio_dest, exist_ok=True)
        for root, dirs, files in os.walk(biblio_src):
            rel_dir = os.path.relpath(root, biblio_src)
            target_dir = os.path.join(biblio_dest, rel_dir) if rel_dir != "." else biblio_dest
            os.makedirs(target_dir, exist_ok=True)
            for file in files:
                s_file = os.path.join(root, file)
                d_file = os.path.join(target_dir, file)
                if _copy_guarded(s_file, d_file, timeout=20.0):
                    biblio_copied += 1
        openalex_meta = _j("OUTPUTS/openalex_metadata.json")
        if os.path.exists(openalex_meta):
            _copy_guarded(openalex_meta, os.path.join(biblio_dest, "openalex_metadata.json"), timeout=20.0)
            biblio_copied += 1
        print(f"  ✓ {biblio_copied} arquivo(s) de bibliometria copiados para bibliometry/")

    # LEIA-ME com o resumo da entrega.
    readme = [
        "# Resultados finais do SLR (Aneta)", "",
        f"Exportado em: {datetime.now().isoformat(timespec='seconds')}", "",
        f"- Artigos selecionados (final): **{len(dois)}**",
        f"- PDFs copiados: **{len(have)}** (em `pdfs/`)" +
        (f" · ausentes: {len(missing)}" if missing else ""),
        "", "## Conteúdo desta pasta", "",
        "- `final_papers.bib` — BibTeX dos artigos selecionados no final",
        "- `final_papers.json` / `final_excluded_papers.json` — incluídos / excluídos",
        "- `final_papers_report.md` — relatório do filtro final (decisão por artigo)",
        "- `selection_decisions_fulltext.xlsx` — planilha de decisão (selecionados/rejeitados/motivo)",
        "- `combined_responses_fulltext_consolidated.xlsx` — planilha de notas por critério",
        "- `pipeline_report.md` / `pipeline_funnel.csv` / `pipeline_metrics.json` — funil do pipeline",
        "- `pdfs/` — PDFs dos artigos selecionados",
    ]
    if os.path.exists(biblio_src):
        readme.append("- `bibliometry/` — Relatórios, gráficos e rankings da análise bibliométrica")
    if missing:
        readme += ["", "## PDFs ausentes/indisponíveis", ""]
        readme += [f"- {d}" for d in missing]
    with open(os.path.join(dest, "LEIA-ME.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(readme))

    print("\n" + "=" * 70)
    print(f"✓ EXPORTAÇÃO CONCLUÍDA: {dest}")
    print(f"  - {len(dois)} selecionados · {len(have)} PDFs · {len(copied_artifacts)} relatórios/planilhas")
    print("=" * 70)
    return dest
