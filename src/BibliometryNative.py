"""Python equivalents of the plots and workbooks in RunBibliometrix.r."""

from collections import Counter
from datetime import date
from itertools import combinations, product
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from contextlib import nullcontext

import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage


def _objects(items):
    return [item for item in items or [] if isinstance(item, dict)]


def _names(items):
    return tuple(
        sorted(
            {
                item["display_name"]
                for item in _objects(items)
                if item.get("display_name")
            }
        )
    )


def _documents(records):
    docs = []
    for index, record in enumerate(_objects(records)):
        authorships = _objects(record.get("authorships"))
        institutions = [i for a in authorships for i in _objects(a.get("institutions"))]
        countries = sorted(
            {i["country_code"] for i in institutions if i.get("country_code")}
            | {c for a in authorships for c in a.get("countries") or []}
        )
        source = (record.get("primary_location") or {}).get("source") or {}
        first = next(
            (a for a in authorships if a.get("author_position") == "first"),
            next(iter(authorships), {}),
        )
        lead = (first.get("author") or {}).get("display_name") or ""
        corresponding = next(
            (a for a in authorships if a.get("is_corresponding")), first
        )
        corresponding_countries = corresponding.get("countries") or [
            i["country_code"]
            for i in _objects(corresponding.get("institutions"))
            if i.get("country_code")
        ]
        docs.append(
            dict(
                lead=lead,
                kind=record.get("type"),
                lead_countries=corresponding_countries[:1],
                key=record.get("id") or record.get("doi") or str(index),
                Paper=record.get("title") or record.get("display_name") or str(index),
                DOI=(record.get("doi") or "").removeprefix("https://doi.org/"),
                PY=record.get("publication_year"),
                TC=record.get("cited_by_count") or 0,
                source=source.get("display_name"),
                authors=tuple(
                    a["author"]["display_name"]
                    for a in authorships
                    if (a.get("author") or {}).get("display_name")
                ),
                terms=tuple(
                    n.split(" (", 1)[0].upper()
                    for n in _names(
                        [
                            item
                            for item in _objects(record.get("concepts"))
                            if (item.get("score") or 0) >= 0.5
                        ]
                    )
                ),
                keywords=_names(record.get("keywords")),
                institutions=_names(institutions),
                countries=countries,
                refs={
                    r
                    for r in record.get("referenced_works") or []
                    if isinstance(r, str)
                },
            )
        )
    return docs


def _rank(docs, field):
    return Counter(name for doc in docs for name in doc[field])


def _network(docs, field, size, minimum=1):
    counts = _rank(docs, field)
    nodes = {n for n, count in counts.most_common(size) if count >= minimum}
    weights = Counter(
        pair
        for doc in docs
        for pair in combinations(sorted(nodes.intersection(doc[field])), 2)
    )
    graph = nx.Graph()
    graph.add_nodes_from(sorted(nodes))
    graph.add_weighted_edges_from((u, v, w) for (u, v), w in weights.items())
    return graph


def generate_native_outputs(records, output_dir):
    """Render into a single stage directory. Record insufficient-data analyses."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    docs = _documents(records)
    status = {}
    from matplotlib.backends.backend_pdf import PdfPages

    # Finish rendering before replacing any previous stage artifacts.
    with TemporaryDirectory(prefix=".bibliometry-", dir=out.parent) as temp:
        staging = Path(temp)
        with PdfPages(staging / "Rplots.pdf") if docs else nullcontext() as pdf:
            _render(docs, staging, status, pdf)
        status["Rplots.pdf"] = "generated" if docs else "No documents"
        manifest = "bibliometry_artifacts.json"
        (staging / manifest).write_text(json.dumps(status, indent=2), encoding="utf-8")
        for name, result in status.items():
            if result == "generated":
                (staging / name).replace(out / name)
            else:
                (out / name).unlink(missing_ok=True)
        (staging / manifest).replace(out / manifest)
    return status


def _render(docs, out, status, pdf):

    def figure(name, title, available, draw, missing):
        path = out / (name + ".png")
        if not available:
            path.unlink(missing_ok=True)
            status[path.name] = missing
            return
        fig = Figure(figsize=(10, 7), layout="constrained")
        ax = fig.subplots()
        ax.set_title(title)
        draw(ax)
        fig.savefig(path, dpi=130)
        pdf.savefig(fig)
        status[path.name] = "generated"

    def sheet(name, frame):
        with pd.ExcelWriter(out / (name + ".xlsx"), engine="openpyxl") as writer:
            include_rows = name in {
                "main_information",
                "most_productive_authors",
                "most_cited_papers",
            }
            if include_rows:
                frame = frame.reset_index(drop=True)
                frame.index = frame.index + 1
            frame.to_excel(writer, index=include_rows)
            for row in writer.book.active.iter_rows():
                for cell in row:
                    if cell.data_type == "f":
                        cell.data_type = "s"
        status[name + ".xlsx"] = "generated"

    df = pd.DataFrame(
        docs,
        columns=[
            "key",
            "Paper",
            "DOI",
            "PY",
            "TC",
            "source",
            "authors",
            "terms",
            "institutions",
            "countries",
            "refs",
            "keywords",
            "lead",
            "lead_countries",
            "kind",
        ],
    )
    # Keep the bibliographic data-frame export readable by R downstream.
    import rdata

    legacy = (
        df.drop(columns=["lead"])
        .rename(
            columns={
                "key": "id_oa",
                "Paper": "TI",
                "DOI": "DI",
                "source": "SO",
                "authors": "AU",
                "terms": "ID",
                "institutions": "AU_UN",
                "countries": "AU_CO",
                "refs": "CR",
                "keywords": "DE",
                "lead_countries": "AU1_CO",
                "kind": "DT",
            }
        )
        .copy()
    )
    for col in ("AU", "ID", "AU_UN", "AU_CO", "CR", "DE", "AU1_CO"):
        legacy[col] = (
            legacy[col].map(lambda items: ";".join(sorted(items))).astype("string")
        )
    for col in ("id_oa", "TI", "DI", "SO", "DT"):
        legacy[col] = legacy[col].astype("string")
    legacy["PY"] = legacy.PY.astype("Int32")
    legacy["TC"] = legacy.TC.astype("Int32")
    rdata.write_rds(out / "bibliometry_data.rds", legacy)
    status["bibliometry_data.rds"] = "generated"
    local = _rank(docs, "refs")
    df["LCS"] = df.key.map(local).astype(int)
    df["TCperYear"] = df.TC / (date.today().year - pd.to_numeric(df.PY) + 1).clip(
        lower=1
    )
    years = df.groupby("PY").size()
    authors = _rank(docs, "authors")
    countries = _rank(docs, "lead_countries")
    frac = Counter()
    for doc in docs:
        for author in doc["authors"]:
            frac[author] += 1 / len(doc["authors"])
    author_frame = pd.DataFrame(
        authors.most_common(30), columns=["Authors", "Articles"]
    )
    fractional = pd.DataFrame(
        frac.most_common(30),
        columns=["Authors-fractionalized", "Articles Fractionalized"],
    )
    sheet("most_productive_authors", pd.concat([author_frame, fractional], axis=1))
    age = date.today().year - pd.to_numeric(df.PY)
    span = years.index[-1] - years.index[0] if len(years) else 0
    growth = (
        ((years.iloc[-1] / years.iloc[0]) ** (1 / span) - 1) * 100 if span else None
    )
    solo = [d["authors"][0] for d in docs if len(d["authors"]) == 1]
    appearances = sum(authors.values())
    summary = {
        "MAIN INFORMATION ABOUT DATA": None,
        "Timespan": f"{min(years.index)}:{max(years.index)}" if len(years) else "",
        "Sources (Journals, Books, etc)": df.source.nunique(),
        "Documents": len(df),
        "Annual Growth Rate %": growth,
        "Document Average Age": age.mean(),
        "Average citations per doc": df.TC.mean(),
        "Average citations per year per doc": df.TCperYear.mean(),
        "References": len(local),
        "DOCUMENT TYPES": None,
        **df.kind.value_counts().sort_index().to_dict(),
        "DOCUMENT CONTENTS": None,
        "Keywords Plus (ID)": len(_rank(docs, "terms")),
        "Author's Keywords (DE)": len(_rank(docs, "keywords")),
        "AUTHORS": None,
        "Authors": len(authors),
        "Author Appearances": appearances,
        "Authors of single-authored docs": len(set(solo)),
        "AUTHORS COLLABORATION": None,
        "Single-authored docs": len(solo),
        "Documents per Author": len(df) / len(authors) if authors else None,
        "Co-Authors per Doc": appearances / len(df) if len(df) else None,
        "International co-authorships %": 100
        * sum(len(d["countries"]) > 1 for d in docs)
        / len(df)
        if len(df)
        else None,
    }
    sheet(
        "main_information",
        pd.DataFrame(summary.items(), columns=["Description", "Results"]),
    )
    df["NTC"] = df.TC / df.groupby("PY").TC.transform("mean").replace(0, np.nan)
    df["Paper"] = [
        f"{d['lead'].upper()}, {d['PY']}, " if d["lead"] else d["Paper"] for d in docs
    ]
    for name, col in [
        ("top20_most_cited_papers", "TC"),
        ("top20_most_locally_cited_papers", "LCS"),
    ]:
        ranked = df.sort_values(col, ascending=False, kind="stable")
        if col == "TC":
            table = ranked[["Paper", "DOI", "TC", "TCperYear", "NTC"]]
            sheet("most_cited_papers", table.head(30))
        else:
            table = ranked.rename(columns={"TC": "GCS", "PY": "Year"})[
                ["Paper", "DOI", "Year", "LCS", "GCS"]
            ]
        table = table.head(20)
        sheet(name, table)

        def citation_chart(ax):
            ordered = table.iloc[::-1]
            bars = ax.barh(
                range(len(ordered)),
                ordered[col],
                color="#3366cc" if col == "TC" else "#990066",
                alpha=0.8,
            )
            ax.bar_label(bars, fontsize=7)
            ax.set_yticks(range(len(ordered)), ordered.Paper, fontsize=7)
            ax.set_xlabel("Total citations" if col == "TC" else "Local citations")
            if col == "TC":
                annual = ax.twiny()
                annual.scatter(
                    ordered.TCperYear, range(len(ordered)), color="#cc3333", s=14
                )
                annual.set_xlabel("Citations per year", color="#cc3333")

        figure(
            name,
            name.replace("_", " ").title(),
            len(table) and (col == "TC" or bool(local)),
            citation_chart,
            "No documents with citation data",
        )
    productivity = pd.Series(dict(authors.most_common(10))).iloc[::-1]

    def author_bars(ax):
        ax.barh(productivity.index, productivity, color="#dddddd")
        ax.scatter(productivity.values, productivity.index, color="#398dc4")
        ax.set_xlabel("Articles")

    figure(
        "most_productive_authors",
        "Most productive authors",
        len(productivity),
        author_bars,
        "Missing authors",
    )
    ranked_countries = pd.Series(dict(countries.most_common(10))).iloc[::-1]
    international = Counter(
        c for d in docs if len(d["countries"]) > 1 for c in d["lead_countries"]
    )

    def country_bars(ax):
        mcp = np.array([international[c] for c in ranked_countries.index])
        scp = ranked_countries.to_numpy() - mcp
        ax.barh(ranked_countries.index, scp, color="#00bfc4", label="SCP")
        ax.barh(ranked_countries.index, mcp, left=scp, color="#f8766d", label="MCP")
        ax.legend()
        ax.set_xlabel("Articles")

    figure(
        "most_productive_countries",
        "Most productive countries",
        len(ranked_countries),
        country_bars,
        "Missing countries",
    )
    for name, series in [
        ("annual_scientific_production", years),
        (
            "average_article_citation",
            df.TC.div(age.clip(lower=1)).groupby(df.PY).mean(),
        ),
    ]:

        def area(ax):
            series_full = series.reindex(
                range(int(series.index.min()), int(series.index.max()) + 1),
                fill_value=0,
            ).astype(float)
            ax.plot(series_full.index, series_full.values, color="grey")
            ax.fill_between(series_full.index, series_full.values, color="#eeeeee")
            ax.set_xticks(series_full.index[:: max(1, len(series_full) // 10)])
            ax.set_ylabel(
                "Articles"
                if name == "annual_scientific_production"
                else "Mean citations per year"
            )

        figure(
            name,
            name.replace("_", " ").title(),
            len(series),
            area,
            "Missing publication year",
        )
    for field, name, limit in [
        ("terms", "keyword_growth_top20", 20),
        ("source", "journal_publication_growth_top5", 5),
        ("authors", "author_production_top10", 10),
    ]:
        expanded = df.explode(field).dropna(subset=[field, "PY"])
        counts = pd.crosstab(expanded.PY, expanded[field])
        counts = counts.reindex(
            columns=counts.sum().sort_values(ascending=False).head(limit).index
        )
        if field == "authors":

            def draw(ax):
                for y, author in enumerate(counts):
                    positive = counts[author][counts[author] > 0]
                    ax.hlines(
                        y,
                        positive.index.min(),
                        positive.index.max(),
                        color="#d59696",
                        lw=0.8,
                    )
                    cites = (
                        expanded[expanded.authors == author]
                        .groupby("PY")
                        .TCperYear.sum()
                    )
                    ax.scatter(
                        positive.index,
                        [y] * len(positive),
                        s=30 * positive.values,
                        c=cites.reindex(positive.index),
                        cmap="Blues",
                        vmin=0,
                        vmax=max(1, expanded.TCperYear.max()),
                    )
                ax.set_yticks(range(len(counts.columns)), counts.columns)
        else:

            def draw(ax):
                counts.cumsum().plot(ax=ax, marker="o", fontsize=8)
                ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1, 1))

        figure(
            name,
            name.replace("_", " ").title(),
            counts.size,
            draw,
            f"Missing {field} or publication year",
        )
    kw = df[df.PY.isin(years.index[-10:])].explode("terms").dropna(subset=["terms"])
    recent = pd.crosstab(kw.terms, kw.PY).reindex(
        columns=years.index[-10:], fill_value=0
    )
    recent = recent.loc[
        recent.sum(axis=1).sort_values(ascending=False, kind="stable").head(20).index
    ].sort_index()
    sheet("top20_keywords_last_years", recent.rename_axis("Keyword").reset_index())
    figure(
        "top20_keywords_last_years",
        "Top keywords by year",
        recent.size,
        lambda ax: recent.T.plot.bar(stacked=True, ax=ax).legend(
            fontsize=7, bbox_to_anchor=(1, 1)
        ),
        "Missing keywords or years",
    )
    for field, name in [
        ("authors", "author_collaboration_network_top50"),
        ("institutions", "affliliation_collaboration_network_top50"),
        ("countries", "country_collaboration_network_top50"),
        ("terms", "keyword_cooccurrences_top50"),
    ]:
        graph = _network(docs, field, 50)
        if field in ("terms", "institutions"):
            frequency = _rank(docs, field)
            for a, b, edge in graph.edges(data=True):
                edge["weight"] /= frequency[a] * frequency[b]
        figure(
            name,
            name.replace("_", " ").title(),
            graph.number_of_edges(),
            lambda ax: _draw_network(ax, graph, circle=field == "countries"),
            f"No co-occurring {field}",
        )
    thematic = _network(docs, "terms", 1000, 2)
    figure(
        "thematic_map_6labels",
        "Thematic map",
        thematic.number_of_edges(),
        lambda ax: _cluster_map(ax, thematic),
        "Requires co-occurring keywords in at least two documents",
    )
    ids = set(df.key)
    citations = nx.DiGraph((d["key"], ref) for d in docs for ref in d["refs"] & ids)
    nodes = sorted(citations, key=lambda k: -citations.in_degree(k))[:50]
    figure(
        "historical_citation_network_top50",
        "Historical citation network",
        citations.number_of_edges(),
        lambda ax: _historical(ax, citations.subgraph(nodes), df),
        "No within-corpus citations",
    )
    coupling = nx.Graph()
    for a, b in combinations(sorted(docs, key=lambda d: -d["TC"])[:500], 2):
        common = len(a["refs"] & b["refs"])
        if common:
            coupling.add_edge(a["key"], b["key"], weight=common)
    figure(
        "coupling_map_cited_ref_fre5_top500",
        "Bibliographic coupling",
        coupling.number_of_edges(),
        lambda ax: _coupling_map(ax, coupling, df),
        "No shared references",
    )
    _conceptual(df, figure)
    _geography(countries, figure, sheet)
    _widgets(out, docs, kw.terms.value_counts(), status)


def _historical(ax, graph, df):
    labels = df.set_index("key")
    dated = [n for n in graph if pd.notna(labels.at[n, "PY"])]
    pos = {}
    for year in sorted({labels.at[n, "PY"] for n in dated}):
        group = sorted(n for n in dated if labels.at[n, "PY"] == year)
        pos.update({n: (year, (i + 1) / (len(group) + 1)) for i, n in enumerate(group)})
    nx.draw_networkx(
        graph.subgraph(dated),
        pos,
        ax=ax,
        node_color="#f8c3c3",
        node_size=20,
        labels={n: labels.at[n, "Paper"][:25] for n in dated},
        font_size=5,
        width=0.4,
    )
    ax.margins(0.12)
    ax.axis("off")


def _draw_network(ax, graph, circle=False):
    pos = (
        nx.circular_layout(graph)
        if circle
        else nx.spring_layout(graph, seed=42, iterations=120, weight="weight")
    )
    groups = nx.community.louvain_communities(
        graph.to_undirected(), seed=42, weight="weight"
    )
    colors = {node: i for i, group in enumerate(groups) for node in group}
    ax.axis("off")
    nx.draw_networkx(
        graph,
        pos,
        ax=ax,
        node_color=[colors[n] for n in graph],
        cmap="Set2",
        node_size=[18 + 12 * graph.degree(n) for n in graph],
        font_size=6,
        labels={k: str(k).removeprefix("https://openalex.org/") for k in graph},
        width=[
            np.log1p(d["weight"]) if "weight" in d else 1
            for _, _, d in graph.edges(data=True)
        ],
    )
    ax.margins(0.2)


def _cluster_map(ax, graph):
    groups = nx.community.louvain_communities(graph, seed=42)
    points = []
    for group in groups:
        sub = graph.subgraph(group)
        external = sum(
            graph[u][v]["weight"] for u in group for v in graph[u] if v not in group
        )
        vertical = sub.size(weight="weight") / len(group)
        points.append((external, vertical))
        ax.scatter(external, vertical, s=30 * len(group), alpha=0.5)
        label = sorted(group, key=lambda n: (-graph.degree(n, weight="weight"), n))[:6]
        ax.annotate(
            "\n".join(x.removeprefix("https://openalex.org/") for x in label),
            (external, vertical),
            fontsize=7,
        )
    ax.axvline(np.median([p[0] for p in points]), color="grey", ls=":")
    ax.axhline(np.median([p[1] for p in points]), color="grey", ls=":")
    ax.set(
        xlabel="Centrality",
        ylabel="Density",
    )


def _coupling_map(ax, graph, df):
    from igraph import Graph
    from scipy.stats import rankdata

    weighted = Graph.TupleList(graph.edges(data="weight"), weights=True)
    groups = weighted.community_walktrap(weights="weight").as_clustering()
    centrality = nx.pagerank(graph, weight="weight")
    impact = (
        df.LCS / df.groupby("PY").LCS.transform("mean").replace(0, np.nan)
    ).fillna(0)
    impact.index = df.key
    clusters = []
    for group in groups:
        members = [weighted.vs[i]["name"] for i in group]
        if len(members) < int(5 * len(df) / 1000):
            continue
        scores = impact.reindex(members)
        eligible = scores[scores >= 1]
        clusters.append(
            (
                np.mean([centrality[n] for n in members]),
                eligible.mean() if len(eligible) else 0,
                len(members),
                scores.idxmax(),
            )
        )
    if clusters:
        x, y, sizes, labels = zip(*clusters)
        x, y = rankdata(x), rankdata(y)
        ax.scatter(x, y, s=np.array(sizes) * 30, alpha=0.5)
        for xx, yy, label in zip(x, y, labels):
            ax.annotate(
                str(label).removeprefix("https://openalex.org/"), (xx, yy), fontsize=8
            )
        ax.axhline(np.mean(y), ls=":", color="grey")
        ax.axvline(np.mean(x), ls=":", color="grey")
    ax.set(xlabel="Centrality (rank)", ylabel="Normalized local citation impact (rank)")


def _conceptual(df, figure):
    # MCA on the complete disjunctive (presence and absence) indicator matrix.
    terms = df.explode("terms").dropna(subset=["terms"])
    matrix = (
        pd.crosstab(terms.key, terms.terms).reindex(df.key, fill_value=0).clip(upper=1)
    )
    matrix = matrix.loc[:, (matrix.sum() >= 5) & (matrix.sum() < len(df))]
    valid = matrix.shape[1] >= 2
    if valid:
        indicators = np.column_stack((matrix, 1 - matrix)).astype(float)
        p = indicators / indicators.sum()
        r, c = p.sum(axis=1), p.sum(axis=0)
        expected = np.outer(r, c)
        u, s, vt = np.linalg.svd(
            (p - expected) / np.sqrt(expected), full_matrices=False
        )
        rows = u[:, :2] * s[:2] / np.sqrt(r[:, None])
        cols = (vt[:2].T * s[:2] / np.sqrt(c[:, None]))[: matrix.shape[1]]
        tree = linkage(cols, method="ward")
        labels = fcluster(tree, min(5, len(cols)), criterion="maxclust")
    for suffix, mode in [
        ("terms_MAC_5cluster", "terms"),
        ("docs_contrib_MAC_5cluster", "contribution"),
        ("docs_tc_MAC_5cluster", "citations"),
        ("dendogram", "tree"),
    ]:

        def draw(ax):
            if mode == "tree":
                dendrogram(
                    tree,
                    labels=list(matrix.columns),
                    ax=ax,
                    leaf_rotation=90,
                    leaf_font_size=7,
                )
            elif mode == "terms":
                from scipy.spatial import ConvexHull
                from matplotlib import colormaps

                palette = colormaps["Set2"]
                for cluster in set(labels):
                    group = np.unique(cols[labels == cluster], axis=0)
                    if len(group) > 2 and np.linalg.matrix_rank(group - group[0]) == 2:
                        hull = ConvexHull(group)
                        ax.fill(
                            *group[hull.vertices].T,
                            color=palette(int(cluster) % 8),
                            alpha=0.25,
                        )
                ax.scatter(*cols.T, c=[palette(int(n) % 8) for n in labels])
                for label, point in zip(matrix.columns, cols):
                    ax.annotate(label, point, fontsize=7)
            else:
                scores = (
                    (u[:, :2] ** 2).sum(axis=1)
                    if mode == "contribution"
                    else df.TC.to_numpy()
                )
                top = np.argsort(-scores, kind="stable")[:100]
                scatter = ax.scatter(*rows[top].T, c=scores[top])
                ax.figure.colorbar(scatter, ax=ax, label=mode)
                for idx in top[:10]:
                    ax.annotate(df.iloc[idx].Paper[:26], rows[idx], fontsize=6)

        figure(
            "conceptual_structure_" + suffix,
            "Conceptual structure — " + mode,
            valid,
            draw,
            "Requires two variable keywords present in at least five papers",
        )


def _geography(countries, figure, sheet):
    from countryinfo import CountryInfo
    from matplotlib import colormaps, colors

    countries_data = CountryInfo().all().values()
    names = {
        c.get("ISO", {}).get("alpha2"): c["name"].lower()
        for c in countries_data
        if c.get("name")
    }
    names.update(US="usa", GB="united kingdom")
    top = dict(countries.most_common(20))
    sheet(
        "world_map_publications_top20",
        pd.DataFrame(
            [(names.get(k, k), v) for k, v in top.items()],
            columns=["country", "publications"],
        ),
    )

    def draw(ax):
        norm = colors.Normalize(0, max(top.values()))
        for country in countries_data:
            code = country.get("ISO", {}).get("alpha2")
            for feature in (country.get("geoJSON") or {}).get("features", []):
                geo = feature["geometry"]
                polygons = (
                    geo["coordinates"]
                    if geo["type"] == "MultiPolygon"
                    else [geo["coordinates"]]
                )
                for polygon in polygons:
                    coords = np.asarray(polygon[0])
                    ax.fill(
                        *coords.T,
                        color=colormaps["Blues"](norm(top[code]))
                        if code in top
                        else "#ddd",
                        linewidth=0.2,
                        edgecolor="white",
                    )
        from matplotlib.cm import ScalarMappable

        ax.figure.colorbar(
            ScalarMappable(norm, colormaps["Blues"]),
            ax=ax,
            label="Publications",
            shrink=0.6,
        )
        ax.set_aspect("equal")
        ax.axis("off")

    figure(
        "world_map_publications_top20",
        "Publications by country",
        bool(top),
        draw,
        "Missing affiliation countries",
    )


def _widgets(out, docs, terms, status):
    import plotly.graph_objects as go
    from wordcloud import WordCloud
    from xml.etree import ElementTree as ET

    links = Counter()
    for left, right in [("terms", "institutions"), ("institutions", "countries")]:
        top_a = dict(_rank(docs, left).most_common(20))
        top_b = dict(_rank(docs, right).most_common(20))
        for d in docs:
            links.update(
                ((left, a), (right, b))
                for a, b in product(d[left], d[right])
                if a in top_a and b in top_b
            )
    nodes = sorted({node for edge in links for node in edge})
    idx = {n: i for i, n in enumerate(nodes)}
    sankey = go.Sankey(
        node=dict(label=[n[1] for n in nodes]),
        link=dict(
            source=[idx[a] for a, b in links],
            target=[idx[b] for a, b in links],
            value=list(links.values()),
        ),
    )
    tree = terms.head(50)
    for name, trace, available in [
        ("sankey_plot_ID_AUUN_AUCO", sankey, links),
        (
            "keywords_treemap_top50",
            go.Treemap(
                labels=list(tree.index), parents=[""] * len(tree), values=list(tree)
            ),
            len(tree),
        ),
    ]:
        path = out / (name + ".html")
        if available:
            go.Figure(trace).write_html(path, include_plotlyjs=True)
        else:
            path.unlink(missing_ok=True)
        status[path.name] = "generated" if available else "Insufficient field data"
    path = out / "keywords_wordcloud.html"
    if len(terms):
        cloud = WordCloud(
            width=900, height=600, background_color="white", random_state=42
        ).generate_from_frequencies(terms.to_dict())
        svg = ET.fromstring(cloud.to_svg())
        for node in svg.iter("{http://www.w3.org/2000/svg}text"):
            ET.SubElement(
                node, "{http://www.w3.org/2000/svg}title"
            ).text = f"{node.text}: {terms[node.text]}"
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        path.write_text(
            "<!doctype html><title>Keyword frequencies</title>"
            + ET.tostring(svg, encoding="unicode"),
            encoding="utf-8",
        )
    else:
        path.unlink(missing_ok=True)
    status[path.name] = (
        "generated" if len(terms) else "Missing keywords or publication years"
    )
