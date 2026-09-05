"""
Filter LLM Responses for Relevant Papers

This module filters LLM-classified papers using configurable SQL criteria (DuckDB),
then generates filtered JSON and BibTeX outputs with accurate entry matching.

The script bridges LLM classification and downstream analysis by extracting papers 
that meet researcher-defined relevance thresholds.

Main Features:
    - Load configuration from .conf file and YAML filter
    - Filter JSON data using DuckDB with SQL WHERE clause
    - Match filtered records to BibTeX entries (DOI → Title → ID hierarchy)
    - Generate filtered JSON and BibTeX outputs
    - Comprehensive statistics reporting

Usage:
    # As a module
    from src.FilterRelevantPapers import filter_relevant_papers
    success = filter_relevant_papers()
    
    # Via CLI
    uv run python aneta.py --filter_relevant_papers

Configuration Files:
    - .conf: Environment variables (PATH_DATA, BIB_FILE, etc.)
    - config/filter_accept_results_llm.yaml: SQL filter configuration

Author: ASRL Development Team
Date: October 21, 2025
"""

import os
import json
import re
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

import yaml
import duckdb
import pandas as pd
from dotenv import load_dotenv

from src.BibTex import read_bibtex, write_bibtex


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class FilterConfig:
    """
    Configuration container for filter operations.
    
    Attributes:
        path_data: Base path for data directory
        bib_file_path: Path to source BibTeX file
        json_input_path: Path to input JSON file (LLM responses)
        json_output_path: Path to output JSON file (filtered)
        bib_output_path: Path to output BibTeX file (matched entries)
        unrelevant_output_path: Path to output JSON file (unrelevant papers)
        yaml_filter_path: Path to YAML configuration with SQL filter
        filter_clause: SQL WHERE clause extracted from YAML
        markdown_report_path: Path to Markdown execution report
        markdown_report_path: Path to Markdown execution report
    """
    path_data: str
    bib_file_path: str
    json_input_path: str
    json_output_path: str
    bib_output_path: str
    unrelevant_output_path: str
    yaml_filter_path: str
    filter_clause: str = ""
    markdown_report_path: str = ""
    selection_decisions_path: str = ""


@dataclass
class MatchingStats:
    """
    Statistics for entry matching operations.
    
    Attributes:
        total_filtered: Total records after filtering
        matched_doi: Number of DOI matches
        matched_title: Number of Title matches
        matched_id: Number of ID matches
        unmatched: Number of unmatched records
        unmatched_entries: List of unmatched record details
    """
    total_filtered: int = 0
    matched_doi: int = 0
    matched_title: int = 0
    matched_id: int = 0
    unmatched: int = 0
    unmatched_entries: List[Dict[str, str]] = field(default_factory=list)


# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

def load_configuration() -> FilterConfig:
    """
    Load configuration from .conf file and construct file paths.
    
    Follows the project pattern for path construction:
    - Load PATH_DATA from environment
    - Append .bibs to create base path
    - Replace .bibs with actual file paths
    
    Returns:
        FilterConfig: Configuration object with all paths
        
    Raises:
        FileNotFoundError: If .conf file is not found
        KeyError: If required environment variables are missing
        Exception: For other configuration errors
    """
    # Load environment variables from .conf file
    conf_path = os.path.abspath(".conf")
    if not os.path.exists(conf_path):
        raise FileNotFoundError(f"Configuration file not found: {conf_path}")
    
    load_dotenv(conf_path)
    
    # Extract required configuration variables
    required_vars = {
        "PATH_DATA": os.getenv("PATH_DATA"),
        "BIB_FILE": os.getenv("BIB_FILE"),
        "FILTER_LLM_RESPONSES_ABSTRACT_PATH": os.getenv("FILTER_LLM_RESPONSES_ABSTRACT_PATH"),
        "RELEVANT_ABSTRACT_PAPERS_OUTPUT": os.getenv("RELEVANT_ABSTRACT_PAPERS_OUTPUT"),
        "RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT": os.getenv("RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT"),
        "UNRELEVANT_ABSTRACT_PAPERS_OUTPUT": os.getenv("UNRELEVANT_ABSTRACT_PAPERS_OUTPUT"),
        "FILTER_LLM_CONFIG_PATH": os.getenv("FILTER_LLM_CONFIG_PATH")
    }
    
    # Validate all required variables are present
    missing_vars = [key for key, value in required_vars.items() if value is None]
    if missing_vars:
        raise KeyError(f"Missing required environment variables in .conf: {', '.join(missing_vars)}")
    
    # Construct paths following project pattern
    path_data = os.path.abspath(required_vars["PATH_DATA"])
    path_data = os.path.join(path_data, ".bibs")
    
    # Construct file paths using .replace(".bibs", ...) pattern
    bib_file_path = path_data.replace(".bibs", required_vars["BIB_FILE"])
    json_input_path = path_data.replace(".bibs", required_vars["FILTER_LLM_RESPONSES_ABSTRACT_PATH"])
    json_output_path = path_data.replace(".bibs", required_vars["RELEVANT_ABSTRACT_PAPERS_OUTPUT"])
    bib_output_path = path_data.replace(".bibs", required_vars["RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT"])
    unrelevant_output_path = path_data.replace(".bibs", required_vars["UNRELEVANT_ABSTRACT_PAPERS_OUTPUT"])
    yaml_filter_path = os.path.abspath(required_vars["FILTER_LLM_CONFIG_PATH"])
    markdown_report_path = os.path.splitext(json_output_path)[0] + "_report.md"

    # Selection decisions Excel path: optional env override, otherwise defaults to the
    # same directory as the relevant-papers JSON. Keeps the .conf change non-mandatory.
    decisions_env = os.getenv("SELECTION_DECISIONS_EXCEL_OUTPUT")
    if decisions_env:
        selection_decisions_path = path_data.replace(".bibs", decisions_env)
    else:
        selection_decisions_path = os.path.join(
            os.path.dirname(json_output_path), "selection_decisions.xlsx"
        )

    # Load SQL filter from YAML
    filter_clause = load_yaml_filter(yaml_filter_path)

    # Create and return configuration object
    config = FilterConfig(
        path_data=path_data,
        bib_file_path=bib_file_path,
        json_input_path=json_input_path,
        json_output_path=json_output_path,
        bib_output_path=bib_output_path,
        unrelevant_output_path=unrelevant_output_path,
        yaml_filter_path=yaml_filter_path,
        filter_clause=filter_clause,
        markdown_report_path=markdown_report_path,
        selection_decisions_path=selection_decisions_path
    )
    
    return config


def load_yaml_filter(yaml_path: str) -> str:
    """
    Load SQL WHERE clause from YAML configuration file.
    
    Args:
        yaml_path: Path to YAML file containing filter configuration
        
    Returns:
        str: SQL WHERE clause extracted from YAML
        
    Raises:
        FileNotFoundError: If YAML file is not found
        KeyError: If 'filter' key is not in YAML
        yaml.YAMLError: If YAML parsing fails
    """
    # Validate file exists
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"YAML filter configuration not found: {yaml_path}")
    
    try:
        # Load YAML file
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
        
        # Validate 'filter' key exists
        if yaml_config is None or "filter" not in yaml_config:
            raise KeyError(f"'filter' key not found in YAML configuration: {yaml_path}")
        
        # Extract and clean filter clause
        filter_clause = yaml_config["filter"]
        
        # Remove extra whitespace and newlines for SQL execution
        filter_clause = filter_clause.replace("\n", " ").replace("\t", " ")
        # Normalize multiple spaces
        while "  " in filter_clause:
            filter_clause = filter_clause.replace("  ", " ")
        filter_clause = filter_clause.strip()
        
        return filter_clause
        
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error parsing YAML file {yaml_path}: {e}")


def construct_paths(path_data: str, bib_file: str, json_input: str, 
                    json_output: str, bib_output: str) -> Tuple[str, str, str, str]:
    """
    Construct absolute paths following project pattern.
    
    Pattern: path.replace(".bibs", relative_path)
    
    Args:
        path_data: Base data path with .bibs suffix
        bib_file: Relative path to BibTeX file
        json_input: Relative path to input JSON
        json_output: Relative path to output JSON
        bib_output: Relative path to output BibTeX
        
    Returns:
        Tuple[str, str, str, str]: Absolute paths (bib, json_in, json_out, bib_out)
    """
    # Apply project pattern: replace .bibs with relative paths
    bib_path = path_data.replace(".bibs", bib_file)
    json_in_path = path_data.replace(".bibs", json_input)
    json_out_path = path_data.replace(".bibs", json_output)
    bib_out_path = path_data.replace(".bibs", bib_output)
    
    # Convert to absolute paths
    bib_path = os.path.abspath(bib_path)
    json_in_path = os.path.abspath(json_in_path)
    json_out_path = os.path.abspath(json_out_path)
    bib_out_path = os.path.abspath(bib_out_path)
    
    return bib_path, json_in_path, json_out_path, bib_out_path


# ============================================================================
# DATA LOADING
# ============================================================================

def load_json_data(json_path: str) -> List[Dict]:
    """
    Load LLM response data from JSON file.
    
    Args:
        json_path: Path to JSON file
        
    Returns:
        List[Dict]: List of JSON records
        
    Raises:
        FileNotFoundError: If JSON file is not found
        json.JSONDecodeError: If JSON is malformed
        ValueError: If JSON is not an array
    """
    # Validate file exists
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    
    try:
        # Load JSON file with UTF-8 encoding
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Validate data is a list
        if not isinstance(data, list):
            raise ValueError(f"JSON data must be an array, got {type(data).__name__}")
        
        # Validate all items are dictionaries
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(f"JSON array item at index {i} must be an object, got {type(item).__name__}")
        
        return data
        
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Malformed JSON in file {json_path}: {e.msg}",
            e.doc,
            e.pos
        )
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    
    try:
        # Load JSON file with UTF-8 encoding
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Validate data is a list
        if not isinstance(data, list):
            raise ValueError(f"JSON file must contain an array, got {type(data).__name__}: {json_path}")
        
        # Log number of records loaded
        print(f"  - Loaded {len(data)} records from JSON")
        
        return data
        
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Malformed JSON in file {json_path}: {e.msg}",
            e.doc,
            e.pos
        )


def load_bibtex_data(bib_path: str) -> List[Dict]:
    """
    Load BibTeX entries using project utility.
    
    Args:
        bib_path: Path to BibTeX file
        
    Returns:
        List[Dict]: List of BibTeX entries
        
    Raises:
        FileNotFoundError: If BibTeX file is not found
        Exception: If BibTeX parsing fails
    """
    # Validate file exists
    if not os.path.exists(bib_path):
        raise FileNotFoundError(f"BibTeX file not found: {bib_path}")
    
    try:
        # Use project utility to read BibTeX
        # read_bibtex handles encoding issues (UTF-8 with chardet fallback)
        entries = read_bibtex(bib_path)
        
        # Validate entries is a list
        if not isinstance(entries, list):
            raise Exception(f"BibTeX parser returned invalid type: {type(entries).__name__}")
        
        return entries
        
    except Exception as e:
        # Re-raise with context if not already a FileNotFoundError
        if isinstance(e, FileNotFoundError):
            raise
        raise Exception(f"Error parsing BibTeX file {bib_path}: {e}")
    if not os.path.exists(bib_path):
        raise FileNotFoundError(f"BibTeX file not found: {bib_path}")
    
    try:
        # Use project utility to read BibTeX
        # read_bibtex() already handles encoding (UTF-8 with chardet fallback)
        bibtex_entries = read_bibtex(bib_path)
        
        # Validate entries loaded
        if not isinstance(bibtex_entries, list):
            raise ValueError(f"Expected list of entries, got {type(bibtex_entries).__name__}")
        
        # Log number of entries loaded
        print(f"  - Loaded {len(bibtex_entries)} entries from BibTeX")
        
        return bibtex_entries
        
    except Exception as e:
        raise Exception(f"Error loading BibTeX file {bib_path}: {e}")


# ============================================================================
# FILTERING
# ============================================================================

def apply_duckdb_filter(data: List[Dict], filter_clause: str) -> Tuple[List[Dict], List[Dict]]:
    """
    Execute SQL filter on data using in-memory DuckDB.
    
    Follows pattern from src/Selection.py:
    - Convert data to DataFrame
    - Register as DuckDB table
    - Execute SQL query with WHERE clause
    - Return filtered records AND unrelevant records
    
    Args:
        data: List of dictionaries to filter
        filter_clause: SQL WHERE clause
        
    Returns:
        Tuple[List[Dict], List[Dict]]: Tuple containing (relevant records, unrelevant records)
        
    Raises:
        duckdb.Error: If SQL syntax is invalid
        Exception: For other database errors
    """
    # Validate input data
    if not data:
        print("Warning: Empty data list provided to filter")
        return [], []
    
    try:
        # Convert list of dictionaries to Pandas DataFrame
        df = pd.DataFrame(data)
        
        # Create in-memory DuckDB connection
        conn = duckdb.connect(':memory:')
        
        # Register DataFrame as DuckDB table
        conn.register('filter_table', df)
        
        # Build SQL query with WHERE clause for RELEVANT papers
        query_relevant = f"""
            SELECT 
                * 
            FROM 
                filter_table
            WHERE 
                {filter_clause}
        """
        
        # Build SQL query with WHERE clause for UNRELEVANT papers (negated condition)
        query_unrelevant = f"""
            SELECT 
                * 
            FROM 
                filter_table
            WHERE 
                NOT ({filter_clause})
        """
        
        # Normalize queries (remove extra whitespace)
        query_relevant = query_relevant.replace("\n", " ").replace("\t", " ")
        while "  " in query_relevant:
            query_relevant = query_relevant.replace("  ", " ")
        query_relevant = query_relevant.strip()
        
        query_unrelevant = query_unrelevant.replace("\n", " ").replace("\t", " ")
        while "  " in query_unrelevant:
            query_unrelevant = query_unrelevant.replace("  ", " ")
        query_unrelevant = query_unrelevant.strip()
        
        # Execute queries and fetch results as DataFrames
        result_relevant_df = conn.execute(query_relevant).fetchdf()
        result_unrelevant_df = conn.execute(query_unrelevant).fetchdf()
        
        # Close connection
        conn.close()
        
        # Convert DataFrames back to list of dictionaries
        filtered_records = result_relevant_df.to_dict('records')
        unrelevant_records = result_unrelevant_df.to_dict('records')
        
        return filtered_records, unrelevant_records
        
    except duckdb.Error as e:
        # SQL syntax or execution error
        raise duckdb.Error(f"DuckDB SQL error: {e}\nFilter clause: {filter_clause}")
    except Exception as e:
        # Other errors (DataFrame conversion, etc.)
        raise Exception(f"Error applying DuckDB filter: {e}")


# ============================================================================
# PER-ARTICLE DECISION + EVIDENCE (derived from the SQL filter clause)
# ============================================================================

# Atomic comparison inside a SQL clause: "column OP number" (e.g. is_relevant_yes_percent >= 65).
# Used ONLY to LOCATE predicates for display — evaluation is always done by DuckDB.
_PREDICATE_RE = re.compile(r'([A-Za-z_]\w*)\s*(>=|<=|!=|<>|=|>|<)\s*(\d+(?:\.\d+)?)')


def _fmt_value(value: object) -> str:
    """Format a score value for the human-readable reason (10.0 -> '10', 66.67 -> '66.67')."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def extract_predicates(filter_clause: str, known_columns) -> List[Tuple[str, str, str]]:
    """
    Locate the atomic ``column OP number`` comparisons inside the SQL filter clause.

    The match is validated against the real consolidated columns so arbitrary tokens
    (function names, literals) are never mistaken for columns. Order and duplicates of
    the clause are preserved (first occurrence wins) so the reason reads like the filter.

    Args:
        filter_clause: SQL WHERE clause from the YAML configuration.
        known_columns: Iterable with the column names available in the consolidated data.

    Returns:
        List of (column, operator, number) tuples, in clause order, de-duplicated.
    """
    known = set(known_columns)
    predicates: List[Tuple[str, str, str]] = []
    seen = set()
    for column, operator, number in _PREDICATE_RE.findall(filter_clause):
        if column not in known:
            continue
        key = (column, operator, number)
        if key in seen:
            continue
        seen.add(key)
        predicates.append((column, operator, number))
    return predicates


def build_selection_reason(record: Dict, predicates: List[Tuple[str, str, str]],
                           predicate_results: List[bool], selected: bool,
                           filter_clause: str = "") -> str:
    """
    Build the human-readable motivation for a single article's decision.

    The reason is derived from the filter clause itself: each atomic threshold is shown
    with the article's actual value and a PASS/FAIL mark, so it always mirrors the
    current YAML configuration. When the clause has no atomic ``column OP number``
    predicates (e.g. only function calls), it falls back to the literal clause.

    Args:
        record: Consolidated record (carries the score columns).
        predicates: Atomic predicates located by :func:`extract_predicates`.
        predicate_results: Booleans for each predicate, evaluated by DuckDB.
        selected: Final decision for the article (the full clause result).
        filter_clause: Original clause, used only for the no-predicate fallback.

    Returns:
        A string such as ``"SELECIONADO — is_relevant_yes_percent=80 (>=65 ✓) · ..."``.
    """
    prefix = "SELECIONADO" if selected else "REJEITADO"
    parts: List[str] = []
    for (column, operator, number), passed in zip(predicates, predicate_results):
        value = record.get(column, "N/A")
        mark = "✓" if passed else "✗"
        parts.append(f"{column}={_fmt_value(value)} ({operator}{number} {mark})")
    if parts:
        return f"{prefix} — " + " · ".join(parts)
    return f"{prefix} — (filtro: {filter_clause.strip()})"


def annotate_with_decision(data: List[Dict], filter_clause: str) -> List[Dict]:
    """
    Annotate every consolidated record with its decision and motivation.

    DuckDB evaluates the full clause (``_selected``) and each atomic predicate in a
    single query; this function only formats those results into a reason string. The
    original record dicts are preserved (no DataFrame round-trip) and gain two keys:
    ``_selected`` (bool) and ``_selection_reason`` (str).

    Args:
        data: List of consolidated records (LLM scores by article).
        filter_clause: SQL WHERE clause from the YAML configuration.

    Returns:
        The same records (new list, same dict objects) with ``_selected`` and
        ``_selection_reason`` added.

    Raises:
        duckdb.Error: If the clause references unknown columns or is invalid SQL.
    """
    if not data:
        return []

    # Build a DataFrame with a stable index so we can map results back to the originals.
    df = pd.DataFrame(data)
    df.insert(0, "_orig_idx", range(len(df)))
    known_columns = [c for c in df.columns if c != "_orig_idx"]
    predicates = extract_predicates(filter_clause, known_columns)

    try:
        conn = duckdb.connect(":memory:")
        conn.register("filter_table", df)

        # One query: decision + each atomic predicate, all evaluated natively by DuckDB.
        predicate_select = "".join(
            f", ({column} {operator} {number}) AS _pred_{i}"
            for i, (column, operator, number) in enumerate(predicates)
        )
        query = (
            f"SELECT _orig_idx, ({filter_clause}) AS _selected{predicate_select} "
            f"FROM filter_table"
        )
        result_df = conn.execute(query).fetchdf()
        conn.close()
    except duckdb.Error as e:
        raise duckdb.Error(f"DuckDB SQL error: {e}\nFilter clause: {filter_clause}")

    annotated: List[Dict] = []
    for _, row in result_df.iterrows():
        idx = int(row["_orig_idx"])
        record = data[idx]
        selected = bool(row["_selected"]) if row["_selected"] is not None else False
        predicate_results = [bool(row[f"_pred_{i}"]) for i in range(len(predicates))]
        record["_selected"] = selected
        record["_selection_reason"] = build_selection_reason(
            record, predicates, predicate_results, selected, filter_clause
        )
        annotated.append(record)

    return annotated


# ============================================================================
# ENTRY MATCHING
# ============================================================================

def normalize_doi(doi: str) -> str:
    """
    Normalize DOI for matching (lowercase, strip whitespace).
    
    Normalization steps:
    - Strip leading/trailing whitespace
    - Convert to lowercase
    - Remove common prefixes (https://doi.org/, http://dx.doi.org/, doi:)
    
    Args:
        doi: DOI string to normalize
        
    Returns:
        str: Normalized DOI (empty string if input is None or empty)
    
    Examples:
        >>> normalize_doi('10.1234/EXAMPLE')
        '10.1234/example'
        >>> normalize_doi('  https://doi.org/10.1234/example  ')
        '10.1234/example'
        >>> normalize_doi('DOI: 10.1234/example')
        '10.1234/example'
    """
    if not doi:
        return ""
    
    # Strip whitespace and convert to lowercase
    normalized = doi.strip().lower()
    
    # Remove common DOI prefixes
    prefixes = ['https://doi.org/', 'http://doi.org/', 'http://dx.doi.org/', 'https://dx.doi.org/', 'doi:']
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    
    # Final cleanup
    normalized = normalized.strip()
    
    return normalized


def normalize_title(title: str) -> str:
    """
    Normalize title for matching (remove punctuation, normalize spaces).
    
    Normalization steps:
    - Strip leading/trailing whitespace
    - Convert to lowercase
    - Remove all punctuation (except spaces)
    - Normalize multiple spaces to single space
    - Remove common LaTeX commands and special characters
    
    Args:
        title: Title string to normalize
        
    Returns:
        str: Normalized title (empty string if input is None or empty)
    
    Examples:
        >>> normalize_title('The Quick Brown Fox!')
        'the quick brown fox'
        >>> normalize_title('Title: With -- Special Characters...')
        'title with special characters'
        >>> normalize_title('  Multiple   Spaces  ')
        'multiple spaces'
    """
    if not title:
        return ""
    
    # Strip whitespace and convert to lowercase
    normalized = title.strip().lower()
    
    # Remove common LaTeX commands
    normalized = re.sub(r'\\[a-z]+\{([^}]*)\}', r'\1', normalized)
    normalized = re.sub(r'\\[a-z]+', '', normalized)
    
    # Remove all punctuation except spaces
    # Keep only alphanumeric characters and spaces
    normalized = re.sub(r'[^a-z0-9\s]', ' ', normalized)
    
    # Normalize multiple spaces to single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Final cleanup
    normalized = normalized.strip()
    
    return normalized


def match_bibtex_entries(filtered_json: List[Dict], 
                        bibtex_entries: List[Dict]) -> Tuple[List[Dict], MatchingStats]:
    """
    Match filtered JSON records to BibTeX entries using three-tier hierarchy.
    
    Matching Strategy:
        1. Primary: DOI matching (normalized, case-insensitive)
        2. Secondary: Title matching (normalized, punctuation removed)
        3. Tertiary: BibTeX ID matching (exact)
    
    The function uses optimized lookup dictionaries for O(n) complexity.
    Unmatched entries are tracked with details for debugging.
    
    Args:
        filtered_json: List of filtered JSON records
        bibtex_entries: List of BibTeX entries to match against
        
    Returns:
        Tuple[List[Dict], MatchingStats]: 
            - List of matched BibTeX entries (maintains order from filtered_json)
            - Statistics object with matching details
    
    Examples:
        >>> json_records = [{'doi': '10.1234/example', 'title': 'Test Paper'}]
        >>> bib_entries = [{'ID': 'paper1', 'doi': '10.1234/EXAMPLE', 'title': 'Test Paper'}]
        >>> matched, stats = match_bibtex_entries(json_records, bib_entries)
        >>> stats.matched_doi
        1
    """
    # Initialize statistics
    stats = MatchingStats(total_filtered=len(filtered_json))
    matched_entries: List[Dict] = []
    
    # Handle empty inputs
    if not filtered_json:
        print("Warning: No filtered records to match")
        return matched_entries, stats
    
    if not bibtex_entries:
        print("Warning: No BibTeX entries available for matching")
        stats.unmatched = len(filtered_json)
        # Track all as unmatched
        for record in filtered_json:
            stats.unmatched_entries.append({
                'id': record.get('id', 'N/A'),
                'doi': record.get('doi', 'N/A'),
                'title': record.get('article_title', record.get('title', 'N/A'))
            })
        return matched_entries, stats
    
    # Build lookup dictionaries for performance (O(n) complexity)
    # DOI lookup: normalized_doi -> BibTeX entry
    doi_lookup: Dict[str, Dict] = {}
    for bib in bibtex_entries:
        doi = bib.get('doi', '')
        if doi:
            normalized_doi = normalize_doi(doi)
            if normalized_doi:
                # Store first occurrence (avoid duplicates)
                if normalized_doi not in doi_lookup:
                    doi_lookup[normalized_doi] = bib
    
    # Title lookup: normalized_title -> BibTeX entry
    title_lookup: Dict[str, Dict] = {}
    for bib in bibtex_entries:
        title = bib.get('title', '')
        if title:
            normalized_title = normalize_title(title)
            if normalized_title:
                # Store first occurrence
                if normalized_title not in title_lookup:
                    title_lookup[normalized_title] = bib
    
    # ID lookup: exact ID -> BibTeX entry
    id_lookup: Dict[str, Dict] = {}
    for bib in bibtex_entries:
        bib_id = bib.get('ID', '')
        if bib_id:
            # Exact match (case-sensitive for IDs)
            if bib_id not in id_lookup:
                id_lookup[bib_id] = bib
    
    # Track matched BibTeX entries to avoid duplicates
    matched_bib_ids = set()
    
    # Match each JSON record using three-tier hierarchy
    for record in filtered_json:
        matched_entry = None
        match_method = None
        
        # Strategy 1: Try DOI matching (PRIMARY)
        doi = record.get('doi', '')
        if doi:
            normalized_doi = normalize_doi(doi)
            if normalized_doi and normalized_doi in doi_lookup:
                matched_entry = doi_lookup[normalized_doi]
                match_method = 'doi'
                stats.matched_doi += 1
        
        # Strategy 2: Try Title matching (SECONDARY)
        if not matched_entry:
            title = record.get('article_title', record.get('title', ''))
            if title:
                normalized_title = normalize_title(title)
                if normalized_title and normalized_title in title_lookup:
                    matched_entry = title_lookup[normalized_title]
                    match_method = 'title'
                    stats.matched_title += 1
        
        # Strategy 3: Try ID matching (TERTIARY)
        if not matched_entry:
            record_id = record.get('id', '')
            if record_id and record_id in id_lookup:
                matched_entry = id_lookup[record_id]
                match_method = 'id'
                stats.matched_id += 1
        
        # Handle matched entry
        if matched_entry:
            # Check for duplicate matches (same BibTeX entry matched multiple times)
            bib_id = matched_entry.get('ID', '')
            if bib_id and bib_id not in matched_bib_ids:
                matched_entries.append(matched_entry)
                matched_bib_ids.add(bib_id)
            elif not bib_id:
                # BibTeX entry without ID (rare, but possible)
                matched_entries.append(matched_entry)
        else:
            # Track unmatched entry
            stats.unmatched += 1
            stats.unmatched_entries.append({
                'id': record.get('id', 'N/A'),
                'doi': record.get('doi', 'N/A'),
                'title': record.get('article_title', record.get('title', 'N/A'))
            })
    
    return matched_entries, stats


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def write_filtered_outputs(filtered_json: List[Dict], matched_bibtex: List[Dict],
                          json_path: str, bib_path: str, 
                          unrelevant_json: Optional[List[Dict]] = None,
                          unrelevant_path: Optional[str] = None) -> None:
    """
    Write filtered JSON and matched BibTeX entries to files.
    
    Creates parent directories if needed. Uses UTF-8 encoding for both formats.
    JSON output is pretty-printed with indent=2 for readability.
    
    Args:
        filtered_json: Filtered JSON records to write (relevant papers)
        matched_bibtex: Matched BibTeX entries to write
        json_path: Output path for JSON file (relevant papers)
        bib_path: Output path for BibTeX file
        unrelevant_json: Optional unrelevant JSON records to write
        unrelevant_path: Optional output path for unrelevant JSON file
        
    Raises:
        OSError: If file creation fails (disk space, invalid path, etc.)
        PermissionError: If write permission denied
        Exception: For other write errors
        
    Examples:
        >>> filtered = [{'id': '1', 'title': 'Paper 1'}]
        >>> bibtex = [{'ID': 'paper1', 'title': 'Paper 1'}]
        >>> write_filtered_outputs(filtered, bibtex, 'out.json', 'out.bib')
    """
    # Step 1: Create parent directories for JSON output if needed
    json_dir = os.path.dirname(json_path)
    if json_dir and not os.path.exists(json_dir):
        try:
            os.makedirs(json_dir, exist_ok=True)
            print(f"  - Created directory: {json_dir}")
        except OSError as e:
            raise OSError(f"Failed to create directory for JSON output {json_dir}: {e}")
        except PermissionError as e:
            raise PermissionError(f"Permission denied creating directory {json_dir}: {e}")
    
    # Step 2: Create parent directories for BibTeX output if needed
    bib_dir = os.path.dirname(bib_path)
    if bib_dir and not os.path.exists(bib_dir):
        try:
            os.makedirs(bib_dir, exist_ok=True)
            print(f"  - Created directory: {bib_dir}")
        except OSError as e:
            raise OSError(f"Failed to create directory for BibTeX output {bib_dir}: {e}")
        except PermissionError as e:
            raise PermissionError(f"Permission denied creating directory {bib_dir}: {e}")
    
    # Step 3: Write filtered JSON to output file
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(
                filtered_json,
                f,
                ensure_ascii=False,  # Preserve Unicode characters
                indent=2,            # Pretty-print with 2-space indentation
                sort_keys=False      # Preserve original key order
            )
        
        print(f"  - JSON output written: {json_path} ({len(filtered_json)} records)")
        
    except PermissionError as e:
        raise PermissionError(f"Permission denied writing JSON file {json_path}: {e}")
    except OSError as e:
        raise OSError(f"Failed to write JSON file {json_path}: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error writing JSON file {json_path}: {e}")
    
    # Step 4: Write matched BibTeX entries to output file
    try:
        # Use project utility for BibTeX output
        # write_bibtex() handles encoding (UTF-8) and proper BibTeX formatting
        # Signature: write_bibtex(path, entries)
        write_bibtex(bib_path, matched_bibtex)
        
        print(f"  - BibTeX output written: {bib_path} ({len(matched_bibtex)} entries)")
        
    except PermissionError as e:
        raise PermissionError(f"Permission denied writing BibTeX file {bib_path}: {e}")
    except OSError as e:
        raise OSError(f"Failed to write BibTeX file {bib_path}: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error writing BibTeX file {bib_path}: {e}")
    
    # Step 5: Validate files were created successfully
    if not os.path.exists(json_path):
        raise OSError(f"JSON output file was not created: {json_path}")
    
    if not os.path.exists(bib_path):
        raise OSError(f"BibTeX output file was not created: {bib_path}")
    
    # Step 6: Validate file sizes (files should not be empty if data was provided)
    if filtered_json and os.path.getsize(json_path) == 0:
        raise OSError(f"JSON output file is empty despite having data: {json_path}")
    
    if matched_bibtex and os.path.getsize(bib_path) == 0:
        raise OSError(f"BibTeX output file is empty despite having data: {bib_path}")
    
    # Step 7: Write unrelevant papers if provided
    if unrelevant_json is not None and unrelevant_path is not None:
        # Create parent directory for unrelevant output if needed
        unrelevant_dir = os.path.dirname(unrelevant_path)
        if unrelevant_dir and not os.path.exists(unrelevant_dir):
            try:
                os.makedirs(unrelevant_dir, exist_ok=True)
                print(f"  - Created directory: {unrelevant_dir}")
            except OSError as e:
                raise OSError(f"Failed to create directory for unrelevant output {unrelevant_dir}: {e}")
            except PermissionError as e:
                raise PermissionError(f"Permission denied creating directory {unrelevant_dir}: {e}")
        
        # Write unrelevant JSON to output file
        try:
            with open(unrelevant_path, 'w', encoding='utf-8') as f:
                json.dump(
                    unrelevant_json,
                    f,
                    ensure_ascii=False,  # Preserve Unicode characters
                    indent=2,            # Pretty-print with 2-space indentation
                    sort_keys=False      # Preserve original key order
                )
            
            print(f"  - Unrelevant JSON output written: {unrelevant_path} ({len(unrelevant_json)} records)")
            
        except PermissionError as e:
            raise PermissionError(f"Permission denied writing unrelevant JSON file {unrelevant_path}: {e}")
        except OSError as e:
            raise OSError(f"Failed to write unrelevant JSON file {unrelevant_path}: {e}")
        except Exception as e:
            raise Exception(f"Unexpected error writing unrelevant JSON file {unrelevant_path}: {e}")
        
        # Validate unrelevant file was created successfully
        if not os.path.exists(unrelevant_path):
            raise OSError(f"Unrelevant JSON output file was not created: {unrelevant_path}")
        
        # Validate file size
        if unrelevant_json and os.path.getsize(unrelevant_path) == 0:
            raise OSError(f"Unrelevant JSON output file is empty despite having data: {unrelevant_path}")


def _load_questions_legend(yaml_filter_path: str) -> Optional[Dict[str, str]]:
    """
    Best-effort load of the research-questions legend for the decision spreadsheet.

    Looks for ``config/research_questions.yaml`` (relative to the project root inferred
    from the filter YAML path). Any failure returns ``None`` so the Excel is still
    generated without the legend sheet.
    """
    try:
        from src.GenerativeAI.LLMUtilExcel import read_research_questions
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(yaml_filter_path)))
        candidates = [
            os.path.join(project_root, "config", "research_questions.yaml"),
            os.path.join(project_root, "Config", "research_questions.yaml"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return read_research_questions(path)
    except Exception:
        return None
    return None


def write_decision_excel(annotated: List[Dict], output_path: str,
                         filter_clause: str, predicates: List[Tuple[str, str, str]],
                         questions: Optional[Dict[str, str]] = None) -> None:
    """
    Write the selection-decision spreadsheet with full evidence per article.

    Sheets:
        - ``Decisão``: every article (scores + ``selecionado`` + ``motivo``), sortable.
        - ``Selecionados`` / ``Rejeitados``: the two groups split for quick reading.
        - ``Critério``: the SQL clause applied and generation timestamp (audit trail).
        - ``Research Questions``: legend (when available).

    Columns are ordered as: id, doi, article_title, selecionado, motivo, then the
    columns referenced by the filter (the ones that justify the decision), then the
    remaining score columns. The long ``article_abstract``/``article_keywords`` fields
    are omitted here (they remain in the consolidated scores spreadsheet).

    Args:
        annotated: Records carrying ``_selected`` and ``_selection_reason``.
        output_path: Destination ``.xlsx`` path.
        filter_clause: SQL clause applied (for the ``Critério`` sheet).
        predicates: Atomic predicates located in the clause (drive column ordering).
        questions: Optional research-questions legend.
    """
    if not annotated:
        print("  ⚠ Nenhum dado para gerar a planilha de decisão")
        return

    from openpyxl.utils import get_column_letter

    drop_cols = {"_selected", "_selection_reason", "article_abstract", "article_keywords"}
    referenced = []
    for column, _, _ in predicates:
        if column not in referenced:
            referenced.append(column)

    # Build display rows: map internal flags to friendly columns, drop noisy fields.
    rows: List[Dict] = []
    for record in annotated:
        row = {k: v for k, v in record.items() if k not in drop_cols}
        row["selecionado"] = "sim" if record.get("_selected") else "não"
        row["motivo"] = record.get("_selection_reason", "")
        rows.append(row)

    df = pd.DataFrame(rows)

    # Column ordering: identity, decision, referenced (justifying) columns, then the rest.
    front = [c for c in ["id", "doi", "article_title", "selecionado", "motivo",
                         "total_responses", "providers", "models"] if c in df.columns]
    ref_present = [c for c in referenced if c in df.columns and c not in front]
    rest = sorted(c for c in df.columns if c not in front and c not in ref_present)
    ordered = front + ref_present + rest
    df = df[ordered]

    # Ensure parent directory exists.
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    selected_df = df[df["selecionado"] == "sim"] if "selecionado" in df.columns else df
    rejected_df = df[df["selecionado"] == "não"] if "selecionado" in df.columns else df

    criterio_df = pd.DataFrame({
        "campo": ["filtro_sql", "gerado_em", "total_artigos", "selecionados", "rejeitados"],
        "valor": [
            filter_clause.strip(),
            datetime.now().isoformat(timespec="seconds"),
            len(df),
            int((df["selecionado"] == "sim").sum()) if "selecionado" in df.columns else 0,
            int((df["selecionado"] == "não").sum()) if "selecionado" in df.columns else 0,
        ],
    })

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Decisão", index=False)
        selected_df.to_excel(writer, sheet_name="Selecionados", index=False)
        rejected_df.to_excel(writer, sheet_name="Rejeitados", index=False)
        criterio_df.to_excel(writer, sheet_name="Critério", index=False)

        if questions:
            questions_df = pd.DataFrame({
                "question_id": list(questions.keys()),
                "question_text": list(questions.values()),
            })
            questions_df.to_excel(writer, sheet_name="Research Questions", index=False)

        # Auto-fit column widths (capped) for readability on the main sheet.
        worksheet = writer.sheets["Decisão"]
        for idx, col in enumerate(df.columns, 1):
            max_length = max(df[col].astype(str).apply(len).max(), len(str(col)))
            max_length = min(int(max_length), 60)
            worksheet.column_dimensions[get_column_letter(idx)].width = max_length + 2

    print(f"  ✓ Planilha de decisão criada: {output_path}")


# ============================================================================
# STATISTICS AND REPORTING
# ============================================================================

def build_markdown_report(input_count: int, filtered_count: int, unrelevant_count: int,
                          stats: MatchingStats, execution_time: float,
                          config: FilterConfig,
                          annotated: Optional[List[Dict]] = None) -> str:
    """Build the markdown execution report string.

    The markdown structure mirrors the console output to keep both
    representations consistent. Percentages are guarded against
    division-by-zero to avoid runtime errors.

    Args:
        input_count: Number of input records.
        filtered_count: Number of filtered records.
        unrelevant_count: Number of unrelevant records.
        stats: Matching statistics container.
        execution_time: Total execution time in seconds.
        config: Configuration object with paths and filter clause.

    Returns:
        Markdown-formatted string ready to be persisted.
    """
    # Step 1: Prepare helper computations for percentages.
    relevant_percentage = (filtered_count / input_count * 100) if input_count else 0.0
    unrelevant_percentage = (unrelevant_count / input_count * 100) if input_count else 0.0
    doi_pct = (stats.matched_doi / stats.total_filtered * 100) if stats.total_filtered else 0.0
    title_pct = (stats.matched_title / stats.total_filtered * 100) if stats.total_filtered else 0.0
    id_pct = (stats.matched_id / stats.total_filtered * 100) if stats.total_filtered else 0.0
    unmatched_pct = (stats.unmatched / stats.total_filtered * 100) if stats.total_filtered else 0.0
    matched_total = stats.matched_doi + stats.matched_title + stats.matched_id
    records_per_sec = (input_count / execution_time) if execution_time > 0 else 0.0

    # Step 2: Build markdown content incrementally.
    lines: List[str] = []
    lines.append("# Filter Relevant Papers - Execution Report")
    lines.append("")
    lines.append(f"Generated at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")

    # Configuration section.
    lines.append("## Configuration")
    lines.append(f"- Configuration file: `.conf`")
    lines.append(f"- Filter configuration: `{config.yaml_filter_path}`")
    lines.append(f"- SQL filter: `{config.filter_clause}`")
    lines.append("")

    # Input section.
    lines.append("## Input Data")
    lines.append(f"- JSON records loaded: **{input_count:,}**")
    lines.append(f"- JSON source file: `{config.json_input_path}`")
    lines.append(f"- BibTeX source file: `{config.bib_file_path}`")
    lines.append("")

    # Filtering section.
    lines.append("## Filtering Results")
    lines.append(f"- Relevant papers: **{filtered_count:,}** ({relevant_percentage:.1f}% of input)")
    lines.append(f"- Unrelevant papers: **{unrelevant_count:,}** ({unrelevant_percentage:.1f}% of input)")
    lines.append("")

    # Matching section.
    lines.append("## Entry Matching")
    if stats.total_filtered:
        lines.append(f"- DOI matches: **{stats.matched_doi:,}** ({doi_pct:.1f}%)")
        lines.append(f"- Title matches: **{stats.matched_title:,}** ({title_pct:.1f}%)")
        lines.append(f"- ID matches: **{stats.matched_id:,}** ({id_pct:.1f}%)")
        lines.append(f"- Total matched: **{matched_total:,}** ({100 - unmatched_pct:.1f}%)")
        lines.append(f"- Unmatched: **{stats.unmatched:,}** ({unmatched_pct:.1f}%)")

        if stats.unmatched_entries:
            lines.append("")
            lines.append("### Unmatched Entries (sample)")
            display_count = min(5, len(stats.unmatched_entries))
            for entry in stats.unmatched_entries[:display_count]:
                truncated_title = entry.get('title', 'N/A')
                if len(truncated_title) > 100:
                    truncated_title = truncated_title[:100].rstrip() + "..."
                lines.append(
                    f"- ID: `{entry.get('id', 'N/A')}` · DOI: `{entry.get('doi', 'N/A')}` · Title: {truncated_title}"
                )

            if len(stats.unmatched_entries) > display_count:
                lines.append(f"- ...and {len(stats.unmatched_entries) - display_count} more unmatched entries")
    else:
        lines.append("- No records to match (empty filter result)")
    lines.append("")

    # Output section.
    lines.append("## Output Files")
    lines.append(f"- Relevant JSON: `{config.json_output_path}` (records: {filtered_count:,})")
    lines.append(f"- Unrelevant JSON: `{config.unrelevant_output_path}` (records: {unrelevant_count:,})")
    lines.append(f"- BibTeX output: `{config.bib_output_path}` (entries: {matched_total:,})")
    lines.append(f"- Selection decisions Excel: `{config.selection_decisions_path}` (rows: {input_count:,})")
    lines.append(f"- Markdown report: `{config.markdown_report_path}`")
    lines.append("")

    # Performance section.
    lines.append("## Performance")
    lines.append(f"- Execution time: {execution_time:.3f} seconds")
    lines.append(f"- Processing speed: {records_per_sec:.0f} records/second")
    lines.append("")

    # Per-article evidence table (decision + derived motivation).
    if annotated:
        lines.append("## Per-Article Decision")
        lines.append("")
        lines.append("| ID | Title | Selected | Reason |")
        lines.append("|---|---|---|---|")
        for record in annotated:
            rec_id = str(record.get("id", "")) or str(record.get("_response_id", ""))
            title = str(record.get("article_title", "") or "")
            if len(title) > 80:
                title = title[:80].rstrip() + "…"
            selected = "yes" if record.get("_selected") else "no"
            # Escape pipes so the markdown table stays valid.
            reason = str(record.get("_selection_reason", "")).replace("|", "\\|")
            title = title.replace("|", "\\|")
            lines.append(f"| {rec_id} | {title} | {selected} | {reason} |")
        lines.append("")

    # Completion note.
    lines.append("✅ Filtering completed successfully.")

    # Step 3: Join lines with newline separators for final markdown.
    return "\n".join(lines)


def report_statistics(input_count: int, filtered_count: int, unrelevant_count: int,
                     stats: MatchingStats, execution_time: float,
                     config: FilterConfig,
                     annotated: Optional[List[Dict]] = None) -> None:
    """
    Display comprehensive statistics to console.
    
    Generates a formatted report showing:
    - Configuration loading status
    - Input file statistics
    - SQL filter being applied
    - Filtering results (before/after counts, percentages)
    - Matching statistics (DOI, Title, ID matches with percentages)
    - Unmatched entries list (if any)
    - Output file generation results
    - Execution time
    Additionally, the report is persisted to a Markdown file located in the
    same directory as the JSON outputs for traceability.
    
    Args:
        input_count: Number of input records
        filtered_count: Number of filtered records
        stats: Matching statistics object
        execution_time: Execution time in seconds
        config: Configuration object
    
    Examples:
        >>> report_statistics(1000, 250, stats, 2.5, config)
        # Displays formatted statistics report to console
    """
    print("\n" + "="*70)
    print("=== FILTER RELEVANT PAPERS - EXECUTION REPORT ===")
    print("="*70)
    
    # Configuration Section
    print("\n[CONFIGURATION]")
    print(f"  ✓ Configuration file: .conf")
    print(f"  ✓ Filter config: {config.yaml_filter_path}")
    print(f"  ✓ SQL Filter: {config.filter_clause[:80]}{'...' if len(config.filter_clause) > 80 else ''}")
    
    # Input Section
    print("\n[INPUT DATA]")
    print(f"  - JSON records loaded: {input_count:,}")
    print(f"  - Source file: {config.json_input_path}")
    print(f"  - BibTeX entries loaded: (available for matching)")
    print(f"  - Source file: {config.bib_file_path}")
    
    # Filtering Section
    print("\n[FILTERING RESULTS]")
    if input_count > 0:
        relevant_percentage = (filtered_count / input_count) * 100
        unrelevant_percentage = (unrelevant_count / input_count) * 100
        print(f"  - Relevant papers: {filtered_count:,} ({relevant_percentage:.1f}% of input)")
        print(f"  - Unrelevant papers: {unrelevant_count:,} ({unrelevant_percentage:.1f}% of input)")
    else:
        print(f"  - Relevant papers: {filtered_count:,}")
        print(f"  - Unrelevant papers: {unrelevant_count:,}")
    
    # Matching Section
    print("\n[ENTRY MATCHING]")
    if stats.total_filtered > 0:
        # Calculate percentages
        doi_pct = (stats.matched_doi / stats.total_filtered) * 100
        title_pct = (stats.matched_title / stats.total_filtered) * 100
        id_pct = (stats.matched_id / stats.total_filtered) * 100
        unmatched_pct = (stats.unmatched / stats.total_filtered) * 100
        
        print(f"  - DOI matches: {stats.matched_doi:,} ({doi_pct:.1f}%)")
        print(f"  - Title matches: {stats.matched_title:,} ({title_pct:.1f}%)")
        print(f"  - ID matches: {stats.matched_id:,} ({id_pct:.1f}%)")
        print(f"  - Total matched: {stats.matched_doi + stats.matched_title + stats.matched_id:,} ({100 - unmatched_pct:.1f}%)")
        print(f"  - Unmatched: {stats.unmatched:,} ({unmatched_pct:.1f}%)")
        
        # Display unmatched entries details if any
        if stats.unmatched > 0 and stats.unmatched_entries:
            print("\n  [Unmatched Entries Details]")
            # Show first 5 unmatched entries
            display_count = min(5, len(stats.unmatched_entries))
            for i, entry in enumerate(stats.unmatched_entries[:display_count], 1):
                print(f"    {i}. ID: {entry.get('id', 'N/A')[:20]}")
                print(f"       DOI: {entry.get('doi', 'N/A')[:40]}")
                print(f"       Title: {entry.get('title', 'N/A')[:60]}...")
            
            if len(stats.unmatched_entries) > display_count:
                remaining = len(stats.unmatched_entries) - display_count
                print(f"    ... and {remaining} more unmatched entries")
    else:
        print("  - No records to match (empty filter result)")
    
    # Output Section
    print("\n[OUTPUT FILES]")
    matched_count = stats.matched_doi + stats.matched_title + stats.matched_id
    print(f"  ✓ Relevant JSON output: {config.json_output_path}")
    print(f"    Records: {filtered_count:,}")
    print(f"  ✓ Unrelevant JSON output: {config.unrelevant_output_path}")
    print(f"    Records: {unrelevant_count:,}")
    print(f"  ✓ BibTeX output: {config.bib_output_path}")
    print(f"    Entries: {matched_count:,}")
    print(f"  ✓ Selection decisions Excel: {config.selection_decisions_path}")
    print(f"    Rows: {input_count:,} (selected: {filtered_count:,} / rejected: {unrelevant_count:,})")

    # Performance Section
    print("\n[PERFORMANCE]")
    print(f"  - Execution time: {execution_time:.3f} seconds")
    if input_count > 0:
        records_per_sec = input_count / execution_time if execution_time > 0 else 0
        print(f"  - Processing speed: {records_per_sec:.0f} records/second")
    
    # Summary
    print("\n" + "="*70)
    print("✓ FILTERING COMPLETED SUCCESSFULLY")
    print("="*70 + "\n")

    # Persist markdown report alongside JSON outputs for auditing.
    try:
        # Ensure parent directory exists before persisting.
        report_dir = os.path.dirname(config.markdown_report_path)
        if report_dir and not os.path.exists(report_dir):
            os.makedirs(report_dir, exist_ok=True)

        markdown_content = build_markdown_report(
            input_count=input_count,
            filtered_count=filtered_count,
            unrelevant_count=unrelevant_count,
            stats=stats,
            execution_time=execution_time,
            config=config,
            annotated=annotated
        )

        with open(config.markdown_report_path, "w", encoding="utf-8") as report_file:
            report_file.write(markdown_content)

        print(f"  ✓ Markdown report saved: {config.markdown_report_path}")

    except OSError as error:
        print(f"  ⚠ Warning: Failed to save markdown report: {error}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def filter_relevant_papers(config: Optional[FilterConfig] = None) -> bool:
    """
    Main entry point for filtering LLM responses.
    
    This function orchestrates the entire filtering workflow:
    1. Load configuration from .conf and YAML
    2. Load JSON and BibTeX data
    3. Apply DuckDB filter with SQL WHERE clause
    4. Match filtered records to BibTeX entries
    5. Generate output files (JSON and BibTeX)
    6. Display statistics
    
    The function handles errors gracefully at each step and provides
    clear error messages to help diagnose issues. Execution time is
    measured for performance monitoring.
    
    Returns:
        bool: True if successful, False otherwise
    
    Raises:
        Exception: For critical errors that prevent execution
        
    Examples:
        >>> from src.FilterRelevantPapers import filter_relevant_papers
        >>> success = filter_relevant_papers()
        >>> if success:
        ...     print("Filtering completed successfully")
    """
    # Start timing
    start_time = time.time()
    
    print("\n" + "="*70)
    print("=== FILTER RELEVANT PAPERS ===")
    print("="*70 + "\n")
    
    try:
        # Step 1: Load Configuration
        print("[1/6] Loading configuration...")
        try:
            if config is None:
                config = load_configuration()
            print("  ✓ Configuration loaded successfully")
            print(f"  - Data path: {config.path_data}")
            print(f"  - Filter clause loaded ({len(config.filter_clause)} characters)")
        except FileNotFoundError as e:
            print(f"  ✗ Error: {e}")
            print("  → Please ensure .conf file exists in project root")
            return False
        except KeyError as e:
            print(f"  ✗ Error: {e}")
            print("  → Please check .conf file has all required variables")
            return False
        except Exception as e:
            print(f"  ✗ Unexpected error loading configuration: {e}")
            return False
        
        # Step 2: Load Input Data
        print("\n[2/6] Loading input data...")
        try:
            # Load JSON data
            json_data = load_json_data(config.json_input_path)
            input_count = len(json_data)
            print(f"  ✓ JSON data loaded: {input_count:,} records")
            
            # Load BibTeX data
            bibtex_data = load_bibtex_data(config.bib_file_path)
            bib_count = len(bibtex_data)
            print(f"  ✓ BibTeX data loaded: {bib_count:,} entries")
            
        except FileNotFoundError as e:
            print(f"  ✗ Error: {e}")
            print("  → Please check file paths in .conf")
            return False
        except json.JSONDecodeError as e:
            print(f"  ✗ Error: Malformed JSON - {e}")
            print("  → Please validate JSON file format")
            return False
        except Exception as e:
            print(f"  ✗ Unexpected error loading data: {e}")
            return False
        
        # Step 3: Apply DuckDB Filter (with per-article decision + evidence)
        print("\n[3/6] Applying SQL filter...")
        try:
            # Locate the atomic predicates of the clause (for evidence + Excel ordering).
            known_cols = set()
            for record in json_data:
                known_cols.update(record.keys())
            predicates = extract_predicates(config.filter_clause, known_cols)

            # Annotate each article with `_selected` + `_selection_reason`, then split.
            annotated = annotate_with_decision(json_data, config.filter_clause)
            filtered_data = [r for r in annotated if r.get("_selected")]
            unrelevant_data = [r for r in annotated if not r.get("_selected")]
            filtered_count = len(filtered_data)
            unrelevant_count = len(unrelevant_data)
            
            if input_count > 0:
                relevant_percentage = (filtered_count / input_count) * 100
                unrelevant_percentage = (unrelevant_count / input_count) * 100
                print(f"  ✓ Filter applied:")
                print(f"    - Relevant: {filtered_count:,} records ({relevant_percentage:.1f}% of input)")
                print(f"    - Unrelevant: {unrelevant_count:,} records ({unrelevant_percentage:.1f}% of input)")
            else:
                print(f"  ✓ Filter applied:")
                print(f"    - Relevant: {filtered_count:,} records")
                print(f"    - Unrelevant: {unrelevant_count:,} records")
            
            # Warning if no records pass filter
            if filtered_count == 0:
                print("  ⚠ Warning: No records passed the filter criteria")
                print("  → Proceeding with empty result set")
                
        except duckdb.Error as e:
            print(f"  ✗ SQL Error: {e}")
            print("  → Please check SQL filter syntax in YAML configuration")
            return False
        except Exception as e:
            print(f"  ✗ Unexpected error applying filter: {e}")
            return False
        
        # Step 4: Match BibTeX Entries
        print("\n[4/6] Matching BibTeX entries...")
        try:
            matched_bibtex, matching_stats = match_bibtex_entries(filtered_data, bibtex_data)
            matched_count = len(matched_bibtex)
            
            print(f"  ✓ Matching completed: {matched_count:,} entries matched")
            print(f"    - DOI matches: {matching_stats.matched_doi:,}")
            print(f"    - Title matches: {matching_stats.matched_title:,}")
            print(f"    - ID matches: {matching_stats.matched_id:,}")
            
            if matching_stats.unmatched > 0:
                print(f"    - Unmatched: {matching_stats.unmatched:,}")
                
        except Exception as e:
            print(f"  ✗ Unexpected error during matching: {e}")
            return False
        
        # Step 5: Write Output Files
        print("\n[5/6] Generating output files...")
        try:
            write_filtered_outputs(
                filtered_json=filtered_data,
                matched_bibtex=matched_bibtex,
                json_path=config.json_output_path,
                bib_path=config.bib_output_path,
                unrelevant_json=unrelevant_data,
                unrelevant_path=config.unrelevant_output_path
            )

            # Selection-decision spreadsheet (all articles + decision + derived motivation).
            write_decision_excel(
                annotated=annotated,
                output_path=config.selection_decisions_path,
                filter_clause=config.filter_clause,
                predicates=predicates,
                questions=_load_questions_legend(config.yaml_filter_path),
            )
            print(f"  ✓ Output files created successfully")
            
        except PermissionError as e:
            print(f"  ✗ Permission Error: {e}")
            print("  → Please check write permissions for output directories")
            return False
        except OSError as e:
            print(f"  ✗ File System Error: {e}")
            print("  → Please check disk space and path validity")
            return False
        except Exception as e:
            print(f"  ✗ Unexpected error writing outputs: {e}")
            return False
        
        # Step 6: Display Statistics
        print("\n[6/6] Generating statistics report...")
        execution_time = time.time() - start_time
        
        try:
            report_statistics(
                input_count=input_count,
                filtered_count=filtered_count,
                unrelevant_count=unrelevant_count,
                stats=matching_stats,
                execution_time=execution_time,
                config=config,
                annotated=annotated
            )
        except Exception as e:
            print(f"  ⚠ Warning: Error displaying statistics: {e}")
            # Not a critical error, continue
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n✗ Execution interrupted by user")
        return False
    except Exception as e:
        print(f"\n✗ Critical error: {e}")
        print("  → Please review the error above and check your configuration")
        return False


# ============================================================================
# FILTRO FINAL (TRIAGEM POR TEXTO COMPLETO)
# ============================================================================

def load_configuration_fulltext() -> FilterConfig:
    """
    Configuração do filtro FINAL (texto completo): lê o consolidado de full-text e grava
    final_papers.* + selection_decisions_fulltext.xlsx. Reaproveita toda a lógica de
    filter_relevant_papers, só trocando caminhos/YAML. Casa os relevantes contra o
    relevant_abstract_papers.bib (que contém os papers triados por abstract).
    """
    conf_path = os.path.abspath(".conf")
    if os.path.exists(conf_path):
        load_dotenv(conf_path)

    path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
    path_data = os.path.join(path_data, ".bibs")

    bib_file = os.getenv("RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT", "OUTPUTS/relevant_abstract_papers.bib")
    json_input = os.getenv("FILTER_LLM_RESPONSES_FULLTEXT_PATH",
                           "OUTPUTS/processed_responses/combined_responses_fulltext_consolidated.json")
    json_output = os.getenv("FINAL_PAPERS_OUTPUT", "OUTPUTS/processed_responses/final_papers.json")
    bib_output = os.getenv("FINAL_PAPERS_BIBs_OUTPUT", "OUTPUTS/final_papers.bib")
    unrelevant_output = os.getenv("FINAL_EXCLUDED_PAPERS_OUTPUT",
                                  "OUTPUTS/processed_responses/final_excluded_papers.json")
    yaml_filter = os.getenv("FILTER_LLM_CONFIG_FULLTEXT_PATH",
                            "config/filter_accept_results_llm_fulltext.yaml")

    bib_file_path = path_data.replace(".bibs", bib_file)
    json_input_path = path_data.replace(".bibs", json_input)
    json_output_path = path_data.replace(".bibs", json_output)
    bib_output_path = path_data.replace(".bibs", bib_output)
    unrelevant_output_path = path_data.replace(".bibs", unrelevant_output)
    yaml_filter_path = os.path.abspath(yaml_filter)
    markdown_report_path = os.path.splitext(json_output_path)[0] + "_report.md"

    decisions_env = os.getenv("SELECTION_DECISIONS_FULLTEXT_EXCEL_OUTPUT")
    if decisions_env:
        selection_decisions_path = path_data.replace(".bibs", decisions_env)
    else:
        selection_decisions_path = os.path.join(
            os.path.dirname(json_output_path), "selection_decisions_fulltext.xlsx")

    filter_clause = load_yaml_filter(yaml_filter_path)

    return FilterConfig(
        path_data=path_data,
        bib_file_path=bib_file_path,
        json_input_path=json_input_path,
        json_output_path=json_output_path,
        bib_output_path=bib_output_path,
        unrelevant_output_path=unrelevant_output_path,
        yaml_filter_path=yaml_filter_path,
        filter_clause=filter_clause,
        markdown_report_path=markdown_report_path,
        selection_decisions_path=selection_decisions_path,
    )


def filter_final_papers() -> bool:
    """Filtro FINAL da triagem por texto completo → final_papers + selection_decisions_fulltext."""
    return filter_relevant_papers(load_configuration_fulltext())
