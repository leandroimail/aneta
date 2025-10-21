# REQUIREMENTS AND DEVELOPMENT REQUEST DOCUMENT (DRSD)
## Bibliographic Filtering Script with DuckDB

---

## DOCUMENT METADATA

| Field | Value |
|-------|-------|
| **Project** | ASRL - Automated Systematic Review Literature |
| **Feature Name** | Filter LLM Responses for Relevant Papers |
| **Document Version** | 1.0 |
| **Creation Date** | October 21, 2025 |
| **Analyst** | GitHub Copilot (Claude Sonnet 4.5) |
| **Status** | Draft for Review |

---

## 1. CONTEXT AND OBJECTIVE

### 1.1 Project Context

The ASRL (Automated Systematic Review Literature) project is a comprehensive bibliographic analysis system that processes academic papers through multiple stages:

1. **Search**: Retrieves papers from academic databases
2. **Enrichment**: Enhances BibTeX entries with additional metadata
3. **Selection**: Applies inclusion/exclusion criteria using DuckDB queries
4. **LLM Classification**: Uses Large Language Models to evaluate paper relevance based on abstracts
5. **Filtering** (NEW): Filters LLM-processed results to identify truly relevant papers
6. **Bibliometry**: Generates bibliometric analysis
7. **PDF Download & Processing**: Downloads and extracts content from papers

The project currently lacks an automated filtering mechanism to process LLM responses and generate filtered outputs based on configurable SQL criteria.

### 1.2 Business Need

After LLM classification generates response data with relevance scores and research question alignments, researchers need to:

- **Filter** papers based on configurable SQL criteria (e.g., relevance thresholds, research question alignment)
- **Extract** relevant papers into separate JSON and BibTeX files
- **Match** papers accurately using multiple identifiers (DOI, title, BibTeX ID)
- **Maintain** data consistency between JSON responses and BibTeX entries
- **Automate** the filtering process for reproducibility

### 1.3 Feature Objective

Create a Python CLI script that:

1. Reads system configuration from `.conf` file
2. Loads LLM response data from JSON files
3. Applies SQL-based filtering using DuckDB in-memory database
4. Generates filtered JSON output maintaining source structure
5. Creates corresponding filtered BibTeX file with accurate entry matching
6. Integrates seamlessly with existing aneta.py workflow
7. Follows established project patterns and coding standards

---

## 2. DESCRIPTION OF THE REQUESTED APPLICATION/FEATURE

### 2.1 Feature Overview

A standalone Python module that processes LLM-classified papers through configurable SQL filters to identify and extract relevant bibliographic entries. The script acts as a bridge between LLM classification outputs and downstream analysis tools.

### 2.2 Key Capabilities

#### 2.2.1 Configuration Management
- Read environment variables from `.conf` file
- Load YAML configuration with SQL filter expressions
- Construct file paths following project conventions
- Support configurable base paths via `PATH_DATA`

#### 2.2.2 Data Processing
- Load JSON data from LLM response files
- Parse BibTeX files using existing `src/BibTex.py` utilities
- Execute DuckDB SQL queries on in-memory tables
- Filter data based on complex SQL WHERE clauses

#### 2.2.3 Entry Matching
- Match papers using hierarchical identifier strategy:
  1. Primary: DOI (most reliable)
  2. Secondary: Title (normalized comparison)
  3. Tertiary: BibTeX ID (fallback)
- Handle missing or malformed identifiers gracefully
- Maintain referential integrity between JSON and BibTeX outputs

#### 2.2.4 Output Generation
- Create filtered JSON file preserving source schema
- Generate filtered BibTeX file with matched entries
- Maintain data consistency across outputs
- Support configurable output paths

### 2.3 Integration Points

- **Input Source**: `OUTPUTS/processed_responses/combined_responses_consolidated.json`
- **Configuration**: `config/filter_accept_results_llm.yaml`
- **BibTeX Source**: `OUTPUTS/select_bibs.bib`
- **Output JSON**: `OUTPUTS/relevant_papers.json`
- **Output BibTeX**: `OUTPUTS/relevant_abstract_papers.bib`
- **CLI Integration**: `aneta.py` (new command flag)

### 2.4 User Interaction Flow

```
User executes → aneta.py --filter_relevant_papers
             ↓
    Script reads .conf and YAML config
             ↓
    Loads JSON responses and BibTeX entries
             ↓
    Applies SQL filter via DuckDB
             ↓
    Matches entries (DOI → Title → ID)
             ↓
    Generates filtered JSON and BibTeX outputs
             ↓
    Reports filtering statistics
```

---

## 3. FUNCTIONAL REQUIREMENTS

### FR-01: Configuration File Reading
**Priority**: Critical  
**Description**: The script must read configuration parameters from `.conf` file following the existing dotenv pattern.

**Acceptance Criteria**:
- Load variables using `python-dotenv`
- Support the following configuration keys:
  - `BIB_FILE`: Source BibTeX file path
  - `PATH_DATA`: Base data directory
  - `FILTER_LLM_RESPONSES_ABSTRACT_PATH`: Input JSON path
  - `RELEVANT_ABSTRACT_PAPERS_OUTPUT`: Output JSON path
  - `RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT`: Output BibTeX path
  - `FILTER_LLM_CONFIG_PATH`: YAML filter configuration path
- Handle missing configuration with clear error messages
- Use `os.path.abspath()` for path resolution

**Example**:
```python
load_dotenv(os.path.abspath(".conf"))
path_data = os.getenv("PATH_DATA", ".data")
```

---

### FR-02: Path Construction
**Priority**: Critical  
**Description**: Construct file paths following the project's established pattern from `aneta.py`.

**Acceptance Criteria**:
- Prepend `PATH_DATA` to output paths
- Use pattern: `path_data.replace(".bibs", output_path)`
- Maintain consistency with existing scripts
- Support both absolute and relative paths
- Validate path existence before operations

**Example Pattern** (from aneta.py):
```python
path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
path_data = os.path.join(path_data, ".bibs")
path_directory_file_bib = path_data.replace(".bibs", bib_file)
```

---

### FR-03: YAML Filter Configuration Loading
**Priority**: Critical  
**Description**: Load SQL filter expressions from YAML configuration file.

**Acceptance Criteria**:
- Read YAML file from `FILTER_LLM_CONFIG_PATH`
- Extract `filter` key containing SQL WHERE clause
- Validate YAML structure
- Handle file not found errors
- Support multi-line SQL expressions
- Strip unnecessary whitespace from SQL

**Example YAML Structure**:
```yaml
filter: >
  ((is_relevant_yes_percent >= 65
  AND total_models_answered >= 2)
  AND
  (
    principal_research_question_yes_percent >= 65
    AND principal_research_question_total_count >= 2
  ))
```

---

### FR-04: JSON Data Loading
**Priority**: Critical  
**Description**: Load LLM response data from JSON file into memory.

**Acceptance Criteria**:
- Read JSON file using standard `json` library
- Support UTF-8 encoding
- Handle large files efficiently
- Validate JSON structure (must be array of objects)
- Provide clear error messages for malformed JSON
- Log number of records loaded

**Expected JSON Schema** (consolidated responses):
```json
[
  {
    "_response_id": "unique_id",
    "id": "bibtex_entry_id",
    "doi": "10.1234/example",
    "article_title": "Paper Title",
    "article_abstract": "Abstract text...",
    "total_responses": 3,
    "is_relevant_yes_percent": 75.0,
    "is_relevant_total_count": 3,
    "principal_research_question_yes_percent": 66.67,
    "principal_research_question_total_count": 3,
    ...
  }
]
```

---

### FR-05: BibTeX File Loading
**Priority**: Critical  
**Description**: Load BibTeX entries using existing `src/BibTex.py` utilities.

**Acceptance Criteria**:
- Use `read_bibtex()` function from `src/BibTex.py`
- Handle encoding issues (UTF-8, chardet fallback)
- Support multiple BibTeX entry types
- Log number of entries loaded
- Validate BibTeX structure
- Handle malformed entries gracefully

**Example**:
```python
from src.BibTex import read_bibtex
bibtex_entries = read_bibtex(bib_file_path)
```

---

### FR-06: DuckDB In-Memory Database
**Priority**: Critical  
**Description**: Create in-memory DuckDB database from JSON data and execute SQL queries.

**Acceptance Criteria**:
- Initialize DuckDB in-memory connection
- Register JSON data as DataFrame table
- Execute SQL SELECT with WHERE clause from config
- Return filtered results as DataFrame
- Handle SQL syntax errors with clear messages
- Clean up database connection after operation
- Support complex SQL expressions (AND, OR, parentheses, comparisons)

**Example** (from Selection.py):
```python
import duckdb
conn = duckdb.connect(':memory:')
conn.register('table_name', dataframe)
query = f"SELECT * FROM table_name WHERE {filter_clause}"
result_df = conn.execute(query).fetchdf()
```

---

### FR-07: Entry Matching Strategy
**Priority**: Critical  
**Description**: Match filtered JSON entries to BibTeX entries using hierarchical identifier matching.

**Acceptance Criteria**:
- Implement three-tier matching strategy:
  1. **Primary Match**: DOI (case-insensitive, normalized)
  2. **Secondary Match**: Title (normalized, whitespace/punctuation removed)
  3. **Tertiary Match**: BibTeX ID (exact match)
- Track matching statistics (success rate per method)
- Handle missing fields gracefully
- Log unmatched entries for debugging
- Prefer earlier matches (DOI > Title > ID)

**Matching Logic**:
```python
def normalize_doi(doi: str) -> str:
    """Normalize DOI: lowercase, strip whitespace"""
    return doi.lower().strip()

def normalize_title(title: str) -> str:
    """Normalize title: remove punctuation, lowercase, collapse whitespace"""
    import re
    title = re.sub(r'[^\w\s]', '', title.lower())
    return re.sub(r'\s+', ' ', title).strip()

def match_entry(json_record, bibtex_entries):
    # Try DOI match
    if json_record.get('doi'):
        for bib in bibtex_entries:
            if normalize_doi(json_record['doi']) == normalize_doi(bib.get('doi', '')):
                return bib
    
    # Try title match
    if json_record.get('article_title'):
        json_title_norm = normalize_title(json_record['article_title'])
        for bib in bibtex_entries:
            if normalize_title(bib.get('title', '')) == json_title_norm:
                return bib
    
    # Try ID match
    if json_record.get('id'):
        for bib in bibtex_entries:
            if bib.get('ID') == json_record['id']:
                return bib
    
    return None
```

---

### FR-08: Filtered JSON Output
**Priority**: Critical  
**Description**: Generate filtered JSON file maintaining exact source structure.

**Acceptance Criteria**:
- Write filtered records to JSON file
- Preserve all fields from source
- Maintain data types and structure
- Use UTF-8 encoding with ensure_ascii=False
- Pretty-print with indentation (indent=2)
- Create parent directories if needed
- Validate output file creation
- Log number of records written

**Example**:
```python
import json
with open(output_json_path, 'w', encoding='utf-8') as f:
    json.dump(filtered_records, f, indent=2, ensure_ascii=False)
```

---

### FR-09: Filtered BibTeX Output
**Priority**: Critical  
**Description**: Generate filtered BibTeX file with matched entries.

**Acceptance Criteria**:
- Use `write_bibtex()` from `src/BibTex.py`
- Include only matched entries
- Preserve original BibTeX formatting
- Maintain entry order from filtered JSON
- Create parent directories if needed
- Validate output file creation
- Log number of entries written

**Example**:
```python
from src.BibTex import write_bibtex
write_bibtex(output_bib_path, matched_bibtex_entries)
```

---

### FR-10: CLI Integration
**Priority**: High  
**Description**: Integrate script into `aneta.py` as a new command-line option.

**Acceptance Criteria**:
- Add `--filter_relevant_papers` argument to argparse
- Create wrapper function in `aneta.py`
- Import and call filtering module
- Follow existing CLI pattern from other commands
- Support both CLI flag and script mode variable
- Provide help text for new command

**Example Integration**:
```python
# In aneta.py argparse
group.add_argument('--filter_relevant_papers', 
                   action='store_true', 
                   help='Filters LLM responses to identify relevant papers')

# Wrapper function
def run_filter_relevant_papers():
    from src.FilterRelevantPapers import filter_relevant_papers
    filter_relevant_papers()
    return True

# CLI handler
elif args.filter_relevant_papers:
    run_filter_relevant_papers()
```

---

### FR-11: Logging and Reporting
**Priority**: Medium  
**Description**: Provide comprehensive logging of filtering operations and statistics.

**Acceptance Criteria**:
- Log configuration loading
- Report input file statistics (records/entries loaded)
- Display SQL filter being applied
- Show filtering results (records before/after)
- Report matching statistics (DOI/Title/ID success rates)
- Display unmatched entries with details
- Report output file generation
- Show execution time
- Use consistent logging format

**Example Output**:
```
=== Filter Relevant Papers ===
Configuration loaded from: .conf
Filter config: config/filter_accept_results_llm.yaml
SQL Filter: ((is_relevant_yes_percent >= 65 AND total_models_answered >= 2)...)

Loading data...
- Input JSON: 1,234 records loaded
- Source BibTeX: 1,234 entries loaded

Applying filter...
- Filtered records: 345 (27.9% of input)

Matching BibTeX entries...
- DOI matches: 320 (92.8%)
- Title matches: 20 (5.8%)
- ID matches: 3 (0.9%)
- Unmatched: 2 (0.6%)

Generating outputs...
✓ JSON output: OUTPUTS/relevant_papers.json (345 records)
✓ BibTeX output: OUTPUTS/relevant_abstract_papers.bib (343 entries)

Completed in 2.3 seconds
```

---

## 4. NON-FUNCTIONAL REQUIREMENTS

### NFR-01: Performance
**Requirement**: The script must process up to 10,000 records in under 10 seconds.  
**Justification**: Typical datasets contain 100-2,000 papers; performance headroom ensures scalability.  
**Measurement**: Execution time from data loading to output generation.

---

### NFR-02: Memory Efficiency
**Requirement**: Peak memory usage must not exceed 500MB for typical datasets (2,000 records).  
**Justification**: In-memory DuckDB operations require reasonable resource limits.  
**Measurement**: Monitor process memory during execution.

---

### NFR-03: Error Handling
**Requirement**: All errors must be caught with descriptive messages and graceful failure.  
**Justification**: Users need clear feedback for configuration or data issues.  
**Implementation**:
- Try-except blocks around I/O operations
- Validation of configuration values
- SQL syntax error handling
- File not found error messages
- JSON parsing error details

---

### NFR-04: Code Quality
**Requirement**: Code must follow project standards from `.github/copilot-instructions.md`.  
**Standards**:
- Python 3.11+ syntax
- Type hints (typing annotations)
- Docstrings (Google/NumPy style)
- English comments and variable names
- Error handling with logging
- Standard library preference

---

### NFR-05: Maintainability
**Requirement**: Code must be modular and testable.  
**Implementation**:
- Separate functions for each major operation
- Clear function signatures with type hints
- Minimal dependencies (reuse existing utilities)
- Configuration-driven behavior
- Unit test compatibility

---

### NFR-06: Compatibility
**Requirement**: Script must work with existing project infrastructure.  
**Constraints**:
- Compatible with `uv run python` execution
- Works with existing `.conf` format
- Uses established file path conventions
- Integrates with `aneta.py` CLI pattern
- Compatible with Python 3.11+

---

### NFR-07: Documentation
**Requirement**: Code must be self-documenting with comprehensive docstrings.  
**Standards**:
- Module-level docstring explaining purpose
- Function docstrings with Args, Returns, Raises sections
- Inline comments for complex logic
- Type hints for all function parameters and returns
- Example usage in module docstring

---

## 5. ANALYSIS OF EXISTING CODE

### 5.1 Architectural Overview

The ASRL project follows a **modular script-based architecture**:

```
Main CLI (aneta.py)
    ↓
Individual Module Scripts (src/*.py)
    ↓
Utility Libraries (src/BibTex.py, src/Config.py)
    ↓
Configuration Files (config/*.yaml, .conf)
    ↓
Data Files (PATH_DATA/OUTPUTS/*)
```

**Key Patterns**:
- **Dotenv Configuration**: All scripts load `.conf` using `python-dotenv`
- **Path Construction**: Use `os.path.abspath()` and `.replace(".bibs", ...)` pattern
- **DuckDB Filtering**: `Selection.py` demonstrates SQL-based filtering
- **BibTeX Processing**: `BibTex.py` provides standardized I/O functions
- **CLI Integration**: `aneta.py` uses argparse with function wrappers

### 5.2 Relevant Code Components

#### 5.2.1 Selection.py - Filtering Pattern
```python
# Pattern: DuckDB in-memory filtering with YAML config
def pre_include_sql(list_bib):
    with open("config/search_config.yaml", "r") as f:
        config = yaml.safe_load(f)
    filter_string = config["filter_string"]
    
    conn = duckdb.connect(':memory:')
    conn.register('table_bibs', dataframe)
    query = f"SELECT * FROM table_bibs WHERE {filter_string}"
    df = conn.execute(query).fetchdf()
    return df.to_dict('records')
```

**Reusable Elements**:
- YAML configuration pattern
- DuckDB in-memory database
- SQL WHERE clause filtering
- DataFrame registration
- Error handling structure

#### 5.2.2 BibTex.py - I/O Utilities
```python
def read_bibtex(path):
    """Reads BibTeX with encoding fallback"""
    # UTF-8 first, chardet fallback
    
def write_bibtex(path, entries):
    """Writes BibTeX using bibtexparser"""
    
def join_bib(path):
    """Joins multiple BibTeX files"""
```

**Reusable Elements**:
- Encoding handling (UTF-8 + chardet)
- BibTeX parser configuration
- Standardized I/O patterns

#### 5.2.3 aneta.py - CLI Integration Pattern
```python
# Pattern: Argparse + function wrapper
parser.add_argument('--command', action='store_true', help='...')

def run_command():
    from src.Module import function
    function()
    return True

if args.command:
    run_command()
```

**Reusable Elements**:
- Argparse configuration
- Function wrapper pattern
- Import-on-demand
- Return boolean for success

#### 5.2.4 Path Construction Pattern
```python
# From aneta.py
path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
path_data = os.path.join(path_data, ".bibs")
path_directory_file_bib = path_data.replace(".bibs", bib_file)
```

**Key Insight**: Use `.replace(".bibs", ...)` to construct output paths from base path.

### 5.3 Dependencies

**Required Libraries**:
- `os`: File system operations
- `json`: JSON I/O
- `yaml`: Configuration loading (PyYAML)
- `duckdb`: In-memory SQL database
- `pandas`: DataFrame operations
- `python-dotenv`: Environment variable loading
- `bibtexparser`: BibTeX parsing (via `src/BibTex.py`)
- `typing`: Type hints
- `re`: Text normalization

**All dependencies are already present in the project.**

### 5.4 Integration Points

#### Input Dependencies
- **JSON Source**: Generated by `LLMUtilExcel.process_responses_to_excel()`
- **BibTeX Source**: Generated by `Selection.get_analyse()`
- **Configuration**: User-defined in `config/filter_accept_results_llm.yaml`

#### Output Dependencies
- **JSON Output**: Used by downstream analysis scripts
- **BibTeX Output**: Used by bibliography tools and PDF download

#### Execution Sequence
Recommended workflow position:
1. Search → Enrich → Selection → LLM Classification → **Filter Relevant** → Bibliometry → Download

---

## 6. PROPOSED ARCHITECTURE AND DIAGRAMS

### 6.1 Module Structure

```
src/
└── FilterRelevantPapers.py  (NEW)
    ├── filter_relevant_papers()       # Main entry point
    ├── load_configuration()           # Load .conf and YAML
    ├── construct_paths()              # Build file paths
    ├── load_json_data()               # Load LLM responses
    ├── load_bibtex_data()             # Load BibTeX entries
    ├── apply_duckdb_filter()          # Execute SQL filter
    ├── match_bibtex_entries()         # Match JSON to BibTeX
    ├── write_filtered_outputs()       # Generate output files
    └── report_statistics()            # Log results
```

### 6.2 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      Configuration Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  .conf                  config/filter_accept_results_llm.yaml   │
│  (env vars)             (SQL WHERE clause)                       │
└────────────┬────────────────────────────────┬───────────────────┘
             │                                │
             ▼                                ▼
┌─────────────────────┐           ┌──────────────────────┐
│  Input Data Layer   │           │  Filter Config       │
├─────────────────────┤           ├──────────────────────┤
│ JSON Responses      │           │ filter: >            │
│ (LLM processed)     │           │   is_relevant >= 65  │
│                     │           │   AND ...            │
│ BibTeX Entries      │           └──────────────────────┘
│ (source papers)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Processing Layer                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌─────────────────┐  │
│  │ Load JSON    │ →  │ Load BibTeX  │ →  │ Create DuckDB   │  │
│  │ (Pandas DF)  │    │ (Dict list)  │    │ In-Memory DB    │  │
│  └──────────────┘    └──────────────┘    └─────────────────┘  │
│                                                    │              │
│                                                    ▼              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Execute SQL Filter (WHERE clause from YAML)              │  │
│  │ SELECT * FROM responses WHERE is_relevant_yes_percent... │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Match Filtered Records to BibTeX Entries                 │  │
│  │ 1. Try DOI match (normalized)                            │  │
│  │ 2. Try Title match (normalized)                          │  │
│  │ 3. Try ID match (exact)                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Output Layer                                │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────┐      ┌─────────────────────────┐   │
│  │ Filtered JSON          │      │ Filtered BibTeX         │   │
│  │ relevant_papers.json   │      │ relevant_abstract_      │   │
│  │ (same structure as     │      │ papers.bib              │   │
│  │  input)                │      │ (matched entries only)  │   │
│  └────────────────────────┘      └─────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Console Report (Statistics & Matching Info)             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 Sequence Diagram

```
User          aneta.py       FilterRelevantPapers     DuckDB       FileSystem
 │                │                  │                   │              │
 │  execute       │                  │                   │              │
 │ ──────────────>│                  │                   │              │
 │   --filter_    │                  │                   │              │
 │   relevant_    │  call            │                   │              │
 │   papers       │ ───────────────> │                   │              │
 │                │                  │                   │              │
 │                │                  │  load_config()    │              │
 │                │                  │ ──────────────────────────────> │
 │                │                  │ <────────────────────────────── │
 │                │                  │  (.conf + YAML)   │              │
 │                │                  │                   │              │
 │                │                  │  load_json_data() │              │
 │                │                  │ ──────────────────────────────> │
 │                │                  │ <────────────────────────────── │
 │                │                  │                   │              │
 │                │                  │  load_bibtex()    │              │
 │                │                  │ ──────────────────────────────> │
 │                │                  │ <────────────────────────────── │
 │                │                  │                   │              │
 │                │                  │  register_table() │              │
 │                │                  │ ─────────────────>│              │
 │                │                  │                   │              │
 │                │                  │  execute_query()  │              │
 │                │                  │ ─────────────────>│              │
 │                │                  │ <─────────────────│              │
 │                │                  │  (filtered DF)    │              │
 │                │                  │                   │              │
 │                │                  │  match_entries()  │              │
 │                │                  │ ─────────────────┐│              │
 │                │                  │                  ││              │
 │                │                  │ <─────────────────┘              │
 │                │                  │  (matched list)   │              │
 │                │                  │                   │              │
 │                │                  │  write_outputs()  │              │
 │                │                  │ ──────────────────────────────> │
 │                │                  │ <────────────────────────────── │
 │                │                  │                   │              │
 │                │                  │  report_stats()   │              │
 │                │                  │ ─────────────────┐│              │
 │                │  return          │ <─────────────────┘              │
 │                │ <─────────────── │                   │              │
 │  result        │                  │                   │              │
 │ <──────────────│                  │                   │              │
 │                │                  │                   │              │
```

### 6.4 Class/Module Design

```python
# src/FilterRelevantPapers.py

from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass

@dataclass
class FilterConfig:
    """Configuration for filtering operation"""
    bib_file: str
    path_data: str
    filter_llm_responses_path: str
    relevant_papers_output: str
    relevant_papers_bib_output: str
    filter_config_path: str

@dataclass
class MatchingStats:
    """Statistics for entry matching"""
    doi_matches: int = 0
    title_matches: int = 0
    id_matches: int = 0
    unmatched: int = 0
    total: int = 0

def filter_relevant_papers() -> bool:
    """
    Main entry point for filtering relevant papers.
    
    Returns:
        bool: True if successful, False otherwise
    """
    pass

def load_configuration() -> FilterConfig:
    """Load configuration from .conf and return structured config."""
    pass

def construct_paths(config: FilterConfig) -> Dict[str, str]:
    """Construct full file paths following project conventions."""
    pass

def load_json_data(json_path: str) -> List[Dict[str, Any]]:
    """Load JSON data from file."""
    pass

def load_bibtex_data(bib_path: str) -> List[Dict[str, Any]]:
    """Load BibTeX entries using src/BibTex.py utilities."""
    pass

def load_yaml_filter(yaml_path: str) -> str:
    """Load SQL WHERE clause from YAML configuration."""
    pass

def apply_duckdb_filter(data: List[Dict], filter_clause: str) -> List[Dict]:
    """Execute DuckDB SQL filter on data."""
    pass

def match_bibtex_entries(
    filtered_json: List[Dict],
    bibtex_entries: List[Dict]
) -> Tuple[List[Dict], MatchingStats]:
    """Match filtered JSON records to BibTeX entries."""
    pass

def normalize_doi(doi: str) -> str:
    """Normalize DOI for comparison."""
    pass

def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    pass

def write_filtered_outputs(
    filtered_json: List[Dict],
    matched_bibtex: List[Dict],
    json_path: str,
    bib_path: str
) -> None:
    """Write filtered JSON and BibTeX outputs."""
    pass

def report_statistics(
    input_count: int,
    filtered_count: int,
    stats: MatchingStats,
    execution_time: float
) -> None:
    """Display filtering statistics to console."""
    pass
```

---

## 7. TECHNICAL SPECIFICATIONS FOR IMPLEMENTATION

### 7.1 File Location
- **Module Path**: `src/FilterRelevantPapers.py`
- **Integration**: `aneta.py` (add CLI argument and wrapper function)

### 7.2 Dependencies
```python
# Standard library
import os
import json
import re
import time
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass

# External libraries (already in project)
import yaml
import duckdb
import pandas as pd
from dotenv import load_dotenv

# Project modules
from src.BibTex import read_bibtex, write_bibtex
```

### 7.3 Configuration Schema

#### .conf Variables
```properties
PATH_DATA=".data"
BIB_FILE="OUTPUTS/select_bibs.bib"
FILTER_LLM_RESPONSES_ABSTRACT_PATH="OUTPUTS/processed_responses/combined_responses_consolidated.json"
RELEVANT_ABSTRACT_PAPERS_OUTPUT="OUTPUTS/relevant_papers.json"
RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT="OUTPUTS/relevant_abstract_papers.bib"
FILTER_LLM_CONFIG_PATH="config/filter_accept_results_llm.yaml"
```

#### YAML Filter Configuration
```yaml
# config/filter_accept_results_llm.yaml
filter: >
  ((is_relevant_yes_percent >= 65
  AND total_models_answered >= 2)
  AND
  (
    principal_research_question_yes_percent >= 65
    AND principal_research_question_total_count >= 2
  ))
```

### 7.4 Input Data Schemas

#### JSON Input (consolidated_responses.json)
```json
[
  {
    "_response_id": "paper_001",
    "id": "Smith2024",
    "doi": "10.1234/example.2024.001",
    "article_title": "Machine Learning in Healthcare",
    "article_abstract": "This paper presents...",
    "article_keywords": "machine learning; healthcare; AI",
    "total_responses": 3,
    "providers": "openai;anthropic;google",
    "models": "gpt-4o;claude-3.5;gemini-pro",
    "is_relevant_total_count": 3,
    "is_relevant_yes_count": 3,
    "is_relevant_no_count": 0,
    "is_relevant_yes_percent": 100.0,
    "principal_research_question_total_count": 3,
    "principal_research_question_yes_count": 2,
    "principal_research_question_yes_percent": 66.67
  }
]
```

#### BibTeX Input (select_bibs.bib)
```bibtex
@article{Smith2024,
  author = {Smith, John and Doe, Jane},
  title = {Machine Learning in Healthcare},
  journal = {Journal of AI Medicine},
  year = {2024},
  doi = {10.1234/example.2024.001},
  abstract = {This paper presents...},
  keywords = {machine learning; healthcare; AI}
}
```

### 7.5 Output Specifications

#### JSON Output
- **Format**: Same structure as input JSON
- **Encoding**: UTF-8
- **Pretty-print**: `indent=2`
- **ASCII**: `ensure_ascii=False`

#### BibTeX Output
- **Format**: Standard BibTeX
- **Encoding**: UTF-8
- **Function**: Use `src/BibTex.write_bibtex()`

### 7.6 Error Handling Matrix

| Error Type | Detection | Handling | User Message |
|------------|-----------|----------|--------------|
| Missing .conf | File check | Raise FileNotFoundError | "Configuration file .conf not found" |
| Missing YAML | File check | Raise FileNotFoundError | "Filter configuration not found: {path}" |
| Invalid YAML | YAML parse | Catch exception | "Invalid YAML syntax in {path}" |
| Missing filter key | Key check | Raise KeyError | "Key 'filter' not found in YAML config" |
| Missing JSON | File check | Raise FileNotFoundError | "Input JSON not found: {path}" |
| Invalid JSON | JSON parse | Catch JSONDecodeError | "Invalid JSON format in {path}" |
| Missing BibTeX | File check | Raise FileNotFoundError | "BibTeX file not found: {path}" |
| SQL syntax error | DuckDB execute | Catch exception | "SQL filter error: {error}" |
| Empty results | Count check | Warning only | "No records match filter criteria" |
| Write permission | File write | Catch OSError | "Cannot write to {path}: permission denied" |

### 7.7 Testing Strategy

#### Unit Tests
1. **Test Configuration Loading**
   - Valid .conf file
   - Missing .conf file
   - Invalid environment variables

2. **Test Path Construction**
   - Absolute paths
   - Relative paths
   - Windows vs Unix paths

3. **Test JSON Loading**
   - Valid JSON
   - Malformed JSON
   - Empty JSON array

4. **Test BibTeX Loading**
   - Valid BibTeX
   - UTF-8 and other encodings
   - Empty BibTeX file

5. **Test YAML Loading**
   - Valid YAML with filter key
   - Missing filter key
   - Invalid YAML syntax

6. **Test DuckDB Filtering**
   - Simple WHERE clause
   - Complex AND/OR conditions
   - SQL syntax errors

7. **Test Entry Matching**
   - DOI matching (exact and normalized)
   - Title matching (normalized)
   - ID matching
   - Unmatched entries

8. **Test Output Generation**
   - JSON writing
   - BibTeX writing
   - Directory creation

#### Integration Tests
1. **End-to-End Flow**
   - Run complete filtering with sample data
   - Verify output correctness
   - Check matching statistics

2. **CLI Integration**
   - Test `aneta.py --filter_relevant_papers`
   - Verify exit codes
   - Check console output

### 7.8 Performance Considerations

**Optimization Strategies**:
1. **Data Loading**: Use generators for large files
2. **Matching**: Create lookup dictionaries for O(1) access
3. **DuckDB**: Leverage in-memory database for fast SQL execution
4. **Normalization**: Cache normalized values to avoid redundant processing

**Benchmark Targets**:
- 1,000 records: < 2 seconds
- 5,000 records: < 5 seconds
- 10,000 records: < 10 seconds

---

## 8. ACCEPTANCE CRITERIA AND TESTS

### AC-01: Configuration Loading
**Given**: A valid `.conf` file exists  
**When**: The script is executed  
**Then**: 
- All required environment variables are loaded
- Paths are constructed correctly
- No errors are raised

**Test**:
```python
def test_configuration_loading():
    config = load_configuration()
    assert config.path_data is not None
    assert config.bib_file is not None
    assert config.filter_config_path is not None
```

---

### AC-02: YAML Filter Loading
**Given**: A valid YAML file with `filter` key exists  
**When**: The filter is loaded  
**Then**: 
- SQL WHERE clause is extracted correctly
- Whitespace is normalized
- No syntax errors

**Test**:
```python
def test_yaml_filter_loading():
    filter_clause = load_yaml_filter("config/filter_accept_results_llm.yaml")
    assert "is_relevant_yes_percent" in filter_clause
    assert len(filter_clause) > 0
```

---

### AC-03: JSON Data Loading
**Given**: A valid JSON file with consolidated responses  
**When**: JSON is loaded  
**Then**: 
- Data is parsed into list of dictionaries
- All required fields are present
- Record count is accurate

**Test**:
```python
def test_json_loading():
    data = load_json_data("path/to/combined_responses_consolidated.json")
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "doi" in data[0]
```

---

### AC-04: BibTeX Data Loading
**Given**: A valid BibTeX file exists  
**When**: BibTeX is loaded  
**Then**: 
- Entries are parsed correctly
- Encoding issues are handled
- Entry count is accurate

**Test**:
```python
def test_bibtex_loading():
    entries = load_bibtex_data("path/to/select_bibs.bib")
    assert isinstance(entries, list)
    assert len(entries) > 0
    assert "ID" in entries[0]
```

---

### AC-05: DuckDB Filtering
**Given**: Valid data and SQL filter  
**When**: Filter is applied  
**Then**: 
- Results match SQL criteria
- No SQL errors occur
- Filtered count is correct

**Test**:
```python
def test_duckdb_filtering():
    data = [
        {"is_relevant_yes_percent": 75, "total_models_answered": 3},
        {"is_relevant_yes_percent": 50, "total_models_answered": 2}
    ]
    filter_clause = "is_relevant_yes_percent >= 65 AND total_models_answered >= 2"
    filtered = apply_duckdb_filter(data, filter_clause)
    assert len(filtered) == 1
    assert filtered[0]["is_relevant_yes_percent"] == 75
```

---

### AC-06: Entry Matching - DOI
**Given**: JSON record with DOI and matching BibTeX entry  
**When**: Matching is performed  
**Then**: 
- Entry is matched by DOI
- Match is recorded in statistics

**Test**:
```python
def test_doi_matching():
    json_data = [{"doi": "10.1234/example", "id": "Test2024"}]
    bibtex_data = [{"doi": "10.1234/example", "ID": "Test2024"}]
    matched, stats = match_bibtex_entries(json_data, bibtex_data)
    assert len(matched) == 1
    assert stats.doi_matches == 1
```

---

### AC-07: Entry Matching - Title
**Given**: JSON record with title and matching BibTeX entry (no DOI)  
**When**: Matching is performed  
**Then**: 
- Entry is matched by normalized title
- Match is recorded in statistics

**Test**:
```python
def test_title_matching():
    json_data = [{"article_title": "Machine Learning", "doi": ""}]
    bibtex_data = [{"title": "Machine Learning", "doi": "", "ID": "ML2024"}]
    matched, stats = match_bibtex_entries(json_data, bibtex_data)
    assert len(matched) == 1
    assert stats.title_matches == 1
```

---

### AC-08: Entry Matching - ID
**Given**: JSON record with ID and matching BibTeX entry (no DOI/title match)  
**When**: Matching is performed  
**Then**: 
- Entry is matched by BibTeX ID
- Match is recorded in statistics

**Test**:
```python
def test_id_matching():
    json_data = [{"id": "Test2024", "doi": "", "article_title": ""}]
    bibtex_data = [{"ID": "Test2024", "doi": "", "title": ""}]
    matched, stats = match_bibtex_entries(json_data, bibtex_data)
    assert len(matched) == 1
    assert stats.id_matches == 1
```

---

### AC-09: Unmatched Entry Handling
**Given**: JSON record with no matching BibTeX entry  
**When**: Matching is performed  
**Then**: 
- Unmatched count is incremented
- No error is raised
- Warning is logged

**Test**:
```python
def test_unmatched_handling():
    json_data = [{"id": "NoMatch", "doi": "", "article_title": ""}]
    bibtex_data = [{"ID": "Different", "doi": "", "title": ""}]
    matched, stats = match_bibtex_entries(json_data, bibtex_data)
    assert len(matched) == 0
    assert stats.unmatched == 1
```

---

### AC-10: Output File Generation
**Given**: Filtered JSON and matched BibTeX entries  
**When**: Outputs are written  
**Then**: 
- JSON file is created with correct structure
- BibTeX file is created with correct format
- File paths are valid
- Files are readable

**Test**:
```python
def test_output_generation(tmp_path):
    filtered_json = [{"id": "Test", "doi": "10.1234/test"}]
    matched_bib = [{"ID": "Test", "doi": "10.1234/test"}]
    
    json_path = tmp_path / "output.json"
    bib_path = tmp_path / "output.bib"
    
    write_filtered_outputs(filtered_json, matched_bib, str(json_path), str(bib_path))
    
    assert json_path.exists()
    assert bib_path.exists()
    
    with open(json_path) as f:
        data = json.load(f)
    assert len(data) == 1
```

---

### AC-11: CLI Integration
**Given**: Script integrated into `aneta.py`  
**When**: `uv run python aneta.py --filter_relevant_papers` is executed  
**Then**: 
- Script executes successfully
- Outputs are generated
- Statistics are displayed
- Exit code is 0

**Test**:
```bash
# Manual test
uv run python aneta.py --filter_relevant_papers
# Expected: Success message and output files created
```

---

### AC-12: Error Handling - Missing Config
**Given**: `.conf` file does not exist  
**When**: Script is executed  
**Then**: 
- FileNotFoundError is raised
- Clear error message is displayed
- No partial outputs are created

**Test**:
```python
def test_missing_config(monkeypatch):
    monkeypatch.delenv("PATH_DATA", raising=False)
    with pytest.raises(FileNotFoundError):
        load_configuration()
```

---

### AC-13: Error Handling - Invalid SQL
**Given**: YAML contains invalid SQL syntax  
**When**: Filter is applied  
**Then**: 
- DuckDB exception is caught
- Clear error message is displayed
- Script exits gracefully

**Test**:
```python
def test_invalid_sql():
    data = [{"field": "value"}]
    invalid_filter = "INVALID SQL SYNTAX"
    with pytest.raises(Exception) as exc:
        apply_duckdb_filter(data, invalid_filter)
    assert "SQL" in str(exc.value)
```

---

## 9. RISKS, ASSUMPTIONS, AND IMPACTS

### 9.1 Risks

#### Risk 1: Data Schema Mismatch
**Description**: JSON schema from LLM processing may change over time  
**Probability**: Medium  
**Impact**: High  
**Mitigation**:
- Use defensive programming (check field existence)
- Log missing fields
- Document expected schema in code
- Add schema validation function

#### Risk 2: Matching Accuracy
**Description**: Normalized matching may produce false positives/negatives  
**Probability**: Low  
**Impact**: Medium  
**Mitigation**:
- Prioritize DOI matching (most reliable)
- Use strict normalization rules
- Log all unmatched entries for review
- Provide manual override option

#### Risk 3: Performance Degradation
**Description**: Large datasets (>10,000 records) may exceed performance targets  
**Probability**: Low  
**Impact**: Low  
**Mitigation**:
- Use DuckDB for efficient SQL execution
- Implement lookup dictionaries for matching
- Profile code to identify bottlenecks
- Consider batch processing for very large datasets

#### Risk 4: SQL Injection
**Description**: User-provided SQL in YAML could cause security issues  
**Probability**: Very Low  
**Impact**: Medium  
**Mitigation**:
- YAML is controlled by researchers (trusted input)
- DuckDB operates on in-memory data only
- No external database connections
- Consider SQL validation if needed

### 9.2 Assumptions

#### Assumption 1: Data Availability
**Statement**: Input files (JSON and BibTeX) exist and are valid  
**Validation**: File existence checks and format validation  
**Fallback**: Clear error messages guide user to correct issues

#### Assumption 2: Configuration Consistency
**Statement**: `.conf` variables match YAML filter field names  
**Validation**: Document expected field names  
**Fallback**: Provide example configurations

#### Assumption 3: Unicode Support
**Statement**: All text data is UTF-8 compatible  
**Validation**: Encoding detection with chardet fallback  
**Fallback**: Log encoding issues and attempt best-effort processing

#### Assumption 4: Unique Identifiers
**Statement**: DOIs and titles are sufficiently unique for matching  
**Validation**: Log duplicate matches  
**Fallback**: Use hierarchical matching (DOI > Title > ID)

### 9.3 Impacts

#### Impact on Existing Code
- **None**: New module does not modify existing code
- **Integration**: Minimal changes to `aneta.py` (add CLI argument)
- **Dependencies**: No new external dependencies required

#### Impact on Workflow
- **Positive**: Automates manual filtering step
- **Positive**: Improves reproducibility through configuration
- **Neutral**: Adds one step to execution workflow

#### Impact on Data
- **Positive**: Generates structured filtered outputs
- **Positive**: Maintains data consistency between JSON and BibTeX
- **None**: Does not modify source files

#### Impact on Users
- **Positive**: Reduces manual paper selection time
- **Positive**: Provides transparent filtering criteria
- **Positive**: Generates reusable output files
- **Learning Curve**: Minimal (follows existing CLI pattern)

---

## 10. IMPLEMENTATION TIMELINE (Estimate)

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| **Phase 1: Setup** | Environment setup, file structure | 1 hour |
| **Phase 2: Core Functions** | Configuration loading, path construction, data loading | 3 hours |
| **Phase 3: Filtering Logic** | DuckDB integration, SQL execution | 2 hours |
| **Phase 4: Matching Logic** | Entry matching with 3-tier strategy | 3 hours |
| **Phase 5: Output Generation** | JSON and BibTeX writing | 1 hour |
| **Phase 6: CLI Integration** | aneta.py modifications | 1 hour |
| **Phase 7: Error Handling** | Exception handling, validation | 2 hours |
| **Phase 8: Logging & Reporting** | Statistics display, console output | 1 hour |
| **Phase 9: Testing** | Unit tests, integration tests | 3 hours |
| **Phase 10: Documentation** | Code comments, docstrings, README | 2 hours |
| **Total** | | **~19 hours** |

**Note**: Timeline assumes single developer working sequentially. Actual time may vary based on developer experience and unexpected issues.

---

## 11. REFERENCES AND DOCUMENTATION

### 11.1 Internal References
- **aneta.py**: Main CLI script with integration pattern
- **src/Selection.py**: DuckDB filtering example
- **src/BibTex.py**: BibTeX I/O utilities
- **src/GenerativeAI/LLMUtilExcel.py**: JSON schema generation
- **config/filter_accept_results_llm.yaml**: Example filter configuration
- **.conf**: Environment variable configuration

### 11.2 External References
- **DuckDB Documentation**: https://duckdb.org/docs/
- **bibtexparser Documentation**: https://bibtexparser.readthedocs.io/
- **Python dotenv**: https://pypi.org/project/python-dotenv/
- **PyYAML Documentation**: https://pyyaml.org/wiki/PyYAMLDocumentation

### 11.3 Standards and Best Practices
- **PEP 8**: Python style guide
- **PEP 484**: Type hints
- **Google Python Style Guide**: Docstring format
- **Project Coding Standards**: `.github/copilot-instructions.md`

---

## 12. APPENDICES

### Appendix A: Example Configuration Files

#### .conf
```properties
PATH_DATA=".data"
BIB_FILE="OUTPUTS/select_bibs.bib"
FILTER_LLM_RESPONSES_ABSTRACT_PATH="OUTPUTS/processed_responses/combined_responses_consolidated.json"
RELEVANT_ABSTRACT_PAPERS_OUTPUT="OUTPUTS/relevant_papers.json"
RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT="OUTPUTS/relevant_abstract_papers.bib"
FILTER_LLM_CONFIG_PATH="config/filter_accept_results_llm.yaml"
```

#### config/filter_accept_results_llm.yaml
```yaml
# Filter configuration for LLM responses
# SQL WHERE clause applied to consolidated response data

filter: >
  ((is_relevant_yes_percent >= 65
  AND total_models_answered >= 2)
  AND
  (
    principal_research_question_yes_percent >= 65
    AND principal_research_question_total_count >= 2
  ))
```

### Appendix B: Example Execution

```bash
# Activate virtual environment
source .venv/bin/activate

# Run filtering script
uv run python aneta.py --filter_relevant_papers

# Expected output:
# === Filter Relevant Papers ===
# Configuration loaded from: .conf
# Filter config: config/filter_accept_results_llm.yaml
# SQL Filter: ((is_relevant_yes_percent >= 65 AND total_models_answered >= 2)...)
# 
# Loading data...
# - Input JSON: 1,234 records loaded
# - Source BibTeX: 1,234 entries loaded
# 
# Applying filter...
# - Filtered records: 345 (27.9% of input)
# 
# Matching BibTeX entries...
# - DOI matches: 320 (92.8%)
# - Title matches: 20 (5.8%)
# - ID matches: 3 (0.9%)
# - Unmatched: 2 (0.6%)
# 
# Generating outputs...
# ✓ JSON output: .data/OUTPUTS/relevant_papers.json (345 records)
# ✓ BibTeX output: .data/OUTPUTS/relevant_abstract_papers.bib (343 entries)
# 
# Completed in 2.3 seconds
```

### Appendix C: Troubleshooting Guide

#### Issue: "Configuration file .conf not found"
**Solution**: Ensure `.conf` file exists in project root

#### Issue: "Key 'filter' not found in YAML config"
**Solution**: Add `filter:` key to YAML configuration file

#### Issue: "SQL filter error"
**Solution**: Validate SQL syntax in YAML configuration

#### Issue: "No records match filter criteria"
**Solution**: Adjust filter thresholds in YAML configuration

#### Issue: "High unmatched entry count"
**Solution**: Check DOI and title data quality in source files

---

## DOCUMENT APPROVAL

### Review Checklist
- [ ] Requirements are clear and complete
- [ ] Technical specifications are detailed
- [ ] Architecture is well-defined
- [ ] Acceptance criteria are testable
- [ ] Risks are identified and mitigated
- [ ] Implementation timeline is realistic
- [ ] Integration points are documented
- [ ] Error handling is comprehensive

### Stakeholder Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| **Requester** | | | |
| **Analyst** | GitHub Copilot | 2025-10-21 | ✓ |
| **Architect** | | | |
| **Developer** | | | |

---

**END OF REQUIREMENTS AND DEVELOPMENT REQUEST DOCUMENT**
