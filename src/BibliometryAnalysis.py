import os
import json
import csv
from typing import List, Dict, Any, Optional
from collections import Counter

def compute_h_index(citations: List[int]) -> int:
    """Calcula o índice h dado uma lista de contagens de citações."""
    sorted_c = sorted(citations, reverse=True)
    h = 0
    for i, c in enumerate(sorted_c, start=1):
        if c >= i:
            h = i
        else:
            break
    return h


def generate_bibliometry_report_and_plots(
    openalex_records: List[Dict[str, Any]],
    stage: str = "final",
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Gera relatórios, tabelas CSV e gráficos bibliométricos a partir dos metadados do OpenAlex.
    
    Args:
        openalex_records: Lista de dicionários retornados pela API do OpenAlex
        stage: 'final' ou 'post_abstract'
        output_dir: Diretório de destino
        
    Returns:
        Dicionário com métricas calculadas e caminhos dos artefatos
    """
    path_data = os.getenv("PATH_DATA", ".data")
    if output_dir is None:
        output_dir = os.path.join(path_data, "OUTPUTS", "BIBLIOMETRY", stage)
    os.makedirs(output_dir, exist_ok=True)
    
    if not openalex_records:
        print(f"Nenhum registro OpenAlex fornecido para bibliometria ({stage}).")
        return {}
        
    # 1. Extração estruturada
    papers_data = []
    years = []
    venues = []
    authors_all = []
    institutions_all = []
    countries_all = []
    concepts_all = []
    citations_list = []
    oa_count = 0
    
    for r in openalex_records:
        if not r or not isinstance(r, dict):
            continue
        doi = r.get("doi") or ""
        doi_clean = doi.replace("https://doi.org/", "").strip()
        title = r.get("title") or "Sem título"
        year = r.get("publication_year")
        cited_by = r.get("cited_by_count", 0) or 0
        citations_list.append(cited_by)
        
        if year:
            years.append(year)
            
        # Venue
        loc = r.get("primary_location") or {}
        src = loc.get("source") or {}
        venue_name = src.get("display_name") or "Outro / Não especificado"
        venues.append(venue_name)
        
        # Open Access
        oa_info = r.get("open_access") or {}
        is_oa = oa_info.get("is_oa", False)
        if is_oa:
            oa_count += 1
            
        # Authors & Institutions
        authorships = r.get("authorships") or []
        paper_authors = []
        for auth in authorships:
            author_obj = auth.get("author") or {}
            author_name = author_obj.get("display_name")
            if author_name:
                authors_all.append(author_name)
                paper_authors.append(author_name)
                
            insts = auth.get("institutions") or []
            for inst in insts:
                inst_name = inst.get("display_name")
                country = inst.get("country_code")
                if inst_name:
                    institutions_all.append(inst_name)
                if country:
                    countries_all.append(country)
                    
        # Concepts / Keywords
        concepts = r.get("concepts") or []
        for c in concepts:
            c_name = c.get("display_name")
            score = c.get("score", 0) or 0
            if c_name and score > 0.3:
                concepts_all.append(c_name)
                
        papers_data.append({
            "doi": doi_clean,
            "title": title,
            "year": year,
            "venue": venue_name,
            "cited_by_count": cited_by,
            "is_oa": is_oa,
            "authors": "; ".join(paper_authors[:5])
        })
        
    total_papers = len(papers_data)
    total_citations = sum(citations_list)
    avg_citations = round(total_citations / total_papers, 2) if total_papers > 0 else 0
    h_idx = compute_h_index(citations_list)
    oa_pct = round((oa_count / total_papers) * 100, 1) if total_papers > 0 else 0
    
    # 2. Contagens e Rankings
    year_counts = Counter(years)
    venue_counts = Counter(venues)
    author_counts = Counter(authors_all)
    inst_counts = Counter(institutions_all)
    country_counts = Counter(countries_all)
    concept_counts = Counter(concepts_all)
    
    # Top cited papers
    sorted_papers = sorted(papers_data, key=lambda x: x["cited_by_count"], reverse=True)
    top_10_papers = sorted_papers[:10]
    
    # 3. Salvar CSVs
    # Top cited papers
    cited_csv = os.path.join(output_dir, "top_cited_papers.csv")
    with open(cited_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["doi", "title", "year", "venue", "cited_by_count", "is_oa", "authors"])
        writer.writeheader()
        writer.writerows(sorted_papers)
        
    # Publications by year
    years_csv = os.path.join(output_dir, "publications_by_year.csv")
    with open(years_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Year", "Count"])
        for y in sorted(year_counts.keys()):
            writer.writerow([y, year_counts[y]])
            
    # Top Venues
    venues_csv = os.path.join(output_dir, "top_venues.csv")
    with open(venues_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Venue", "Articles"])
        for v, c in venue_counts.most_common(20):
            writer.writerow([v, c])
            
    # Top Authors
    authors_csv = os.path.join(output_dir, "top_authors.csv")
    with open(authors_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Author", "Articles"])
        for a, c in author_counts.most_common(20):
            writer.writerow([a, c])
            
    # Top Concepts
    concepts_csv = os.path.join(output_dir, "top_concepts.csv")
    with open(concepts_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Concept", "Frequency"])
        for conc, c in concept_counts.most_common(25):
            writer.writerow([conc, c])
            
    # 4. Salvar JSON consolidado
    summary_data = {
        "stage": stage,
        "total_papers_analyzed": total_papers,
        "total_citations": total_citations,
        "average_citations_per_paper": avg_citations,
        "corpus_h_index": h_idx,
        "open_access_count": oa_count,
        "open_access_percentage": oa_pct,
        "publications_by_year": dict(sorted(year_counts.items())),
        "top_venues": dict(venue_counts.most_common(10)),
        "top_authors": dict(author_counts.most_common(10)),
        "top_countries": dict(country_counts.most_common(10)),
        "top_concepts": dict(concept_counts.most_common(15)),
        "top_cited_papers": top_10_papers
    }
    summary_json = os.path.join(output_dir, "bibliometry_summary.json")
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
        
    # 5. Gerar Gráficos com Matplotlib/Seaborn
    plots_generated = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        sns.set_theme(style="whitegrid")
        
        # Gráfico 1: Publicações por Ano
        if year_counts:
            plt.figure(figsize=(8, 5))
            y_sorted = sorted(year_counts.keys())
            c_sorted = [year_counts[y] for y in y_sorted]
            bars = plt.bar([str(y) for y in y_sorted], c_sorted, color="#2b5c8f", width=0.55, edgecolor="#1a3857")
            plt.title(f"Produção Científica por Ano ({stage.upper()})", fontsize=13, pad=12, fontweight="bold")
            plt.xlabel("Ano de Publicação", fontsize=11)
            plt.ylabel("Quantidade de Artigos", fontsize=11)
            for bar in bars:
                h = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2., h + 0.5, f"{int(h)}", ha="center", va="bottom", fontsize=10, fontweight="bold")
            plt.tight_layout()
            p1 = os.path.join(output_dir, "publications_by_year.png")
            plt.savefig(p1, dpi=300)
            plt.close()
            plots_generated.append(p1)
            
        # Gráfico 2: Top 10 Veículos de Publicação
        top_v = venue_counts.most_common(10)
        if top_v:
            plt.figure(figsize=(10, 6))
            v_names = [v[0][:40] + ("..." if len(v[0]) > 40 else "") for v in reversed(top_v)]
            v_vals = [v[1] for v in reversed(top_v)]
            plt.barh(v_names, v_vals, color="#3a8076", edgecolor="#224c46")
            plt.title(f"Top 10 Veículos de Publicação ({stage.upper()})", fontsize=13, pad=12, fontweight="bold")
            plt.xlabel("Número de Artigos", fontsize=11)
            for i, val in enumerate(v_vals):
                plt.text(val + 0.2, i, f"{val}", va="center", fontsize=9, fontweight="bold")
            plt.tight_layout()
            p2 = os.path.join(output_dir, "top_venues.png")
            plt.savefig(p2, dpi=300)
            plt.close()
            plots_generated.append(p2)
            
        # Gráfico 3: Top 10 Artigos Mais Citados
        if top_10_papers:
            plt.figure(figsize=(10, 6))
            p_titles = [p["title"][:38] + ("..." if len(p["title"]) > 38 else "") for p in reversed(top_10_papers)]
            p_cites = [p["cited_by_count"] for p in reversed(top_10_papers)]
            plt.barh(p_titles, p_cites, color="#b35a38", edgecolor="#733822")
            plt.title(f"Top 10 Artigos Mais Citados ({stage.upper()})", fontsize=13, pad=12, fontweight="bold")
            plt.xlabel("Total de Citações (OpenAlex)", fontsize=11)
            for i, val in enumerate(p_cites):
                plt.text(val + 0.5, i, f"{val}", va="center", fontsize=9, fontweight="bold")
            plt.tight_layout()
            p3 = os.path.join(output_dir, "top_cited_papers.png")
            plt.savefig(p3, dpi=300)
            plt.close()
            plots_generated.append(p3)
            
    except Exception as e:
        print(f"Aviso ao gerar gráficos matplotlib: {e}")
        
    # 6. Gerar Relatório em Markdown
    md_report = os.path.join(output_dir, f"bibliometry_report_{stage}.md")
    with open(md_report, "w", encoding="utf-8") as f:
        f.write(f"# Relatório Bibliométrico — Estágio: {stage.upper()}\n\n")
        f.write(f"**Total de Artigos Analisados:** {total_papers}  \n")
        f.write(f"**Total de Citações Acumuladas:** {total_citations}  \n")
        f.write(f"**Média de Citações por Artigo:** {avg_citations}  \n")
        f.write(f"**Índice-h do Corpus:** {h_idx}  \n")
        f.write(f"**Taxa de Acesso Aberto (Open Access):** {oa_pct}% ({oa_count}/{total_papers})  \n\n")
        f.write("---\n\n")
        
        f.write("## 1. Evolução Temporal das Publicações\n\n")
        f.write("| Ano | Quantidade de Artigos |\n| :---: | :---: |\n")
        for y in sorted(year_counts.keys()):
            f.write(f"| {y} | {year_counts[y]} |\n")
        f.write("\n---\n\n")
        
        f.write("## 2. Top 10 Artigos Mais Citados\n\n")
        f.write("| DOI | Citações | Ano | Título | Veículo |\n| :--- | :---: | :---: | :--- | :--- |\n")
        for p in top_10_papers:
            f.write(f"| `{p['doi']}` | **{p['cited_by_count']}** | {p['year']} | {p['title']} | {p['venue']} |\n")
        f.write("\n---\n\n")
        
        f.write("## 3. Top Veículos de Publicação (Journals / Conferences)\n\n")
        f.write("| Veículo | Artigos |\n| :--- | :---: |\n")
        for v, c in venue_counts.most_common(10):
            f.write(f"| {v} | {c} |\n")
        f.write("\n---\n\n")
        
        f.write("## 4. Principais Conceitos e Palavras-Chave (OpenAlex)\n\n")
        f.write("| Conceito | Ocorrências |\n| :--- | :---: |\n")
        for conc, c in concept_counts.most_common(15):
            f.write(f"| {conc} | {c} |\n")
        f.write("\n")
        
    print(f"\n✓ Relatório bibliométrico gerado em: {md_report}")
    print(f"✓ Resumo JSON gerado em: {summary_json}")
    if plots_generated:
        print(f"✓ {len(plots_generated)} gráfico(s) PNG gerado(s) em: {output_dir}")
        
    return {
        "output_dir": output_dir,
        "summary_json": summary_json,
        "md_report": md_report,
        "plots": plots_generated,
        "metrics": summary_data
    }
