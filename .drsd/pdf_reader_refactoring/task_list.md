# TASK LIST

# PDFReader.py Refactoring Implementation

**Project**: ASRL  
**Feature**: PDF Processing with Async Batch Support  
**Creation Date**: 19 de outubro de 2025  
**Overall Status**: � In Progress  
**Last Updated**: 19 de outubro de 2025

---

## ✅ LEGEND

- 🔴 Not Started
- 🟡 In Progress
- 🟢 Completed
- ⏸️ Blocked
- ❌ Canceled

---

## 📋 PHASE 1: IMPLEMENT read_single_pdf() (4 hours)

### 1.1 � Core Function Implementation

**Status**: Completed  
**Responsible**: Development Team  
**Estimate**: 2 hours  

**Subtasks**:

- [🟢] Create function signature with type hints
- [🟢] Implement PDF file validation (exists, readable)
- [🟢] Initialize docling DocumentConverter with proper options
- [🟢] Implement PDF conversion with error handling
- [🟢] Extract markdown using `export_to_markdown()`
- [🟢] Collect metadata (filename, page_count, file_size_mb)
- [🟢] Implement processing time measurement
- [🟢] Return structured dictionary with all fields

**Acceptance Criteria**:

- ✅ Function signature matches specification: `read_single_pdf(pdf_path: str) -> Dict[str, Any]`
- ✅ Returns dictionary with 7 required fields
- ✅ Handles FileNotFoundError gracefully
- ✅ Handles docling conversion errors
- ✅ Logs start and completion of processing
- ✅ Processing time is accurate

**Files to Modify**:

- ✅ `src/PDFReader.py`

---

### 1.2 � Error Handling

**Status**: Completed  
**Responsible**: Development Team  
**Estimate**: 1 hour  

**Subtasks**:

- [🟢] Add try-except for FileNotFoundError
- [🟢] Add try-except for docling conversion errors
- [🟢] Add try-except for MemoryError
- [🟢] Implement timeout mechanism (60s default)
- [🟢] Return error dict on failure: `{"success": False, "error": "..."}`
- [🟢] Log all errors with context

**Acceptance Criteria**:

- ✅ Non-existent file returns error dict (not exception)
- ✅ Corrupted PDF returns error dict (not exception)
- ✅ Timeout errors are handled properly
- ✅ All errors are logged with appropriate level

**Files to Modify**:

- ✅ `src/PDFReader.py`

---

### 1.3 � Unit Tests for read_single_pdf()

**Status**: Completed  
**Responsible**: Development Team  
**Estimate**: 1 hour  

**Subtasks**:

- [🟢] Create test file `tests/test_pdf_reader.py`
- [🟢] Test successful PDF processing
- [🟢] Test non-existent file handling
- [🟢] Test corrupted PDF handling
- [🟢] Test metadata collection accuracy
- [🟢] Test processing time measurement
- [🟢] Create test fixtures (sample PDFs)

**Acceptance Criteria**:

- ✅ All tests pass
- ✅ Test coverage > 80% for read_single_pdf()
- ✅ Test fixtures include valid and invalid PDFs
- ✅ Tests are independent and repeatable

**Files to Create**:

- ✅ `tests/test_pdf_reader.py`
- ✅ `tests/fixtures/` (directory created)
- ✅ `tests/__init__.py`

---

## 📋 PHASE 2: IMPLEMENT read_pdfs_batch() (5 hours)

### 2.1 � Async Infrastructure

**Status**: Completed  
**Responsible**: Development Team  
**Estimate**: 2 hours  

**Subtasks**:

- [🟢] Create async function signature with type hints
- [🟢] Implement asyncio.Semaphore for concurrency control
- [🟢] Create ThreadPoolExecutor for blocking docling calls
- [🟢] Implement async wrapper for read_single_pdf()
- [🟢] Create task list for all PDFs in folder
- [🟢] Implement asyncio.gather() with return_exceptions=True

**Acceptance Criteria**:

- ✅ Function is properly async: `async def read_pdfs_batch(...)`
- ✅ Semaphore limits concurrent processing to max_concurrent
- ✅ ThreadPoolExecutor is used for CPU-bound work
- ✅ All PDFs are processed (not limited by semaphore)
- ✅ Function signature: `read_pdfs_batch(folder_path: str, max_concurrent: int = 5) -> List[Dict[str, Any]]`

**Files to Modify**:

- ✅ `src/PDFReader.py`

---

### 2.2 � Result Collection and Error Handling

**Status**: Completed  
**Responsible**: Development Team  
**Estimate**: 1.5 hours  

**Subtasks**:

- [🟢] Separate successful results from failures
- [🟢] Handle exceptions returned by asyncio.gather()
- [🟢] Check if all PDFs failed → raise RuntimeError
- [🟢] Return combined list (successful + failed)
- [🟢] Log batch processing summary
- [🟢] Validate folder exists before processing
- [🟢] Handle empty folder gracefully

**Acceptance Criteria**:

- ✅ Partial failures return all results (success + failed)
- ✅ Total failure raises RuntimeError with error details
- ✅ Empty folder returns empty list (no error)
- ✅ Invalid folder path raises ValueError
- ✅ Summary logging includes success/fail counts

**Files to Modify**:

- ✅ `src/PDFReader.py`

---

### 2.3 � Unit Tests for read_pdfs_batch()

**Status**: Completed  
**Responsible**: Development Team  
**Estimate**: 1.5 hours  

**Subtasks**:

- [🟢] Test successful batch processing (all PDFs succeed)
- [🟢] Test partial failure scenario (some PDFs fail)
- [🟢] Test total failure scenario (all PDFs fail → exception)
- [🟢] Test empty folder handling
- [🟢] Test concurrency limit is respected
- [🟢] Test with max_concurrent=1, 3, 5, 10
- [🟢] Create async test fixtures

**Acceptance Criteria**:

- ✅ All async tests pass with pytest-asyncio
- ✅ Concurrency limit is verified (may require monitoring)
- ✅ Test coverage > 80% for read_pdfs_batch()
- ✅ Tests handle async properly (await, asyncio.run)

**Files to Modify**:

- ✅ `tests/test_pdf_reader.py`

---

## 📋 PHASE 3: IMPLEMENT process_pdfs() (3 hours)

### 3.1 � Configuration Integration

**Status**: Completed  
**Responsible**: Development Team  
**Estimate**: 1 hour  

**Subtasks**:

- [🟢] Create function signature with Optional[str] mode
- [🟢] Load configuration from .conf using os.getenv()
- [🟢] Read PATH_DATA, PDF_PRE_SELECTION_FOLDER, PDF_POST_SELECTION_FOLDER
- [🟢] Read PDF_MAX_CONCURRENT (default: 5)
- [🟢] Read PDF_TIMEOUT_SECONDS (default: 60)
- [🟢] Read PDF_PROCESSING_MODE (default: "both")
- [🟢] Validate all configuration values
- [🟢] Use mode parameter if provided, else use config

**Acceptance Criteria**:

- ✅ Function signature: `process_pdfs(mode: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]`
- ✅ Configuration is read correctly from .conf
- ✅ Mode parameter overrides config if provided
- ✅ Invalid mode raises ValueError
- ✅ Missing config raises ValueError with clear message

**Files to Modify**:

- ✅ `src/PDFReader.py`
- ✅ `.conf`

---

### 3.2 � PDF Deduplication Logic

**Status**: Completed  
**Responsible**: Development Team  
**Estimate**: 1 hour  

**Subtasks**:

- [🟢] Implement _get_pdf_filenames() helper function
- [🟢] Implement _optimize_post_processing() helper function
- [🟢] Get set of PDF filenames in PRE folder
- [🟢] Filter POST folder to exclude PRE filenames
- [🟢] Log optimization results (how many PDFs skipped)
- [🟢] Handle case where folders don't exist

**Acceptance Criteria**:

- ✅ PDFs in POST that exist in PRE are not processed
- ✅ Optimization is only applied for mode "post" and "both"
- ✅ Logging clearly shows how many PDFs were skipped
- ✅ Algorithm uses set intersection for O(n) performance

**Files to Modify**:

- ✅ `src/PDFReader.py`

---

### 3.3 � Orchestration and Testing

**Status**: Completed  
**Responsible**: Development Team  
**Estimate**: 1 hour  

**Subtasks**:

- [🟢] Call read_pdfs_batch() for PRE folder if mode requires
- [🟢] Call read_pdfs_batch() for POST folder with optimization
- [🟢] Aggregate results into {"pre": [...], "post": [...]}
- [🟢] Handle case where both folders are empty
- [🟢] Write unit tests for mode="pre"
- [🟢] Write unit tests for mode="post"
- [🟢] Write unit tests for mode="both" with deduplication
- [🟢] Write test for invalid mode

**Acceptance Criteria**:

- ✅ Mode "pre" processes only PRE folder
- ✅ Mode "post" processes only POST folder (with optimization)
- ✅ Mode "both" processes both folders (with optimization)
- ✅ Invalid mode raises ValueError
- ✅ Return structure matches specification
- ✅ Test coverage > 80%

**Files to Modify**:

- ✅ `src/PDFReader.py`
- ✅ `tests/test_pdf_reader.py`

---

## 📋 PHASE 4: INTEGRATION WITH aneta.py (3 hours)

### 4.1 🔴 Update aneta.py

**Status**: Not Started  
**Responsible**: Development Team  
**Estimate**: 1 hour  

**Subtasks**:

- [ ] Import new process_pdfs function
- [ ] Modify run_pdf_reader() to use process_pdfs()
- [ ] Remove old calls to read_pdfs_with_docling()
- [ ] Add result logging (summary of processing)
- [ ] Add error handling with try-except
- [ ] Update CLI argument handler
- [ ] Test manual mode override via CLI

**Acceptance Criteria**:

- run_pdf_reader() successfully calls process_pdfs()
- Results are logged clearly (success/failure counts)
- Errors are caught and logged properly
- Function returns bool (True/False)
- CLI argument --read_pdfs works correctly

**Files to Modify**:

- `aneta.py`

---

### 4.2 🔴 Update .conf File

**Status**: Not Started  
**Responsible**: Development Team  
**Estimate**: 0.5 hours  

**Subtasks**:

- [ ] Add PDF_MAX_CONCURRENT=5 to .conf
- [ ] Add PDF_TIMEOUT_SECONDS=60 to .conf
- [ ] Add PDF_PROCESSING_MODE="both" to .conf
- [ ] Add comments explaining each variable
- [ ] Test that configuration is read correctly

**Acceptance Criteria**:

- All 3 new variables are in .conf
- Default values are reasonable
- Comments explain purpose of each variable
- process_pdfs() reads values correctly

**Files to Modify**:

- `.conf`

---

### 4.3 🔴 Integration Tests

**Status**: Not Started  
**Responsible**: Development Team  
**Estimate**: 1.5 hours  

**Subtasks**:

- [ ] Create integration test setup (folders + PDFs)
- [ ] Test run_pdf_reader() end-to-end
- [ ] Test CLI execution: python aneta.py --read_pdfs
- [ ] Test with different .conf configurations
- [ ] Test error handling when folders don't exist
- [ ] Verify no markdown files are created
- [ ] Verify data is returned correctly

**Acceptance Criteria**:

- Integration tests pass with real PDFs
- CLI execution works correctly
- No markdown files are created (data only in memory)
- Error scenarios are handled gracefully
- Tests are repeatable and isolated

**Files to Modify**:

- `tests/test_integration_pdf_reader.py` (new)

---

## 📋 PHASE 5: CODE REVIEW AND DOCUMENTATION (4 hours)

### 5.1 🔴 Code Quality Review

**Status**: Not Started  
**Responsible**: Development Team  
**Estimate**: 2 hours  

**Subtasks**:

- [ ] Review all type hints are complete and correct
- [ ] Review error handling is comprehensive
- [ ] Review logging is structured and useful
- [ ] Check code follows project style guidelines
- [ ] Ensure backward compatibility is maintained
- [ ] Run linters (flake8, mypy, black)
- [ ] Address any code quality issues

**Acceptance Criteria**:

- All type hints pass mypy static analysis
- Code follows PEP 8 style guide
- No linting errors
- Logging is consistent and informative
- No breaking changes to existing API

**Files to Review**:

- `src/PDFReader.py`
- `aneta.py`
- All test files

---

### 5.2 🔴 Performance Testing

**Status**: Not Started  
**Responsible**: Development Team  
**Estimate**: 1 hour  

**Subtasks**:

- [ ] Create performance test with 100 PDFs
- [ ] Measure processing time (target: < 5 minutes)
- [ ] Measure memory usage (target: < 2GB)
- [ ] Test with different max_concurrent values (1, 5, 10)
- [ ] Document performance results
- [ ] Optimize if benchmarks not met

**Acceptance Criteria**:

- 100 PDFs processed in < 5 minutes
- Memory usage < 2GB during processing
- Performance is consistent across runs
- Optimal max_concurrent value identified

**Files to Create**:

- `tests/test_performance_pdf_reader.py`

---

### 5.3 🔴 Documentation Updates

**Status**: Not Started  
**Responsible**: Development Team  
**Estimate**: 1 hour  

**Subtasks**:

- [ ] Update function docstrings in PDFReader.py
- [ ] Add usage examples in docstrings
- [ ] Update README.md with new functionality
- [ ] Document configuration variables
- [ ] Add troubleshooting section
- [ ] Document performance characteristics
- [ ] Add migration guide from old to new functions

**Acceptance Criteria**:

- All functions have complete docstrings
- README.md includes usage examples
- Configuration is well documented
- Migration guide is clear and actionable

**Files to Modify**:

- `src/PDFReader.py` (docstrings)
- `README.md`
- `.drsd/pdf_reader_refactoring/` (this folder)

---

## 📊 PROGRESS SUMMARY

| Phase | Tasks | Status | Progress |
|-------|-------|--------|----------|
| Phase 1: read_single_pdf() | 3 | 🟢 | 3/3 (100%) |
| Phase 2: read_pdfs_batch() | 3 | 🟢 | 3/3 (100%) |
| Phase 3: process_pdfs() | 3 | � | 3/3 (100%) |
| Phase 4: Integration | 3 | 🔴 | 0/3 (0%) |
| Phase 5: Review & Docs | 3 | 🔴 | 0/3 (0%) |

**Overall Progress**: 9/15 tasks completed (60%)

---

## 📝 IMPLEMENTATION NOTES

### Order of Implementation

1. Start with Phase 1 (read_single_pdf) - foundation
2. Move to Phase 2 (async batch) - builds on Phase 1
3. Implement Phase 3 (orchestrator) - uses Phase 1 & 2
4. Integrate with Phase 4 (aneta.py) - uses Phase 3
5. Finalize with Phase 5 (review & docs) - validates everything

### Critical Dependencies

- Phase 2 depends on Phase 1 completion
- Phase 3 depends on Phase 2 completion
- Phase 4 depends on Phase 3 completion
- Phase 5 depends on all previous phases

### Testing Strategy

- Write tests alongside implementation (not after)
- Run tests after each subtask completion
- Integration tests only after Phase 4
- Performance tests in Phase 5

---

## 🔗 REFERENCES

- **DRSD Document**: `.drsd/pdf_reader_refactoring/drsd_pdf_reader_refactoring.md`
- **Development Request**: `.drsd/pdf_reader_refactoring/development_request.md`
- **docling Documentation**: Check pyproject.toml for version details
- **Existing Implementation**: `src/PDFReader.py` (current version)

---

**Last Updated**: 19 de outubro de 2025  
**Next Review**: After Phase 1 completion  
**Contact**: See Development Request document for questions
