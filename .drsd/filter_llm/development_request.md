# DEVELOPMENT REQUEST
## Filter LLM Responses for Relevant Papers

---

**Date**: October 21, 2025  
**Priority**: Medium  
**Estimated Effort**: ~19 hours  
**Developer Assignment**: [To be assigned]

---

## REQUEST SUMMARY

Create a Python CLI script (`src/FilterRelevantPapers.py`) that filters LLM-classified papers using configurable SQL criteria (DuckDB), then generates filtered JSON and BibTeX outputs with accurate entry matching.

This script bridges LLM classification and downstream analysis by extracting papers that meet researcher-defined relevance thresholds.

---

## BUSINESS VALUE

- **Automates** manual paper filtering step
- **Improves** reproducibility through configuration-driven filtering
- **Maintains** data consistency between JSON responses and BibTeX entries
- **Reduces** research time by programmatically applying selection criteria

---

## FUNCTIONAL REQUIREMENTS (Main Points)

### 1. Configuration Management
- Read `.conf` file using python-dotenv
- Load SQL filter from YAML configuration (`config/filter_accept_results_llm.yaml`)
- Construct file paths following project pattern: `path_data.replace(".bibs", output_path)`

### 2. Data Processing
- Load JSON from `OUTPUTS/processed_responses/combined_responses_consolidated.json`
- Load BibTeX from `OUTPUTS/select_bibs.bib` using `src/BibTex.py`
- Execute DuckDB SQL query on in-memory database
- Filter data based on YAML WHERE clause

### 3. Entry Matching (Three-Tier Strategy)
1. **Primary**: DOI matching (normalized, case-insensitive)
2. **Secondary**: Title matching (remove punctuation, normalize whitespace)
3. **Tertiary**: BibTeX ID matching (exact)

Match filtered JSON records to BibTeX entries using this hierarchical approach.

### 4. Output Generation
- **JSON**: `OUTPUTS/relevant_papers.json` (filtered records, same structure as input)
- **BibTeX**: `OUTPUTS/relevant_abstract_papers.bib` (matched entries only)
- Use `src/BibTex.write_bibtex()` for BibTeX output
- UTF-8 encoding, pretty-print JSON with `indent=2`

### 5. CLI Integration
- Add `--filter_relevant_papers` argument to `aneta.py`
- Follow existing CLI pattern from other commands
- Provide comprehensive console output with statistics

---

## TECHNICAL SPECIFICATIONS

### Implementation Location
- **Module**: `src/FilterRelevantPapers.py`
- **Integration**: `aneta.py` (add CLI argument and wrapper function)

### Key Dependencies (All Already in Project)
```python
import os, json, re, time
import yaml, duckdb, pandas as pd
from dotenv import load_dotenv
from src.BibTex import read_bibtex, write_bibtex
```

### Configuration Variables (.conf)
```properties
PATH_DATA=".data"
BIB_FILE="OUTPUTS/select_bibs.bib"
FILTER_LLM_RESPONSES_ABSTRACT_PATH="OUTPUTS/processed_responses/combined_responses_consolidated.json"
RELEVANT_ABSTRACT_PAPERS_OUTPUT="OUTPUTS/relevant_papers.json"
RELEVANT_ABSTRACT_PAPERS_BIBs_OUTPUT="OUTPUTS/relevant_abstract_papers.bib"
FILTER_LLM_CONFIG_PATH="config/filter_accept_results_llm.yaml"
```

### Example Filter Configuration (YAML)
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

### Core Functions Structure
```python
def filter_relevant_papers() -> bool:
    """Main entry point"""

def load_configuration() -> FilterConfig:
    """Load .conf and construct paths"""

def load_yaml_filter(yaml_path: str) -> str:
    """Extract SQL WHERE clause from YAML"""

def load_json_data(json_path: str) -> List[Dict]:
    """Load LLM response data"""

def load_bibtex_data(bib_path: str) -> List[Dict]:
    """Load BibTeX entries using src/BibTex.py"""

def apply_duckdb_filter(data: List[Dict], filter_clause: str) -> List[Dict]:
    """Execute SQL filter via in-memory DuckDB"""

def match_bibtex_entries(filtered_json: List[Dict], bibtex_entries: List[Dict]) -> Tuple[List[Dict], MatchingStats]:
    """Match using DOI → Title → ID hierarchy"""

def write_filtered_outputs(filtered_json: List[Dict], matched_bibtex: List[Dict], json_path: str, bib_path: str) -> None:
    """Generate JSON and BibTeX output files"""

def report_statistics(input_count: int, filtered_count: int, stats: MatchingStats, execution_time: float) -> None:
    """Display filtering statistics"""
```

---

## CRITICAL TECHNICAL POINTS

### 1. Path Construction Pattern
Follow `aneta.py` pattern:
```python
path_data = os.path.abspath(os.getenv("PATH_DATA", ".data"))
path_data = os.path.join(path_data, ".bibs")
full_path = path_data.replace(".bibs", "OUTPUTS/relevant_papers.json")
```

### 2. DuckDB Filtering Pattern
Follow `src/Selection.py` pattern:
```python
conn = duckdb.connect(':memory:')
conn.register('table_name', pd.DataFrame(data))
query = f"SELECT * FROM table_name WHERE {filter_clause}"
result_df = conn.execute(query).fetchdf()
```

### 3. Entry Matching Logic
```python
def match_entry(json_record, bibtex_entries):
    # 1. Try DOI match (normalized)
    if json_record.get('doi'):
        for bib in bibtex_entries:
            if normalize_doi(json_record['doi']) == normalize_doi(bib.get('doi', '')):
                return bib
    
    # 2. Try Title match (normalized)
    if json_record.get('article_title'):
        json_title_norm = normalize_title(json_record['article_title'])
        for bib in bibtex_entries:
            if normalize_title(bib.get('title', '')) == json_title_norm:
                return bib
    
    # 3. Try ID match (exact)
    if json_record.get('id'):
        for bib in bibtex_entries:
            if bib.get('ID') == json_record['id']:
                return bib
    
    return None  # Unmatched
```

### 4. Error Handling Requirements
- Validate file existence before operations
- Catch and display SQL syntax errors clearly
- Handle missing fields gracefully
- Log unmatched entries with details
- Create directories if needed

---

## KEY ACCEPTANCE CRITERIA

### AC-1: Configuration Loading
- ✓ Load all variables from `.conf`
- ✓ Load SQL WHERE clause from YAML
- ✓ Construct paths following project pattern

### AC-2: Data Processing
- ✓ Load JSON and BibTeX correctly
- ✓ Execute DuckDB filter without errors
- ✓ Return filtered records matching SQL criteria

### AC-3: Entry Matching
- ✓ DOI matches work with normalized comparison
- ✓ Title matches work with normalized comparison
- ✓ ID matches work with exact comparison
- ✓ Unmatched entries are tracked and logged

### AC-4: Output Generation
- ✓ JSON output preserves source structure
- ✓ BibTeX output contains matched entries only
- ✓ Files created in correct paths
- ✓ UTF-8 encoding maintained

### AC-5: CLI Integration
- ✓ `aneta.py --filter_relevant_papers` executes successfully
- ✓ Statistics displayed to console
- ✓ Exit code 0 on success

### AC-6: Performance
- ✓ Process 1,000 records in < 2 seconds
- ✓ Process 5,000 records in < 5 seconds

---

## MAIN RISKS AND ASSUMPTIONS

### Risks
1. **JSON Schema Changes**: LLM processing output schema may evolve
   - *Mitigation*: Use defensive programming, check field existence
   
2. **Matching Accuracy**: Normalized matching may have edge cases
   - *Mitigation*: Prioritize DOI, log all unmatched for review

### Assumptions
1. Input files (JSON, BibTeX) exist and are valid
2. `.conf` variables match YAML filter field names
3. DOIs and titles are sufficiently unique for matching

---

## EXAMPLE EXECUTION

```bash
# Run filtering
uv run python aneta.py --filter_relevant_papers

# Expected output:
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
✓ JSON output: .data/OUTPUTS/relevant_papers.json (345 records)
✓ BibTeX output: .data/OUTPUTS/relevant_abstract_papers.bib (343 entries)

Completed in 2.3 seconds
```

---

## CODING STANDARDS (from .github/copilot-instructions.md)

- ✅ Python 3.11+ syntax
- ✅ Type hints (typing annotations)
- ✅ Docstrings (Google/NumPy style) for all functions
- ✅ English comments and variable names
- ✅ Error handling with try-except and logging
- ✅ Standard library preference
- ✅ Run via `uv run python <script>.py`

---

## REFERENCE IMPLEMENTATIONS

### Similar Filtering Logic
- **File**: `src/Selection.py` → `pre_include_sql()` function
- **Pattern**: DuckDB in-memory database with YAML SQL filter

### BibTeX I/O
- **File**: `src/BibTex.py` → `read_bibtex()`, `write_bibtex()`
- **Pattern**: Encoding handling with chardet fallback

### CLI Integration
- **File**: `aneta.py` → Various command functions
- **Pattern**: Argparse + wrapper function + import-on-demand

### Path Construction
- **File**: `aneta.py` → Various functions
- **Pattern**: `path_data.replace(".bibs", output_relative_path)`

---

## DELIVERABLES

1. ✅ **New Module**: `src/FilterRelevantPapers.py` (fully implemented with type hints and docstrings)
2. ✅ **CLI Integration**: Modifications to `aneta.py` (add argument and wrapper function)
3. ✅ **Unit Tests**: Test suite for core functions (optional but recommended)
4. ✅ **Documentation**: Code docstrings and inline comments

---

## TESTING GUIDANCE

### Manual Testing
1. Prepare test data: sample JSON and BibTeX files
2. Create test YAML filter configuration
3. Run: `uv run python aneta.py --filter_relevant_papers`
4. Verify output files created correctly
5. Check statistics match expectations

### Unit Testing (Recommended)
- Test configuration loading
- Test path construction
- Test YAML filter loading
- Test JSON/BibTeX loading
- Test DuckDB filtering
- Test entry matching (DOI, Title, ID)
- Test output generation

---

## QUESTIONS FOR CLARIFICATION

Before starting implementation, please confirm:

1. ✅ Should unmatched entries be logged to a separate file or just console?
   - *Suggested*: Console logging with count is sufficient

2. ✅ Should the script fail if no records pass the filter?
   - *Suggested*: Warning only, generate empty output files

3. ✅ Should matching be case-sensitive for BibTeX IDs?
   - *Suggested*: Exact match (case-sensitive) for IDs

4. ✅ Should execution continue if some entries fail to match?
   - *Suggested*: Yes, log unmatched but continue processing

---

## RELATED DOCUMENTS

- **Full Requirements**: `.drsd/filter_llm/drsd_request.md`
- **Task List**: `.drsd/filter_llm/task_list.md`
- **Coding Standards**: `.github/copilot-instructions.md`

---

**IMPLEMENTATION READY**: All requirements documented. Ready for development team assignment.
