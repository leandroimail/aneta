# DEVELOPMENT REQUEST

# PDFReader.py Refactoring - Async PDF Processing System

**Project**: ASRL (Automated Systematic Review Library)  
**Feature**: PDF Processing with Async Batch Support  
**Request Date**: 19 de outubro de 2025  
**Priority**: HIGH  
**Estimated Effort**: 19 hours (5 days)

---

## EXECUTIVE SUMMARY

Refatorar o módulo `src/PDFReader.py` para implementar processamento assíncrono de PDFs usando a biblioteca docling, com controle de concorrência, otimização de processamento, e retorno de dados estruturados em memória.

**Key Benefits**:

- ⚡ **10-20x faster**: Processamento paralelo vs sequencial
- 💾 **Memory efficient**: Dados retornados em memória, sem I/O desnecessário
- 🔄 **Smart optimization**: Evita reprocessamento de PDFs duplicados
- ⚙️ **Configurable**: Controle de concorrência via `.conf`

---

## REQUEST DETAILS

### What Needs to Be Built

**3 Main Functions**:

1. **`read_single_pdf(pdf_path: str) -> Dict[str, Any]`**
   - Convert single PDF to markdown
   - Return structured data with metadata
   - Handle errors gracefully

2. **`read_pdfs_batch(folder_path: str, max_concurrent: int) -> List[Dict[str, Any]]`**
   - Async batch processing
   - Concurrency control via semaphore
   - Continue on partial failures

3. **`process_pdfs(mode: Optional[str]) -> Dict[str, List[Dict[str, Any]]]`**
   - Main orchestrator
   - Read config from `.conf`
   - Optimize by filtering duplicate PDFs
   - Return structured results: `{"pre": [...], "post": [...]}`

### Integration Requirements

**Update `aneta.py`**:

- Modify `run_pdf_reader()` to use new `process_pdfs()`
- Keep backward compatibility with old function
- Add proper error handling and logging

**Update `.conf`**:

```bash
PDF_MAX_CONCURRENT=5
PDF_TIMEOUT_SECONDS=60
PDF_PROCESSING_MODE="both"
```

---

## MAIN FUNCTIONAL REQUIREMENTS

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Single PDF processing with metadata | HIGH |
| FR-02 | Async batch processing with concurrency control | HIGH |
| FR-03 | Configuration integration from `.conf` | HIGH |
| FR-04 | PDF deduplication optimization | MEDIUM |
| FR-05 | In-memory data return (no file saving) | HIGH |
| FR-06 | Support 3 modes: `pre`, `post`, `both` | HIGH |
| FR-07 | Continue on partial failures | HIGH |
| FR-08 | Exception on total failure | MEDIUM |
| FR-09 | Integration with `aneta.py` | HIGH |
| FR-10 | Configurable concurrency limit | MEDIUM |

---

## CRITICAL TECHNICAL POINTS

### 1. Async Implementation

```python
# Use asyncio.Semaphore for concurrency control
semaphore = asyncio.Semaphore(max_concurrent)

# Use ThreadPoolExecutor for blocking docling calls
with ThreadPoolExecutor() as executor:
    result = await loop.run_in_executor(executor, read_single_pdf, pdf_path)
```

### 2. PDF Deduplication

```python
# Get filenames from PRE folder
pre_names = {f.name for f in pre_folder.glob("*.pdf")}

# Filter POST folder
post_pdfs = [pdf for pdf in post_folder.glob("*.pdf") 
             if pdf.name not in pre_names]
```

### 3. Error Handling Strategy

- Single PDF failure → Return `{"success": False, "error": "..."}` (continue)
- All PDFs failure → Raise `RuntimeError` with all error details
- Partial failures → Return all results (successful + failed)

### 4. Return Structure

```python
{
    "pre": [
        {
            "markdown": str,
            "filename": str,
            "page_count": int,
            "processing_time": float,
            "file_size_mb": float,
            "success": bool,
            "error": Optional[str]
        },
        # ... more PDFs
    ],
    "post": [
        # Only PDFs NOT in pre
    ]
}
```

---

## KEY ACCEPTANCE CRITERIA

### Must Have

1. ✅ All 3 functions implemented with correct signatures
2. ✅ Async batch processing with semaphore control
3. ✅ PDF deduplication working correctly
4. ✅ Configuration read from `.conf`
5. ✅ Data returned in memory (no markdown files created)
6. ✅ Integration with `aneta.py` working
7. ✅ Type hints complete on all functions
8. ✅ Comprehensive error handling
9. ✅ Logging for monitoring and debug

### Performance Targets

- ⚡ Process 100 PDFs in < 5 minutes
- 💾 Memory usage < 2GB for 100 PDFs
- 🔄 Handle 20% failure rate gracefully

### Testing Requirements

- ✅ Unit tests for each function
- ✅ Integration test with `aneta.py`
- ✅ Error handling tests
- ✅ Performance benchmarks
- ✅ Test coverage > 80%

---

## MAIN RISKS AND ASSUMPTIONS

### Risks

| Risk | Mitigation |
|------|------------|
| Memory exhaustion with large PDFs | Enforce max_concurrent limit |
| Slow docling processing | Set 60s timeout per PDF |
| Configuration errors | Validate all config values |

### Assumptions

- PDFs are not encrypted or DRM-protected
- Average processing time: 3-5 seconds per PDF
- Users have minimum 4GB RAM
- File system has read permissions

---

## IMPLEMENTATION PHASES

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **1** | 4h | `read_single_pdf()` + unit tests |
| **2** | 5h | `read_pdfs_batch()` async + tests |
| **3** | 3h | `process_pdfs()` + optimization logic |
| **4** | 3h | `aneta.py` integration + tests |
| **5** | 4h | Code review + documentation |

**Total**: 19 hours (≈ 5 working days)

---

## FILES TO BE MODIFIED

### Primary Changes

1. **`src/PDFReader.py`** (MAJOR)
   - Add 3 new functions
   - Implement async logic
   - Add configuration validation
   - Keep backward compatibility

2. **`aneta.py`** (MINOR)
   - Update `run_pdf_reader()`
   - Add new imports
   - Improve error handling

3. **`.conf`** (MINOR)
   - Add 3 new variables

### New Files

4. **`tests/test_pdf_reader.py`** (NEW)
   - Unit tests
   - Integration tests
   - Performance tests

---

## DEPENDENCIES

### Already Available

- ✅ Python >= 3.12.7
- ✅ docling >= 2.57.0
- ✅ python-dotenv >= 1.1.1
- ✅ asyncio (standard library)
- ✅ concurrent.futures (standard library)

### To Be Added

- ⚠️ pytest-asyncio (dev dependency only)

---

## DEFINITION OF DONE

A implementação estará completa quando:

1. ✅ Todas as 3 funções principais estão implementadas
2. ✅ Todos os testes unitários passam (coverage > 80%)
3. ✅ Testes de integração com `aneta.py` passam
4. ✅ Benchmarks de performance atendem os requisitos
5. ✅ Configuração `.conf` atualizada
6. ✅ Logs estruturados implementados
7. ✅ Code review aprovado
8. ✅ Documentação atualizada
9. ✅ Função antiga mantida com deprecation warning
10. ✅ Nenhum arquivo markdown é criado (apenas retorno em memória)

---

## CONTACT AND QUESTIONS

Para esclarecimentos ou dúvidas durante a implementação:

- Consulte o DRSD completo em `.drsd/pdf_reader_refactoring/drsd_pdf_reader_refactoring.md`
- Revise os diagramas Mermaid para entender os fluxos
- Consulte a task list detalhada em `task_list.md`

---

**Document Version**: 1.1  
**Status**: ✅ Ready for Implementation  
**Next Step**: Review Task List and Begin Phase 1