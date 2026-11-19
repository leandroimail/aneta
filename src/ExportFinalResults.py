"""
Exporta os RESULTADOS FINAIS do SLR para uma pasta única (cópia), pronta para entrega:
  - PDFs dos artigos SELECIONADOS no final (texto completo) → <pasta>/pdfs/
  - BibTeX final (final_papers.bib) e final_papers.json
  - Relatório final do filtro (final_papers_report.md) e as planilhas de decisão/notas
  - Relatório do pipeline (funil PRISMA): pipeline_report.md/.csv + pipeline_metrics.json
  - LEIA-ME.md com o resumo do que foi exportado

Uma falha de leitura ou cópia preserva a entrega anterior.
"""
from src.CachePaths import doi_filename as _sanitize
import os
import re
import json
import hashlib
from contextlib import contextmanager
from pathlib import Path
import tempfile
from src.PdfCache import clone_or_copy
from src.CachePaths import cache_root
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv(os.path.abspath(".conf"))

from src.PipelineReport import generate_report


def _base() -> str:
    return os.path.abspath(os.getenv("PATH_DATA", ".data"))


def _j(rel: str) -> str:
    return os.path.join(_base(), rel)


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
    """Stage an independent copy under timeout before publishing the destination."""
    if not src or not os.path.exists(src):
        return False

    try:
        with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(dst))) as directory:
            staged = os.path.join(directory, "export")
            def prepare():
                clone_or_copy(src, staged)
                return True
            if not _run_with_timeout(prepare, timeout):
                return False
            os.replace(staged, dst)
            return True
    except OSError:
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


_MANIFEST = ".aneta-export.json"


def _inventory(folder):
    files = {}
    for entry in folder.rglob("*"):
        if entry.is_symlink():
            raise ValueError(f"Entrega contém link simbólico: {entry}")
        if entry.is_dir():
            files[entry.relative_to(folder).as_posix()] = "directory"
        elif entry.name == _MANIFEST and entry.parent == folder:
            continue
        elif entry.is_file():
            def checksum(path=entry):
                with path.open("rb") as stream:
                    return hashlib.file_digest(stream, "sha256").hexdigest()
            digest = _run_with_timeout(checksum, 40)
            if digest is None:
                raise OSError(f"Não foi possível verificar a integridade de {entry}")
            files[entry.relative_to(folder).as_posix()] = digest
        else:
            raise ValueError(f"Entrada desconhecida na entrega: {entry}")
    return files


def _check_destination(folder):
    if folder.is_symlink():
        raise ValueError(f"Destino da entrega é um link: {folder}")
    if not folder.exists() or (folder.is_dir() and not any(folder.iterdir())):
        return
    manifest = folder / _MANIFEST
    readme = folder / "LEIA-ME.md"
    if not manifest.exists() and readme.is_file() and not readme.is_symlink() and (folder / "pdfs").is_dir():
        with readme.open(encoding="utf-8") as stream:
            if stream.readline().strip() == "# Resultados finais do SLR (Aneta)" and (
                (folder / "final_papers.bib").is_file() or (folder / "final_papers.json").is_file()
            ):
                return "legacy"
    if not manifest.is_file() or manifest.is_symlink():
        raise ValueError(f"Destino contém arquivos sem inventário do Aneta: {folder}. Escolha uma pasta vazia.")
    if json.loads(manifest.read_text(encoding="utf-8")) != _inventory(folder):
        raise ValueError(f"O conteúdo da entrega foi alterado: {folder}. Escolha uma pasta vazia.")


@contextmanager
def _publish_lock(folder):
    """Serialize the short destination check/swap across concurrent Aneta exports."""
    lockfile = folder.parent / ("." + folder.name + ".aneta-export.lock")
    with lockfile.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def export_final_results(dest: Optional[str] = None) -> Optional[str]:
    """Prepare and verify the delivery before replacing a previous managed export."""
    folder = Path(dest or _j(os.getenv("FINAL_RESULTS_FOLDER", "OUTPUTS/final_results"))).absolute()
    resolved = folder.resolve()
    protected = [
        Path.cwd(), Path(_base()), Path(_j("OUTPUTS")), Path(_j("OUTPUTS/processed_responses")),
        Path(_j(os.getenv("FINAL_PAPERS_OUTPUT", "OUTPUTS/processed_responses/final_papers.json"))),
        Path(_j(os.getenv("FINAL_PAPERS_BIBs_OUTPUT", "OUTPUTS/final_papers.bib"))),
    ]
    sources = [Path(_j(os.getenv("FOLDER_SAVE_PDF", "PDFs"))), Path(_j("OUTPUTS/BIBLIOMETRY")),
               cache_root()]
    if any(path.resolve().is_relative_to(resolved) for path in protected + sources) or any(
        resolved.is_relative_to(path.resolve()) for path in sources
    ):
        raise ValueError(f"O destino da entrega se sobrepõe aos dados de origem: {folder}")
    folder.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder.parent, prefix=".aneta-export-") as directory:
        staged = Path(directory) / "new"
        if not _build_delivery(str(staged)):
            return None
        (staged / _MANIFEST).write_text(json.dumps(_inventory(staged), sort_keys=True), encoding="utf-8")
        with _publish_lock(folder):
            previous = Path(directory) / "previous"
            if _check_destination(folder) == "legacy":
                backup = Path(tempfile.mkdtemp(prefix=folder.name + "-legacy-", dir=folder.parent))
                previous = backup / folder.name
                print(f"Entrega legada preservada em {previous}")
            if folder.exists():
                folder.rename(previous)
            try:
                staged.rename(folder)
            except BaseException:
                if previous.exists() and not folder.exists():
                    previous.rename(folder)
                raise
    print(f"Entrega disponível em {folder}")
    return str(folder)


def _build_delivery(dest: str) -> Optional[str]:
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

    pdfs_dest = os.path.join(dest, "pdfs")
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
                raise OSError(f"Falha ao copiar {src}; entrega anterior preservada.")
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
        elif os.path.exists(src):
            raise OSError(f"Falha ao copiar {src}; entrega anterior preservada.")
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
                if not _copy_guarded(s_file, d_file, timeout=20.0):
                    raise OSError(f"Falha ao copiar {s_file}; entrega anterior preservada.")
                biblio_copied += 1
    metadata = Path(_j("OUTPUTS"))
    final_meta = metadata / "openalex_metadata_final.json"
    abstract_meta = metadata / "openalex_metadata_post_abstract.json"
    alias = "openalex_metadata.json"
    sources = [(final_meta, final_meta.name), (abstract_meta, abstract_meta.name)]
    if final_meta.is_file():
        sources.append((final_meta, alias))
    elif not abstract_meta.is_file():
        sources.append((metadata / alias, alias))
    for source, name in sources:
        if source.is_file():
            os.makedirs(biblio_dest, exist_ok=True)
            if not _copy_guarded(str(source), os.path.join(biblio_dest, name), timeout=20.0):
                raise OSError(f"Falha ao copiar {source}. Entrega anterior preservada.")
            biblio_copied += 1
    if biblio_copied:
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
