"""
Métricas e relatório do pipeline (Aneta).

Coleta HÍBRIDA INCREMENTAL:
  - Cada etapa, ao terminar, chama record_stage_auto("<etapa>") — que calcula as contagens
    a partir dos artefatos recém-produzidos e grava:
      * histórico:     .data/OUTPUTS/pipeline_log.jsonl   (append, 1 linha por execução)
      * estado atual:  .data/OUTPUTS/pipeline_metrics.json (upsert por etapa)
  - O comando final generate_report() lê o estado atual e, para qualquer etapa AINDA NÃO
    registrada, calcula lendo os artefatos (pull de fallback). Gera o funil completo do SLR.

Saídas do relatório:
  - .data/OUTPUTS/pipeline_report.md   (funil legível + detalhe por etapa)
  - .data/OUTPUTS/pipeline_funnel.csv  (funil em tabela)
  - .data/OUTPUTS/pipeline_metrics.json (estado consolidado)
"""
import os
import re
import csv
import json
import glob
import urllib.parse
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv(os.path.abspath(".conf"))


# =============================================================================
# Caminhos e utilidades
# =============================================================================

def _paths() -> Dict[str, str]:
    base = os.path.abspath(os.getenv("PATH_DATA", ".data"))

    def j(rel):
        return os.path.join(base, rel)

    return {
        "base": base,
        "outputs": j("OUTPUTS"),
        "select_bibs": j(os.getenv("BIB_FILE", "OUTPUTS/select_bibs.bib")),
        "raw_responses": j("OUTPUTS/raw_responses"),
        "consolidated": j(os.getenv("FILTER_LLM_RESPONSES_ABSTRACT_PATH",
                                    "OUTPUTS/processed_responses/combined_responses_consolidated.json")),
        "relevant": j(os.getenv("RELEVANT_ABSTRACT_PAPERS_OUTPUT",
                                "OUTPUTS/processed_responses/relevant_papers.json")),
        "unrelevant": j(os.getenv("UNRELEVANT_ABSTRACT_PAPERS_OUTPUT",
                                  "OUTPUTS/processed_responses/unrelevant_papers.json")),
        "relevant_bib": j(os.getenv("RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT",
                                    "OUTPUTS/relevant_abstract_papers.bib")),
        "pdfs": j(os.getenv("FOLDER_SAVE_PDF", "PDFs")),
        "bib_dedup": j("OUTPUTS/bib_deduplicate.bib"),
        "bib_dup": j("OUTPUTS/bib_duplicate.bib"),
        "markdowns": j(os.getenv("MARKDOWN_OUTPUT_FOLDER", "PDFs/markdowns")),
        "raw_responses_fulltext": j("OUTPUTS/raw_responses_fulltext"),
        "consolidated_fulltext": j(os.getenv("FILTER_LLM_RESPONSES_FULLTEXT_PATH",
                                   "OUTPUTS/processed_responses/combined_responses_fulltext_consolidated.json")),
        "final_papers": j(os.getenv("FINAL_PAPERS_OUTPUT",
                                    "OUTPUTS/processed_responses/final_papers.json")),
        "final_excluded": j(os.getenv("FINAL_EXCLUDED_PAPERS_OUTPUT",
                                      "OUTPUTS/processed_responses/final_excluded_papers.json")),
        "final_bib": j(os.getenv("FINAL_PAPERS_BIBs_OUTPUT", "OUTPUTS/final_papers.bib")),
        "log": j("OUTPUTS/pipeline_log.jsonl"),
        "state": j("OUTPUTS/pipeline_metrics.json"),
        "report_md": j("OUTPUTS/pipeline_report.md"),
        "funnel_csv": j("OUTPUTS/pipeline_funnel.csv"),
    }


def _sanitize(doi: str) -> str:
    """Replica DonwloadPapers.sanitize_filename (sem importar o módulo pesado)."""
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    return urllib.parse.quote(doi, safe="")


def _read(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None


def _count_bib(path: str) -> Optional[int]:
    txt = _read(path)
    if txt is None:
        return None
    return len(re.findall(r"(?m)^\s*@\w+\s*\{", txt))


def _bib_dois(path: str) -> List[str]:
    txt = _read(path)
    if txt is None:
        return []
    return [m.group(1).strip() for m in re.finditer(r'(?i)doi\s*=\s*[{"]([^}"]+)[}"]', txt)]


def _count_json_list(path: str) -> Optional[int]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return len(data) if isinstance(data, list) else None
    except Exception:
        return None


_PUBLISHER = {
    "10.1109": "IEEE", "10.1016": "Elsevier", "10.1145": "ACM", "10.3390": "MDPI",
    "10.1080": "T&F", "10.1002": "Wiley", "10.1111": "Wiley", "10.1007": "Springer",
    "10.48550": "arXiv",
}


def _publisher(doi: str) -> str:
    for pfx, name in _PUBLISHER.items():
        if doi.startswith(pfx):
            return name
    return "outro"


# =============================================================================
# Pull: calcula as métricas de cada etapa a partir dos artefatos
# =============================================================================

def _pull_busca(P) -> Dict:
    dedup = _count_bib(P["bib_dedup"]) or 0
    dup = _count_bib(P["bib_dup"]) or 0
    m = {}
    if dup:
        m["duplicados_removidos"] = dup
    if dedup:
        m["apos_deduplicacao"] = dedup
    if dedup or dup:
        m["identificados_total"] = dedup + dup
    return m  # vazio quando os .bib de busca/dedup não têm dados (etapa não persistida)


def _pull_enriquecimento(P) -> Dict:
    txt = _read(P["select_bibs"])
    if txt is None:
        return {}
    return {
        "total": len(re.findall(r"(?m)^\s*@\w+\s*\{", txt)),
        "com_doi": len(re.findall(r"(?i)\bdoi\s*=", txt)),
        "com_abstract": len(re.findall(r"(?i)\babstract\s*=", txt)),
    }


def _pull_selecao_metadados(P) -> Dict:
    n = _count_bib(P["select_bibs"])
    return {"selecionados_metadados": n} if n is not None else {}


def _pull_classificacao_llm(P) -> Dict:
    rr = P["raw_responses"]
    if not os.path.isdir(rr):
        return {}
    per = {}
    for d in sorted(glob.glob(os.path.join(rr, "*"))):
        if os.path.isdir(d):
            n = len([f for f in os.listdir(d)
                     if f.startswith("response_") and f.endswith("_raw.txt")])
            per[os.path.basename(d)] = n
    return {"llms": len(per), "respostas_por_llm": per} if per else {}


def _pull_consolidacao(P) -> Dict:
    n = _count_json_list(P["consolidated"])
    if n is None:
        return {}
    m = {"artigos_consolidados": n}
    try:
        with open(P["consolidated"], encoding="utf-8") as f:
            data = json.load(f)
        votes = Counter(r.get("total_responses") for r in data)
        m["distribuicao_votos"] = {str(k): v for k, v in
                                   sorted(votes.items(), key=lambda x: (x[0] is None, x[0]))}
    except Exception:
        pass
    return m


def _pull_filtro(P) -> Dict:
    rel = _count_json_list(P["relevant"])
    unrel = _count_json_list(P["unrelevant"])
    m = {}
    if rel is not None:
        m["selecionados"] = rel
    if unrel is not None:
        m["rejeitados"] = unrel
    if rel is not None and unrel is not None:
        total = rel + unrel
        m["entrada"] = total
        if total:
            m["taxa_selecao_pct"] = round(rel / total * 100, 1)
    try:
        import yaml
        yp = os.getenv("FILTER_LLM_CONFIG_PATH", "config/filter_accept_results_llm.yaml")
        if os.path.exists(yp):
            with open(yp, encoding="utf-8") as f:
                clause = (yaml.safe_load(f) or {}).get("filter", "") or ""
            m["filtro_sql"] = " ".join(clause.split())
    except Exception:
        pass
    return m


def _pull_download(P) -> Dict:
    dois = _bib_dois(P["relevant_bib"])
    if not dois:
        return {}
    pdfs_dir = P["pdfs"]
    missing = [d for d in dois if not os.path.exists(os.path.join(pdfs_dir, _sanitize(d) + ".pdf"))]
    have = len(dois) - len(missing)
    m = {
        "selecionados_com_doi": len(dois),
        "com_pdf": have,
        "sem_pdf": len(missing),
    }
    if dois:
        m["cobertura_pct"] = round(have / len(dois) * 100, 1)
    if missing:
        m["sem_pdf_por_publisher"] = dict(Counter(_publisher(d) for d in missing).most_common())
    return m


def _pull_leitura_pdf(P) -> Dict:
    md = P["markdowns"]
    if os.path.isdir(md):
        return {"markdowns_gerados": len([f for f in os.listdir(md) if f.endswith(".md")])}
    return {}


def _pull_classificacao_fulltext(P) -> Dict:
    rr = P["raw_responses_fulltext"]
    if not os.path.isdir(rr):
        return {}
    per = {}
    for d in sorted(glob.glob(os.path.join(rr, "*"))):
        if os.path.isdir(d):
            n = len([f for f in os.listdir(d)
                     if f.startswith("response_") and f.endswith("_raw.txt")])
            per[os.path.basename(d)] = n
    return {"llms": len(per), "respostas_por_llm": per} if per else {}


def _pull_consolidacao_fulltext(P) -> Dict:
    n = _count_json_list(P["consolidated_fulltext"])
    if n is None:
        return {}
    m = {"artigos_consolidados": n}
    try:
        with open(P["consolidated_fulltext"], encoding="utf-8") as f:
            data = json.load(f)
        votes = Counter(r.get("total_responses") for r in data)
        m["distribuicao_votos"] = {str(k): v for k, v in
                                   sorted(votes.items(), key=lambda x: (x[0] is None, x[0]))}
    except Exception:
        pass
    return m


def _pull_filtro_final(P) -> Dict:
    rel = _count_json_list(P["final_papers"])
    unrel = _count_json_list(P["final_excluded"])
    m = {}
    if rel is not None:
        m["selecionados"] = rel
    if unrel is not None:
        m["rejeitados"] = unrel
    if rel is not None and unrel is not None:
        total = rel + unrel
        m["entrada"] = total
        if total:
            m["taxa_selecao_pct"] = round(rel / total * 100, 1)
    try:
        import yaml
        yp = os.getenv("FILTER_LLM_CONFIG_FULLTEXT_PATH", "config/filter_accept_results_llm_fulltext.yaml")
        if os.path.exists(yp):
            with open(yp, encoding="utf-8") as f:
                clause = (yaml.safe_load(f) or {}).get("filter", "") or ""
            m["filtro_sql"] = " ".join(clause.split())
    except Exception:
        pass
    return m


# (chave_etapa, rótulo, função_pull)
STAGES = [
    ("busca", "Busca / deduplicação", _pull_busca),
    ("enriquecimento", "Enriquecimento", _pull_enriquecimento),
    ("selecao_metadados", "Seleção por metadados", _pull_selecao_metadados),
    ("classificacao_llm", "Classificação por abstract (LLM)", _pull_classificacao_llm),
    ("consolidacao", "Consolidação das respostas", _pull_consolidacao),
    ("filtro", "Filtro de relevância (abstract)", _pull_filtro),
    ("download", "Download de PDFs", _pull_download),
    ("leitura_pdf", "Leitura de PDF", _pull_leitura_pdf),
    ("classificacao_fulltext", "Classificação por texto completo (LLM)", _pull_classificacao_fulltext),
    ("consolidacao_fulltext", "Consolidação (texto completo)", _pull_consolidacao_fulltext),
    ("filtro_final", "Filtro FINAL (texto completo)", _pull_filtro_final),
]
_PULL = {key: fn for key, _label, fn in STAGES}
_LABEL = {key: label for key, label, _fn in STAGES}

# Métrica "principal" de cada etapa para o funil (primeira chave existente).
_FUNNEL_KEY = {
    "busca": ["identificados_total", "apos_deduplicacao"],
    "selecao_metadados": ["selecionados_metadados"],
    "consolidacao": ["artigos_consolidados"],
    "filtro": ["selecionados"],
    "download": ["com_pdf"],
    "leitura_pdf": ["markdowns_gerados"],
    "consolidacao_fulltext": ["artigos_consolidados"],
    "filtro_final": ["selecionados"],
}


# =============================================================================
# Registro incremental (push)
# =============================================================================

def record_stage(stage: str, metrics: Dict) -> None:
    """Grava as métricas de uma etapa no histórico (append) e no estado atual (upsert)."""
    try:
        P = _paths()
        os.makedirs(P["outputs"], exist_ok=True)
        entry = {
            "stage": stage,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "metrics": metrics or {},
        }
        with open(P["log"], "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        state = {}
        if os.path.exists(P["state"]):
            try:
                with open(P["state"], encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                state = {}
        # Estado atual: plano por etapa (mesmo schema que generate_report grava).
        state[stage] = {"timestamp": entry["timestamp"], "metrics": entry["metrics"], "source": "registrado"}
        with open(P["state"], "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"(aviso: falha ao registrar métrica da etapa '{stage}': {e})")


def record_stage_auto(stage: str) -> None:
    """Calcula as métricas da etapa a partir dos artefatos e registra (uso pós-etapa)."""
    fn = _PULL.get(stage)
    if not fn:
        return
    try:
        record_stage(stage, fn(_paths()))
    except Exception as e:
        print(f"(aviso: não foi possível calcular métrica da etapa '{stage}': {e})")


# =============================================================================
# Relatório final (pull de fallback + md/csv/json)
# =============================================================================

def _fmt_metrics(metrics: Dict, indent: str = "  ") -> List[str]:
    lines = []
    for k, v in metrics.items():
        if isinstance(v, dict):
            lines.append(f"{indent}- {k}:")
            for sk, sv in v.items():
                lines.append(f"{indent}    - {sk}: {sv}")
        else:
            lines.append(f"{indent}- {k}: {v}")
    return lines


def _funnel_value(stage: str, metrics: Dict):
    for key in _FUNNEL_KEY.get(stage, []):
        if key in metrics and isinstance(metrics[key], (int, float)):
            return key, metrics[key]
    return None, None


def generate_report():
    """
    Consolida o estado atual + pull de fallback e gera pipeline_report.md, pipeline_funnel.csv
    e atualiza pipeline_metrics.json. Retorna (md, csv, json).
    """
    P = _paths()
    os.makedirs(P["outputs"], exist_ok=True)

    state = {}
    if os.path.exists(P["state"]):
        try:
            with open(P["state"], encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
    # Compat: desempacota schema antigo {gerado_em, etapas:{...}} para o plano por etapa.
    if isinstance(state, dict) and isinstance(state.get("etapas"), dict):
        state = state["etapas"]

    consolidated = {}
    for stage, label, fn in STAGES:
        rec = state.get(stage)
        if rec and rec.get("metrics"):
            consolidated[stage] = {"label": label, "metrics": rec["metrics"],
                                   "timestamp": rec.get("timestamp"), "source": "registrado"}
        else:
            consolidated[stage] = {"label": label, "metrics": fn(P),
                                   "timestamp": None, "source": "calculado dos artefatos"}

    # ---- Funil (valores principais) ----
    funnel = []
    for stage, _label, _fn in STAGES:
        key, val = _funnel_value(stage, consolidated[stage]["metrics"])
        if val is not None:
            funnel.append((consolidated[stage]["label"], key, val))
    top = next((v for _label, _key, v in funnel if v), None)

    # ---- Markdown ----
    md = []
    md.append("# Relatório do Pipeline — Aneta")
    md.append("")
    md.append(f"Gerado em: {datetime.now().isoformat(timespec='seconds')}")
    md.append("")
    md.append("## Funil")
    md.append("")
    md.append("| Etapa | Métrica | Quantidade | % do topo |")
    md.append("|---|---|---:|---:|")
    for label, key, val in funnel:
        pct = f"{val / top * 100:.1f}%" if top else "-"
        md.append(f"| {label} | {key} | {val:,} | {pct} |")
    md.append("")
    md.append("## Detalhe por etapa")
    for stage, label, _fn in STAGES:
        info = consolidated[stage]
        md.append("")
        ts = f" · registrado em {info['timestamp']}" if info["timestamp"] else ""
        md.append(f"### {label}  _({info['source']}{ts})_")
        if info["metrics"]:
            md.extend(_fmt_metrics(info["metrics"]))
        else:
            md.append("  - (sem dados / etapa não executada)")
    md.append("")
    md.append("---")
    md.append(f"Histórico completo de execuções: `{os.path.relpath(P['log'], P['base'])}`")
    md.append("")

    with open(P["report_md"], "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # ---- CSV do funil ----
    with open(P["funnel_csv"], "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["etapa", "metrica", "quantidade", "pct_do_topo"])
        for label, key, val in funnel:
            pct = round(val / top * 100, 1) if top else ""
            w.writerow([label, key, val, pct])

    # ---- Estado consolidado (json) — plano por etapa, mesmo schema do record_stage ----
    flat_state = {
        stage: {"timestamp": consolidated[stage]["timestamp"],
                "source": consolidated[stage]["source"],
                "metrics": consolidated[stage]["metrics"]}
        for stage, _label, _fn in STAGES
    }
    with open(P["state"], "w", encoding="utf-8") as f:
        json.dump(flat_state, f, ensure_ascii=False, indent=2)

    print("Relatório do pipeline gerado:")
    print(f"  - Markdown: {P['report_md']}")
    print(f"  - CSV funil: {P['funnel_csv']}")
    print(f"  - JSON estado: {P['state']}")
    return P["report_md"], P["funnel_csv"], P["state"]
