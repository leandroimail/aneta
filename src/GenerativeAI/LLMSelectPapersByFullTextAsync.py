"""
Triagem por TEXTO COMPLETO (full-text screening) — Aneta.

Espelha a triagem por abstract, trocando o abstract pelo TEXTO COMPLETO do PDF:
  - entrada: relevant_abstract_papers.bib (aprovados no abstract); para cada um, extrai o
    texto (markdown do docling ou PyMuPDF, sem referências) via PDFTextExtract;
  - prompt full-text dedicado (config/fulltext_base_prompts.yaml) com os MESMOS critérios
    (research_questions.yaml: rc/ac/is_relevant/RQ/sq);
  - roda multi-LLM do grupo FULL_TEXT (modelos de contexto grande), 1 paper por vez, async;
  - salva em .data/OUTPUTS/raw_responses_fulltext/<llm>/response_N_<llm>_<model>_raw.txt
    (mesma ordem entre LLMs) + select_bibs_fulltext.json (info por artigo p/ consolidação).

Reaproveita do módulo de abstract: clientes/setup_llms, process_article_async (chamada
pura ao LLM), SequencedArticle e os schemas. A consolidação e o filtro final ficam em
process_responses (parametrizado) e FilterRelevantPapers.filter_final_papers.
"""
import os
import json
import re
import asyncio
from typing import List, Optional, Union, Tuple, Dict, Any

import yaml
from dotenv import load_dotenv

load_dotenv(os.path.abspath(".conf"))
load_dotenv(os.path.abspath("config/.env"))

from src.BibTex import read_bibtex
from src.GenerativeAI.LLMUtilExcel import clean_and_parse_json
from src.GenerativeAI.PDFTextExtract import extract_text
from src.GenerativeAI.LLMSelectPapersByAbstractOneOnOneAsync import (
    setup_llms,
    process_article_async,
    SequencedArticle,
    get_rate_limit,
    ArticleAnalysis,
    LLMResponseModel,
)

FULLTEXT_RAW_SUBDIR = "raw_responses_fulltext"
FULLTEXT_GROUP = "FULL_TEXT"


def _paths() -> Dict[str, str]:
    base = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    return {
        "base": base,
        "outputs": os.path.join(base, "OUTPUTS"),
        "raw_dir": os.path.join(base, "OUTPUTS", FULLTEXT_RAW_SUBDIR),
        "article_info": os.path.join(base, "OUTPUTS", "select_bibs_fulltext.json"),
        "relevant_bib": os.path.join(
            base, os.getenv("RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT",
                            "OUTPUTS/relevant_abstract_papers.bib")),
    }


# --------------------------------------------------------------------------- prompt
def _format_criteria() -> Dict[str, str]:
    """Lê research_questions.yaml + search_config.yaml e formata os blocos do prompt."""
    base = os.getenv("PROJECT_PATH", os.getcwd())
    rq_path = os.path.join(base, "config", "research_questions.yaml")
    if not os.path.exists(rq_path):
        rq_path = os.path.join(base, "Config", "research_questions.yaml")
    sc_path = os.path.join(base, "config", "search_config.yaml")
    if not os.path.exists(sc_path):
        sc_path = os.path.join(base, "Config", "search_config.yaml")

    with open(rq_path, encoding="utf-8") as f:
        rq = yaml.safe_load(f)
    search_string = ""
    try:
        with open(sc_path, encoding="utf-8") as f:
            search_string = (yaml.safe_load(f) or {}).get("search_string", "")
    except Exception:
        search_string = ""

    questions = f"principal_research_question: {rq['principal_research_question']}\n"
    for k, v in (rq.get("additional_research_questions") or {}).items():
        questions += f"{k}: {v}\n"
    supporting = "".join(f"{k}: {v}\n" for k, v in (rq.get("supporting_questions") or {}).items())
    rejection = "".join(f"{k}: {v}\n" for k, v in (rq.get("rejection_criteria") or {}).items())
    accepted = "".join(f"{k}: {v}\n" for k, v in (rq.get("accepted_criteria") or {}).items())
    return {
        "query": search_string,
        "questions": questions,
        "supporting_questions": supporting,
        "rejection_criteria": rejection,
        "accepted_criteria": accepted,
        "principal_research_question": rq["principal_research_question"],
    }


def _load_template() -> str:
    base = os.getenv("PROJECT_PATH", os.getcwd())
    path = os.path.join(base, "config", "fulltext_base_prompts.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["base_prompt"]


def _fill_prompt(template: str, crit: Dict[str, str], paper: Dict[str, str], full_text: str) -> str:
    p = template
    p = p.replace("{{query}}", crit["query"])
    p = p.replace("{{questions}}", crit["questions"])
    p = p.replace("{{supporting_questions}}", crit["supporting_questions"])
    p = p.replace("{{rejection_criteria}}", crit["rejection_criteria"])
    p = p.replace("{{accepted_criteria}}", crit["accepted_criteria"])
    p = p.replace("{{principal_research_question}}", crit["principal_research_question"])
    p = p.replace("{{id}}", paper["doi"])
    p = p.replace("{{title}}", paper.get("title", ""))
    p = p.replace("{{full_text}}", full_text)
    return p


def _max_chars() -> int:
    """Teto de caracteres do texto enviado (0 = sem limite). Protege LLMs de contexto menor."""
    try:
        return int(os.getenv("FULLTEXT_MAX_CHARS", "400000"))
    except (TypeError, ValueError):
        return 400000


def _truncate(text: str, cap: int) -> str:
    if cap and len(text) > cap:
        head = int(cap * 0.7)
        tail = cap - head
        return text[:head] + "\n\n[...TRUNCADO...]\n\n" + text[-tail:]
    return text


def build_fulltext_prompts(input_bib: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Monta os prompts de full-text para os papers (aprovados no abstract) que TÊM texto.
    Escreve select_bibs_fulltext.json (info por artigo, na ordem dos prompts) p/ a consolidação.

    Returns:
        (papers, pending) — papers: [{id,doi,title,abstract,keywords,prompt}] na ordem;
        pending: [{id, reason}] dos sem DOI/sem texto (não excluídos automaticamente).
    """
    P = _paths()
    bib = input_bib or P["relevant_bib"]
    entries = read_bibtex(bib)

    template = _load_template()
    crit = _format_criteria()
    cap = _max_chars()

    # Extrai o texto em PARALELO (cada leitura já tem timeout interno; paralelizar faz os
    # timeouts de arquivos só-na-nuvem (OneDrive) se sobreporem em vez de somarem).
    from concurrent.futures import ThreadPoolExecutor
    dois = [(e.get("doi") or "").strip() for e in entries]
    uniq = list({d for d in dois if d})
    texts: Dict[str, Optional[str]] = {}
    if uniq:
        with ThreadPoolExecutor(max_workers=8) as ex:
            for d, t in zip(uniq, ex.map(extract_text, uniq)):
                texts[d] = t

    papers: List[Dict[str, Any]] = []
    pending: List[Dict[str, str]] = []
    for i, (e, doi) in enumerate(zip(entries, dois)):
        if not doi:
            pending.append({"id": e.get("ID", "?"), "reason": "sem doi"})
            continue
        text = texts.get(doi)
        if not text:
            pending.append({"id": doi, "reason": "sem texto/pdf"})
            continue
        paper = {
            # idx = posição NO BIB COMPLETO (estável): não muda quando o conjunto de
            # pendentes varia (OneDrive não-determinístico) → response_N e o skip ficam estáveis.
            "idx": i,
            "id": doi, "doi": doi,
            "title": e.get("title", ""), "abstract": e.get("abstract", ""),
            "keywords": e.get("keywords", ""),
        }
        paper["prompt"] = _fill_prompt(template, crit, paper, _truncate(text, cap))
        papers.append(paper)

    # Info por artigo (chave = DOI), na MESMA ordem dos prompts → consolidação.
    os.makedirs(P["outputs"], exist_ok=True)
    info = [{"id": p["doi"], "doi": p["doi"], "title": p["title"],
             "abstract": p["abstract"], "keywords": p["keywords"]} for p in papers]
    with open(P["article_info"], "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print(f"Full-text: {len(papers)} papers com texto · {len(pending)} pendentes (sem PDF/DOI).")
    return papers, pending



def _normalize_doi(value: str) -> str:
    """Lowercase + remove prefixo de resolver (https://doi.org/...); base do skip/resume."""
    return re.sub(r'^(https?://(dx\.)?doi\.org/)', '', str(value or "").strip().lower())


# --------------------------------------------------------------------------- execução
async def _process_papers_for_client(cfg, client, papers: List[Dict[str, Any]], raw_dir: str) -> int:
    rate_limit = cfg.rate_limit or get_rate_limit()
    if rate_limit <= 0:
        rate_limit = get_rate_limit()
    min_delay = 1.0 / rate_limit
    # Full-text é pesado (prompts grandes): concorrência menor que o abstract.
    # Clients pi limitam subprocessos simultâneos (max_concurrent do YAML).
    if getattr(cfg, "max_concurrent", None):
        max_concurrent = max(1, min(int(cfg.max_concurrent), 16))
    else:
        max_concurrent = max(1, min(6, int(rate_limit)))
    sem = asyncio.Semaphore(max_concurrent)
    out_dir = os.path.join(raw_dir, cfg.name)
    os.makedirs(out_dir, exist_ok=True)

    print(f"[{cfg.name}/{cfg.model_name}] full-text: {len(papers)} papers, "
          f"concorrência={max_concurrent}")

    # sequence = idx ESTÁVEL (posição no bib completo). response_N alinhado entre LLMs.
    sequenced = [SequencedArticle(p["idx"], p["prompt"]) for p in papers]
    doi_by_idx = {p["idx"]: _normalize_doi(p.get("doi", "")) for p in papers}

    async def worker(article: SequencedArticle):
        idx = article.sequence
        fpath = os.path.join(out_dir, f"response_{idx + 1}_{cfg.name}_{cfg.model_name}_raw.txt")
        expected_doi = doi_by_idx.get(idx, "")
        if os.path.exists(fpath) and not cfg.overwrite:
            # Skip ROBUSTO (ciente do DOI): só pula se a resposta salva for DESTE paper —
            # evita reaproveitar um response_N de um conjunto/ordem anterior (colisão de índice).
            # Comparação case-insensitive (o prompt pede JSON em lowercase, então o id volta minúsculo).
            try:
                with open(fpath, encoding="utf-8") as f:
                    parsed = clean_and_parse_json(f.read())
                saved_id = _normalize_doi(parsed.get("id", ""))
                if saved_id == expected_doi:
                    return
            except Exception:
                pass
        async with sem:
            try:
                # Timeout por chamada: full-text tem prompts grandes; evita hang indefinido.
                await asyncio.wait_for(process_article_async(article, client), timeout=240)
            except asyncio.TimeoutError:
                print(f"⏱ Timeout (240s) no paper {article.sequence + 1} "
                      f"[{cfg.name}/{cfg.model_name}] — pulando.", flush=True)
            if min_delay > 0:
                await asyncio.sleep(min_delay)
        if article.raw_response:
            # Salva no índice CORRETO do paper (alinhado entre LLMs para a consolidação).
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(article.raw_response)

    await asyncio.gather(*[worker(a) for a in sequenced], return_exceptions=True)

    saved = len([f for f in os.listdir(out_dir)
                 if f.startswith("response_") and f.endswith("_raw.txt")])
    print(f"[{cfg.name}/{cfg.model_name}] {saved}/{len(papers)} respostas em disco.")
    return saved


async def analyze_fulltext(input_bib: Optional[str] = None,
                           selected: Optional[Union[str, List[str]]] = None) -> Dict[str, Any]:
    P = _paths()
    papers, pending = build_fulltext_prompts(input_bib)
    if not papers:
        print("Nenhum paper com texto para triagem por full-text.")
        return {"papers": 0, "pending": len(pending)}

    clients = setup_llms(FULLTEXT_GROUP, selected)
    print(f"Full-text multi-LLM: {len(clients)} cliente(s): "
          f"{', '.join(cfg.name for cfg, _ in clients)}")
    os.makedirs(P["raw_dir"], exist_ok=True)

    results = await asyncio.gather(
        *[_process_papers_for_client(cfg, client, papers, P["raw_dir"]) for cfg, client in clients]
    )
    return {"papers": len(papers), "pending": len(pending),
            "por_llm": {cfg.name: r for (cfg, _), r in zip(clients, results)}}


async def run_fulltext_classification(input_bib: Optional[str] = None,
                                      selected: Optional[Union[str, List[str]]] = None):
    """Entrada principal (async) da classificação por texto completo."""
    try:
        res = await analyze_fulltext(input_bib, selected=selected)
        print(f"Classificação full-text concluída: {res}")
        return res
    except Exception as e:
        print(f"Erro na classificação full-text: {e}")
        raise
