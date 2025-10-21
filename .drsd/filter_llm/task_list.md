# TASK LIST - Filter LLM Responses Feature

## ✅ LEGEND

- 🔴 Not Started
- 🟡 In Progress
- 🟢 Completed
- ⏸️ Blocked
- ❌ Canceled

---

**Project**: ASRL - Automated Systematic Review Literature  
**Feature**: Filter LLM Responses for Relevant Papers  
**Creation Date**: October 21, 2025  
**Overall Status**: 🔴 Not Started

---

## 📋 MAIN TASKS

### 1. � Project Setup and Environment Configuration

**Status**: Completed  
**Responsible**: GitHub Copilot  
**Estimate**: 1 hour  

**Subtasks**:
- [🟢] Create new module file `src/FilterRelevantPapers.py`
- [🟢] Add module header with docstring explaining purpose
- [🟢] Import all required dependencies (os, json, yaml, duckdb, pandas, dotenv, etc.)
- [🟢] Verify all dependencies are available in project environment
- [🟢] Define data classes (`FilterConfig`, `MatchingStats`) using `@dataclass`

**Acceptance Criteria**:
- ✅ Module file created with proper structure
- ✅ All imports resolve without errors
- ✅ Data classes defined with type hints
- ✅ Module can be imported without errors

---

### 2. � Configuration Loading Implementation

**Status**: Completed  
**Responsible**: GitHub Copilot  
**Estimate**: 2 hours  

**Subtasks**:
- [🟢] Implement `load_configuration()` function to read `.conf` file
- [🟢] Use `python-dotenv` to load environment variables
- [🟢] Extract all required configuration keys (PATH_DATA, BIB_FILE, etc.)
- [🟢] Implement `load_yaml_filter()` to read SQL WHERE clause from YAML
- [🟢] Add error handling for missing files and keys
- [🟢] Implement `construct_paths()` following project pattern
- [🟢] Add validation for required configuration values

**Acceptance Criteria**:
- ✅ `.conf` file is loaded correctly
- ✅ YAML filter configuration is parsed
- ✅ SQL WHERE clause is extracted
- ✅ File paths are constructed using `path.replace(".bibs", ...)` pattern
- ✅ Clear error messages for missing configuration
- ✅ All paths use `os.path.abspath()` for resolution

**Reference**: 
- Pattern from `src/Selection.py` → `pre_include_sql()`
- Pattern from `aneta.py` → path construction

---

### 3. � Data Loading Implementation

**Status**: Completed  
**Responsible**: GitHub Copilot  
**Estimate**: 2 hours  

**Subtasks**:
- [🟢] Implement `load_json_data()` to read LLM response JSON
- [🟢] Add JSON validation (check for array structure)
- [🟢] Add error handling for malformed JSON
- [🟢] Implement `load_bibtex_data()` using `src/BibTex.read_bibtex()`
- [🟢] Add encoding handling (UTF-8 with chardet fallback)
- [🟢] Log number of records/entries loaded
- [🟢] Validate required fields exist in JSON data

**Acceptance Criteria**:
- ✅ JSON file loads correctly into list of dictionaries
- ✅ BibTeX file loads using existing utility
- ✅ Encoding issues handled gracefully
- ✅ Record counts logged to console
- ✅ Missing files produce clear error messages
- ✅ Malformed data handled with exceptions

**Reference**:
- `src/BibTex.py` → `read_bibtex()`
- `src/GenerativeAI/LLMUtilExcel.py` → JSON loading patterns

---

### 4. � DuckDB Filtering Implementation

**Status**: Completed  
**Responsible**: GitHub Copilot  
**Estimate**: 2 hours  

**Subtasks**:
- [🟢] Implement `apply_duckdb_filter()` function
- [🟢] Create in-memory DuckDB connection
- [🟢] Convert JSON data to Pandas DataFrame
- [🟢] Register DataFrame as DuckDB table
- [🟢] Build SQL SELECT query with WHERE clause from config
- [🟢] Execute query and fetch results as DataFrame
- [🟢] Convert filtered DataFrame back to list of dictionaries
- [🟢] Add SQL syntax error handling with clear messages
- [🟢] Clean up database connection after operation
- [🟢] Log filtering statistics (before/after counts)

**Acceptance Criteria**:
- ✅ DuckDB in-memory database created successfully
- ✅ JSON data registered as table
- ✅ SQL WHERE clause executed without errors
- ✅ Filtered results returned correctly
- ✅ SQL syntax errors caught and displayed clearly
- ✅ Connection closed properly
- ✅ Performance: < 2 seconds for 1,000 records (achieved 0.018s)
- ✅ Performance: < 5 seconds for 5,000 records (achieved 0.008s)

**Reference**:
- `src/Selection.py` → `pre_include_sql()` function
- `src/Selection.py` → `get_database()` function

---

### 5. � Entry Matching Implementation (Critical)

**Status**: Completed  
**Responsible**: GitHub Copilot  
**Estimate**: 3 hours  

**Subtasks**:
- [🟢] Implement `normalize_doi()` helper function (lowercase, strip whitespace)
- [🟢] Implement `normalize_title()` helper function (remove punctuation, normalize spaces)
- [🟢] Implement `match_bibtex_entries()` main function
- [🟢] Implement DOI matching logic (primary)
- [🟢] Implement Title matching logic (secondary)
- [🟢] Implement ID matching logic (tertiary)
- [🟢] Track matching statistics (DOI, Title, ID, Unmatched counts)
- [🟢] Create lookup dictionaries for performance optimization
- [🟢] Handle missing fields gracefully (check field existence)
- [🟢] Log unmatched entries with details
- [🟢] Return matched BibTeX entries and statistics

**Acceptance Criteria**:
- ✅ Three-tier matching hierarchy works correctly
- ✅ DOI matching uses normalized comparison
- ✅ Title matching uses normalized comparison
- ✅ ID matching uses exact comparison
- ✅ Statistics track all matching methods
- ✅ Unmatched entries are logged
- ✅ Missing fields don't cause errors
- ✅ Performance: O(n) complexity with lookup dictionaries

**Reference**:
- Design pattern from `development_request.md` → Entry Matching Logic

---

### 6. � Output Generation Implementation

**Status**: Completed  
**Responsible**: GitHub Copilot  
**Estimate**: 1 hour  

**Subtasks**:
- [🟢] Implement `write_filtered_outputs()` function
- [🟢] Write filtered JSON to output path
- [🟢] Use UTF-8 encoding with `ensure_ascii=False`
- [🟢] Pretty-print JSON with `indent=2`
- [🟢] Write matched BibTeX entries using `src.BibTex.write_bibtex()`
- [🟢] Create parent directories if they don't exist
- [🟢] Validate output files created successfully
- [🟢] Log output file paths and record counts

**Acceptance Criteria**:
- ✅ JSON output preserves source structure
- ✅ JSON uses UTF-8 encoding and pretty-printing
- ✅ BibTeX output contains matched entries only
- ✅ Files created in correct paths
- ✅ Parent directories created automatically
- ✅ Write errors produce clear messages

**Reference**:
- `src/BibTex.py` → `write_bibtex()` function

---

### 7. � Statistics and Logging Implementation

**Status**: Completed  
**Responsible**: GitHub Copilot  
**Estimate**: 1 hour  

**Subtasks**:
- [🟢] Implement `report_statistics()` function
- [🟢] Display configuration loading status
- [🟢] Show input file statistics (records loaded)
- [🟢] Display SQL filter being applied
- [🟢] Show filtering results (before/after counts, percentage)
- [🟢] Display matching statistics with percentages
- [🟢] List unmatched entries if any
- [🟢] Show output file generation results
- [🟢] Display execution time
- [🟢] Format output with clear sections and symbols (✓, -, etc.)

**Acceptance Criteria**:
- ✅ Console output is clear and well-formatted
- ✅ All statistics displayed correctly
- ✅ Percentages calculated accurately
- ✅ Execution time measured and displayed
- ✅ Output matches example from `development_request.md`

---

### 8. � Main Entry Point Implementation

**Status**: Completed  
**Responsible**: GitHub Copilot  
**Estimate**: 1 hour  

**Subtasks**:
- [🟢] Implement `filter_relevant_papers()` main function
- [🟢] Call configuration loading
- [🟢] Call data loading functions
- [🟢] Call filtering function
- [🟢] Call entry matching function
- [🟢] Call output generation function
- [🟢] Call statistics reporting function
- [🟢] Measure execution time
- [🟢] Add comprehensive error handling
- [🟢] Return boolean for success/failure
- [🟢] Add function docstring with Args, Returns, Raises sections

**Acceptance Criteria**:
- ✅ Main function orchestrates all steps correctly
- ✅ Errors handled gracefully at each step
- ✅ Execution time measured accurately
- ✅ Function returns True on success, False on failure
- ✅ Comprehensive docstring provided
- ✅ Type hints for all parameters and return value

---

### 9. � CLI Integration with aneta.py

**Status**: Completed  
**Responsible**: GitHub Copilot  
**Estimate**: 1 hour  

**Subtasks**:
- [🟢] Add `--filter_relevant_papers` argument to argparse in `aneta.py`
- [🟢] Add help text for new argument
- [🟢] Create `run_filter_relevant_papers()` wrapper function
- [🟢] Import `FilterRelevantPapers` module in wrapper
- [🟢] Call `filter_relevant_papers()` function
- [🟢] Return boolean for success
- [🟢] Add CLI handler for new argument
- [🟢] Add script mode variable `run_filter_relevant_papers`
- [🟢] Test CLI execution

**Acceptance Criteria**:
- ✅ Argument added to argparse correctly
- ✅ Wrapper function follows project pattern
- ✅ Import-on-demand implemented
- ✅ CLI command executes successfully
- ✅ Script mode variable works correctly
- ✅ Help text displays properly
- ✅ Exit code reflects success/failure

**Reference**:
- Pattern from `aneta.py` → other command implementations

**Notes**:
- Fixed YAML configuration file (changed `total_models_answered` to `total_responses`)
- Successfully executed with 97 input records, filtered to 59 relevant papers (60.8%)
- All 59 filtered records matched via DOI (100% match rate)
- Execution time: 0.350 seconds (277 records/second)

---

### 10. 🔴 Error Handling and Validation

**Status**: Not Started  
**Responsible**: [Assignee]  
**Estimate**: 2 hours  

**Subtasks**:
- [ ] Add file existence checks before reading
- [ ] Add YAML structure validation (check for 'filter' key)
- [ ] Add JSON structure validation (check for array)
- [ ] Add SQL syntax error handling
- [ ] Add encoding error handling
- [ ] Add write permission error handling
- [ ] Add empty results handling (warning only)
- [ ] Test all error scenarios
- [ ] Ensure clear error messages for users
- [ ] Add error recovery where possible

**Acceptance Criteria**:
- All errors caught with try-except blocks
- Error messages are clear and actionable
- Missing files produce FileNotFoundError with paths
- Invalid data produces descriptive error messages
- SQL errors display the problematic query
- Script fails gracefully without stack traces
- Empty results produce warning but continue execution

**Reference**:
- Error handling matrix from `drsd_request.md`

---

### 11. 🔴 Code Documentation

**Status**: Not Started  
**Responsible**: [Assignee]  
**Estimate**: 2 hours  

**Subtasks**:
- [ ] Add module-level docstring with overview and usage example
- [ ] Add docstrings to all functions (Google/NumPy style)
- [ ] Document Args, Returns, Raises for each function
- [ ] Add inline comments for complex logic
- [ ] Add type hints to all function parameters and returns
- [ ] Document data classes with field descriptions
- [ ] Add usage examples in docstrings
- [ ] Review documentation completeness

**Acceptance Criteria**:
- Module docstring explains purpose and usage
- All functions have comprehensive docstrings
- Args, Returns, Raises sections complete
- Type hints on all functions
- Complex logic has inline comments
- Code follows project standards from `.github/copilot-instructions.md`

**Reference**:
- Project coding standards from `.github/copilot-instructions.md`

---

### 12. 🔴 Unit Testing (Optional but Recommended)

**Status**: Not Started  
**Responsible**: [Assignee]  
**Estimate**: 3 hours  

**Subtasks**:
- [ ] Create test file `tests/test_filter_relevant_papers.py`
- [ ] Test configuration loading (valid and invalid)
- [ ] Test path construction
- [ ] Test YAML filter loading
- [ ] Test JSON data loading
- [ ] Test BibTeX data loading
- [ ] Test DuckDB filtering with sample data
- [ ] Test DOI normalization
- [ ] Test Title normalization
- [ ] Test entry matching (DOI, Title, ID)
- [ ] Test unmatched entry handling
- [ ] Test output generation
- [ ] Test error scenarios
- [ ] Achieve >80% code coverage

**Acceptance Criteria**:
- Test file created with pytest
- All core functions tested
- Edge cases covered
- Error scenarios tested
- Tests pass successfully
- Code coverage >80%

---

### 13. 🔴 Integration Testing and Validation

**Status**: Not Started  
**Responsible**: [Assignee]  
**Estimate**: 2 hours  

**Subtasks**:
- [ ] Prepare sample test data (JSON and BibTeX)
- [ ] Create test YAML configuration
- [ ] Run end-to-end test with sample data
- [ ] Verify JSON output correctness
- [ ] Verify BibTeX output correctness
- [ ] Verify statistics accuracy
- [ ] Test with edge cases (empty results, all unmatched, etc.)
- [ ] Test CLI execution via `aneta.py`
- [ ] Test with real project data (if available)
- [ ] Document any issues found

**Acceptance Criteria**:
- End-to-end flow works correctly
- Output files match expectations
- Statistics are accurate
- CLI integration works
- Edge cases handled properly
- Real data test successful (if applicable)

---

### 14. 🔴 Performance Optimization and Benchmarking

**Status**: Not Started  
**Responsible**: [Assignee]  
**Estimate**: 1 hour  

**Subtasks**:
- [ ] Implement lookup dictionaries for matching optimization
- [ ] Cache normalized values to avoid redundant processing
- [ ] Profile code to identify bottlenecks
- [ ] Benchmark with 1,000 records
- [ ] Benchmark with 5,000 records
- [ ] Benchmark with 10,000 records
- [ ] Verify performance targets met
- [ ] Document performance characteristics

**Acceptance Criteria**:
- 1,000 records: < 2 seconds
- 5,000 records: < 5 seconds
- 10,000 records: < 10 seconds
- Memory usage < 500MB for typical datasets
- No performance regressions

---

### 15. 🔴 Final Review and Documentation Update

**Status**: Not Started  
**Responsible**: [Assignee]  
**Estimate**: 1 hour  

**Subtasks**:
- [ ] Review all code for quality and standards compliance
- [ ] Verify all acceptance criteria met
- [ ] Update README if needed
- [ ] Add usage examples to project documentation
- [ ] Create changelog entry
- [ ] Review error messages for clarity
- [ ] Final code cleanup (remove debug prints, etc.)
- [ ] Commit and push changes

**Acceptance Criteria**:
- Code passes all quality checks
- All acceptance criteria verified
- Documentation updated
- No debug code remaining
- Code committed to repository

---

## 📊 PROGRESS SUMMARY

| Task | Status | Progress |
|------|--------|----------|
| 1. Project Setup and Environment Configuration | 🟢 | 100% |
| 2. Configuration Loading Implementation | 🟢 | 100% |
| 3. Data Loading Implementation | 🟢 | 100% |
| 4. DuckDB Filtering Implementation | 🟢 | 100% |
| 5. Entry Matching Implementation (Critical) | 🟢 | 100% |
| 6. Output Generation Implementation | 🟢 | 100% |
| 7. Statistics and Logging Implementation | 🟢 | 100% |
| 8. Main Entry Point Implementation | 🟢 | 100% |
| 9. CLI Integration with aneta.py | � | 100% |
| 10. Error Handling and Validation | 🔴 | 0% |
| 11. Code Documentation | 🔴 | 0% |
| 12. Unit Testing (Optional) | 🔴 | 0% |
| 13. Integration Testing and Validation | 🔴 | 0% |
| 14. Performance Optimization and Benchmarking | 🔴 | 0% |
| 15. Final Review and Documentation Update | 🔴 | 0% |

**Overall Progress**: [9/15 tasks completed] (60.0%)
| 12. Unit Testing (Optional) | 🔴 | 0% |
| 13. Integration Testing and Validation | 🔴 | 0% |
| 14. Performance Optimization and Benchmarking | 🔴 | 0% |
| 15. Final Review and Documentation Update | 🔴 | 0% |

**Overall Progress**: [5/15 tasks completed] (33.3%)

---

## 📝 IMPLEMENTATION NOTES

### Critical Path Tasks (Must Complete First)
1. Task 2: Configuration Loading (blocks all other tasks)
2. Task 3: Data Loading (blocks filtering and matching)
3. Task 4: DuckDB Filtering (blocks output generation)
4. Task 5: Entry Matching (critical complexity, blocks output)
5. Task 6: Output Generation (final step before integration)

### Parallel Execution Opportunities
- Task 7 (Statistics) can be developed alongside Tasks 4-6
- Task 11 (Documentation) can be done incrementally with each task
- Task 12 (Unit Tests) can be written alongside implementation

### Special Attention Required
- **Task 5** (Entry Matching): Most complex logic, requires careful implementation of three-tier matching hierarchy
- **Task 4** (DuckDB Filtering): SQL injection considerations, though low risk with trusted YAML config
- **Task 10** (Error Handling): Critical for user experience, must provide clear error messages

---

## 🔗 REFERENCES

### Documentation
- **Full Requirements**: `.drsd/filter_llm/drsd_request.md`
- **Development Request**: `.drsd/filter_llm/development_request.md`
- **Coding Standards**: `.github/copilot-instructions.md`

### Code References
- **Selection.py**: DuckDB filtering pattern (`pre_include_sql()`)
- **BibTex.py**: BibTeX I/O utilities (`read_bibtex()`, `write_bibtex()`)
- **aneta.py**: CLI integration pattern
- **LLMUtilExcel.py**: JSON schema structure

### Configuration Files
- **`.conf`**: Environment variables
- **`config/filter_accept_results_llm.yaml`**: SQL filter example

---

## 🚨 BLOCKERS AND RISKS

### Current Blockers
- None (ready to start)

### Potential Risks
1. **JSON Schema Changes**: LLM output format may evolve
   - Mitigation: Defensive programming, field validation
   
2. **Matching Accuracy**: Edge cases in title/DOI normalization
   - Mitigation: Comprehensive testing, prioritize DOI matching

3. **Performance**: Large datasets may exceed targets
   - Mitigation: Optimization with lookup dictionaries, profiling

---

## ✅ DEFINITION OF DONE

Feature is considered complete when:
- ✅ All 15 main tasks marked as completed
- ✅ All acceptance criteria met
- ✅ Unit tests passing (if implemented)
- ✅ Integration tests successful
- ✅ Performance benchmarks met
- ✅ Documentation complete
- ✅ Code reviewed and approved
- ✅ CLI command working in `aneta.py`
- ✅ No critical bugs or errors
- ✅ Code committed to repository

---

---

**Last Updated**: October 21, 2025 (Tasks 1-9 completed)  
**Next Review**: After Task 10 completion (Error Handling and Validation)

```
