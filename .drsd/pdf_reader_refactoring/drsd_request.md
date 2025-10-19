# REQUIREMENTS AND DEVELOPMENT REQUEST DOCUMENT (DRSD)

# PDFReader.py Refactoring - Docling-based PDF Processing System

**Project**: ASRL (Automated Systematic Review Library)  
**Feature**: PDF Processing with Async Batch Support  
**Creation Date**: 19 de outubro de 2025  
**Document Version**: 1.1  
**Status**: ✅ Approved

---

## 1. CONTEXT AND OBJECTIVE

### 1.1 Business Context

O projeto ASRL realiza revisões sistemáticas de literatura científica. Durante o processo, PDFs de artigos precisam ser convertidos para formato markdown para posterior análise por LLMs. O módulo atual (`src/PDFReader.py`) possui funcionalidade básica mas carece de:

- Processamento eficiente em lote
- Retorno de dados em memória
- Otimização para evitar reprocessamento
- Configurações flexíveis de concorrência

### 1.2 Current Pain Points

1. **NameError em `aneta.py`**: Funções necessárias não estão sendo exportadas corretamente
2. **Falta de Async Processing**: Processamento síncrono é lento para múltiplos PDFs
3. **Processamento Redundante**: PDFs em `post` já foram processados em `pre`, causando desperdício
4. **Falta de Retorno em Memória**: Sistema só salva arquivos, sem retornar dados para uso imediato
5. **Configuração Rígida**: Sem controle de concorrência para ambientes com recursos limitados

### 1.3 Objective

Refatorar `src/PDFReader.py` para fornecer uma API robusta, assíncrona e configurável que:

- Processe PDFs com paralelismo controlado
- Retorne dados estruturados em memória
- Otimize processamento evitando redundâncias
- Integre-se perfeitamente com `aneta.py`

---

## 2. CORE FUNCTIONALITY

### 2.1 Function Signatures

#### Function 1: `read_single_pdf(pdf_path: str) -> Dict[str, Any]`

Função base para processar um único PDF usando docling.

**Input**: Caminho para arquivo PDF  

**Output**: 

```python
{
    "markdown": str,           # Conteúdo em markdown
    "filename": str,           # Nome do arquivo
    "page_count": int,         # Número de páginas
    "processing_time": float,  # Tempo de processamento (segundos)
    "file_size_mb": float,     # Tamanho do arquivo
    "success": bool,           # Status de sucesso
    "error": Optional[str]     # Mensagem de erro (se houver)
}
```

#### Function 2: `read_pdfs_batch(folder_path: str, max_concurrent: int = 5) -> List[Dict[str, Any]]`

Processamento assíncrono em lote com controle de concorrência.

**Behavior**:

- Processa até `max_concurrent` PDFs em paralelo
- Continua processando mesmo se alguns PDFs falharem
- Lança exceção apenas se TODOS os PDFs falharem
- Retorna lista de dicionários (mesmo formato de `read_single_pdf`)

#### Function 3: `process_pdfs(mode: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]`

Orquestrador principal que integra com configuração.

**Output**:

```python
{
    "pre": [
        {
            "markdown": "...",
            "filename": "paper1.pdf",
            "page_count": 12,
            "processing_time": 3.45,
            "file_size_mb": 2.3,
            "success": True,
            "error": None
        }
    ],
    "post": [
        # Apenas PDFs que NÃO estão em 'pre'
    ]
}
```

**Optimization Logic**:

- Identifica PDFs em `PDF_PRE_SELECTION_FOLDER`
- Para modo `post` ou `both`: filtra PDFs já existentes em `pre`
- Processa apenas PDFs únicos em cada categoria

---

## 3. ARCHITECTURE DIAGRAMS (Mermaid)

### 3.1 High-Level Architecture

```mermaid
graph TB
    User[User] --> Aneta[aneta.py]
    Aneta --> RunPDF[run_pdf_reader]
    RunPDF --> Conf[Load .conf]
    RunPDF --> Process[process_pdfs mode]
    
    Process --> ValidateConf[Validate Configuration]
    ValidateConf --> DetermineMode[Determine Folders Based on Mode]
    
    DetermineMode --> PreFolder[PRE Folder Processing]
    DetermineMode --> PostFolder[POST Folder Processing]
    
    PreFolder --> OptimizePre[List All PDFs in PRE]
    PostFolder --> OptimizePost[Optimize: Filter Duplicates]
    
    OptimizePre --> BatchPre[read_pdfs_batch PRE]
    OptimizePost --> BatchPost[read_pdfs_batch POST]
    
    BatchPre --> Results[Aggregate Results]
    BatchPost --> Results
    
    Results --> Return[Return Dict pre, post]
    Return --> Aneta
    
    BatchPre --> SinglePDF1[read_single_pdf]
    BatchPost --> SinglePDF2[read_single_pdf]
    
    SinglePDF1 --> Docling[docling.DocumentConverter]
    SinglePDF2 --> Docling
    
    Docling --> Markdown[Export to Markdown]
    Markdown --> Metadata[Collect Metadata]
    
    style User fill:#e1f5ff
    style Process fill:#fff4e1
    style Results fill:#e8f5e9
    style Docling fill:#f3e5f5
```

### 3.2 Sequence Diagram - Main Flow

```mermaid
sequenceDiagram
    participant User
    participant Aneta as aneta.py
    participant Process as process_pdfs()
    participant Batch as read_pdfs_batch()
    participant Single as read_single_pdf()
    participant Docling as docling Library
    
    User->>Aneta: python aneta.py --read_pdfs
    Aneta->>Aneta: Load .conf configuration
    Aneta->>Process: Call process_pdfs(mode=None)
    
    Process->>Process: Read mode from .conf (both)
    Process->>Process: List PDFs in PRE folder<br/>[pdf1, pdf2, pdf3]
    Process->>Process: List PDFs in POST folder<br/>[pdf1, pdf3, pdf4]
    Process->>Process: Optimize POST: remove duplicates<br/>[pdf4]
    
    Process->>Batch: read_pdfs_batch(PRE, max_concurrent=5)
    
    par Process pdf1
        Batch->>Single: read_single_pdf(pdf1)
        Single->>Docling: Convert PDF
        Docling-->>Single: Document
        Single->>Single: Export to markdown
        Single->>Single: Collect metadata
        Single-->>Batch: Result dict
    and Process pdf2
        Batch->>Single: read_single_pdf(pdf2)
        Single->>Docling: Convert PDF
        Docling-->>Single: Document
        Single-->>Batch: Result dict
    and Process pdf3
        Batch->>Single: read_single_pdf(pdf3)
        Single->>Docling: Convert PDF
        Docling-->>Single: Document
        Single-->>Batch: Result dict
    end
    
    Batch-->>Process: List[Dict] for PRE
    
    Process->>Batch: read_pdfs_batch(POST, max_concurrent=5)
    Batch->>Single: read_single_pdf(pdf4)
    Single->>Docling: Convert PDF
    Docling-->>Single: Document
    Single-->>Batch: Result dict
    Batch-->>Process: List[Dict] for POST
    
    Process->>Process: Aggregate results<br/>{"pre": [...], "post": [...]}
    Process-->>Aneta: Return complete results
    Aneta->>Aneta: Log summary
    Aneta-->>User: ✅ Success message
```

### 3.3 Data Flow Diagram

```mermaid
flowchart TD
    Conf[.conf File] -->|Read Config| ProcessPDF[process_pdfs]
    
    ProcessPDF -->|Determine Folders| PreFolder[PRE Folder<br/>PDFs_PreSelection]
    ProcessPDF -->|Determine Folders| PostFolder[POST Folder<br/>PDFs]
    
    PreFolder -->|List Files| PreFiles["paper1.pdf<br/>paper2.pdf<br/>paper3.pdf"]
    PostFolder -->|List Files| PostFiles["paper1.pdf<br/>paper3.pdf<br/>paper4.pdf"]
    
    PreFiles -->|Process All| BatchPre[read_pdfs_batch<br/>max_concurrent=5]
    PostFiles -->|Filter Duplicates| Optimize[Optimization Logic]
    
    Optimize -->|Remove paper1, paper3| FilteredPost["paper4.pdf"]
    FilteredPost -->|Process Unique| BatchPost[read_pdfs_batch<br/>max_concurrent=5]
    
    BatchPre -->|Semaphore Control| Parallel1[Parallel Processing<br/>up to 5 PDFs]
    BatchPost -->|Semaphore Control| Parallel2[Parallel Processing<br/>up to 5 PDFs]
    
    Parallel1 --> Task1[Task 1: read_single_pdf]
    Parallel1 --> Task2[Task 2: read_single_pdf]
    Parallel1 --> Task3[Task 3: read_single_pdf]
    
    Task1 --> Docling1[docling.convert]
    Task2 --> Docling2[docling.convert]
    Task3 --> Docling3[docling.convert]
    
    Docling1 --> MD1[export_to_markdown]
    Docling2 --> MD2[export_to_markdown]
    Docling3 --> MD3[export_to_markdown]
    
    MD1 --> Result1["Dict:<br/>markdown, filename,<br/>page_count, etc."]
    MD2 --> Result2["Dict:<br/>markdown, filename,<br/>page_count, etc."]
    MD3 --> Result3["Dict:<br/>markdown, filename,<br/>page_count, etc."]
    
    Parallel2 --> Task4[Task 4: read_single_pdf]
    Task4 --> Docling4[docling.convert]
    Docling4 --> MD4[export_to_markdown]
    MD4 --> Result4["Dict:<br/>markdown, filename,<br/>page_count, etc."]
    
    Result1 --> Collect[Collect All Results]
    Result2 --> Collect
    Result3 --> Collect
    Result4 --> Collect
    
    Collect --> FinalResult["Return:<br/>{<br/>'pre': [Result1, Result2, Result3],<br/>'post': [Result4]<br/>}"]
    
    FinalResult --> Memory[Data in Memory<br/>No files saved]
    
    style Conf fill:#e3f2fd
    style Optimize fill:#fff9c4
    style Memory fill:#c8e6c9
    style FinalResult fill:#f8bbd0
```

### 3.4 Async Concurrency Control Flow

```mermaid
flowchart TD
    Start[read_pdfs_batch Starts] --> ListPDFs[List All PDFs in Folder]
    ListPDFs --> CheckEmpty{PDFs Found?}
    
    CheckEmpty -->|No| ReturnEmpty[Return Empty List]
    CheckEmpty -->|Yes| CreateSemaphore[Create Semaphore<br/>max_concurrent=5]
    
    CreateSemaphore --> CreateTasks[Create Async Tasks<br/>for All PDFs]
    CreateTasks --> TaskPool[Task Pool]
    
    TaskPool --> Task1[Task 1<br/>Acquire Semaphore]
    TaskPool --> Task2[Task 2<br/>Acquire Semaphore]
    TaskPool --> Task3[Task 3<br/>Acquire Semaphore]
    TaskPool --> Task4[Task 4<br/>Acquire Semaphore]
    TaskPool --> Task5[Task 5<br/>Acquire Semaphore]
    TaskPool --> TaskN[Task N<br/>Wait for Semaphore...]
    
    Task1 --> Process1[Process PDF 1<br/>ThreadPoolExecutor]
    Task2 --> Process2[Process PDF 2<br/>ThreadPoolExecutor]
    Task3 --> Process3[Process PDF 3<br/>ThreadPoolExecutor]
    Task4 --> Process4[Process PDF 4<br/>ThreadPoolExecutor]
    Task5 --> Process5[Process PDF 5<br/>ThreadPoolExecutor]
    
    Process1 --> Release1[Release Semaphore]
    Process2 --> Release2[Release Semaphore]
    Process3 --> Release3[Release Semaphore]
    Process4 --> Release4[Release Semaphore]
    Process5 --> Release5[Release Semaphore]
    
    Release1 --> TaskN
    Release2 --> TaskN
    Release3 --> TaskN
    Release4 --> TaskN
    Release5 --> TaskN
    
    TaskN --> ProcessN[Process PDF N<br/>ThreadPoolExecutor]
    ProcessN --> ReleaseN[Release Semaphore]
    
    Release1 --> Gather[asyncio.gather<br/>Collect All Results]
    Release2 --> Gather
    Release3 --> Gather
    Release4 --> Gather
    Release5 --> Gather
    ReleaseN --> Gather
    
    Gather --> Separate[Separate Success<br/>from Failures]
    
    Separate --> CheckAllFailed{All Failed?}
    CheckAllFailed -->|Yes| RaiseException[Raise RuntimeError<br/>with All Error Details]
    CheckAllFailed -->|No| ReturnResults[Return Successful +<br/>Failed Results]
    
    style CreateSemaphore fill:#ffecb3
    style Gather fill:#c5e1a5
    style CheckAllFailed fill:#ef9a9a
    style ReturnResults fill:#a5d6a7
```

### 3.5 PDF Deduplication Algorithm

```mermaid
flowchart TD
    Start[process_pdfs mode=both] --> GetPreFiles[Get PRE Folder PDFs]
    Start --> GetPostFiles[Get POST Folder PDFs]
    
    GetPreFiles --> PreSet["PRE Set:<br/>{paper1.pdf, paper2.pdf, paper3.pdf}"]
    GetPostFiles --> PostList["POST List:<br/>[paper1.pdf, paper3.pdf, paper4.pdf]"]
    
    PostList --> IteratePost[Iterate POST List]
    PreSet --> IteratePost
    
    IteratePost --> Check1{paper1.pdf<br/>in PRE Set?}
    Check1 -->|Yes| Skip1[Skip paper1.pdf]
    Check1 -->|No| Keep1[Keep paper1.pdf]
    
    IteratePost --> Check3{paper3.pdf<br/>in PRE Set?}
    Check3 -->|Yes| Skip3[Skip paper3.pdf]
    Check3 -->|No| Keep3[Keep paper3.pdf]
    
    IteratePost --> Check4{paper4.pdf<br/>in PRE Set?}
    Check4 -->|Yes| Skip4[Skip paper4.pdf]
    Check4 -->|No| Keep4[Keep paper4.pdf]
    
    Skip1 --> LogOptimization[Log Optimization:<br/>2 PDFs skipped]
    Skip3 --> LogOptimization
    Keep4 --> LogOptimization
    
    LogOptimization --> OptimizedPost["Optimized POST:<br/>[paper4.pdf]"]
    
    PreSet --> ProcessPre[Process All PRE PDFs]
    OptimizedPost --> ProcessPost[Process Only Optimized POST]
    
    ProcessPre --> ResultPre["PRE Results:<br/>[Dict1, Dict2, Dict3]"]
    ProcessPost --> ResultPost["POST Results:<br/>[Dict4]"]
    
    ResultPre --> Combine[Combine Results]
    ResultPost --> Combine
    
    Combine --> Final["Final Output:<br/>{<br/>'pre': [Dict1, Dict2, Dict3],<br/>'post': [Dict4]<br/>}"]
    
    style PreSet fill:#bbdefb
    style OptimizedPost fill:#fff9c4
    style LogOptimization fill:#ffccbc
    style Final fill:#c8e6c9
```

### 3.6 Error Handling Flow

```mermaid
flowchart TD
    Start[read_single_pdf] --> ValidateFile{PDF File<br/>Exists?}
    
    ValidateFile -->|No| ReturnError1["Return:<br/>{success: False,<br/>error: 'File not found'}"]
    ValidateFile -->|Yes| StartTimer[Start Processing Timer]
    
    StartTimer --> InitConverter[Initialize<br/>DocumentConverter]
    InitConverter --> TryConvert{Try Convert<br/>with Timeout}
    
    TryConvert -->|Timeout| ReturnError2["Return:<br/>{success: False,<br/>error: 'Timeout after 60s'}"]
    TryConvert -->|Corrupted PDF| ReturnError3["Return:<br/>{success: False,<br/>error: 'Conversion failed'}"]
    TryConvert -->|Success| ExportMD[Export to Markdown]
    
    ExportMD --> CollectMetadata[Collect Metadata:<br/>- page_count<br/>- file_size<br/>- processing_time]
    
    CollectMetadata --> ReturnSuccess["Return:<br/>{success: True,<br/>markdown: '...',<br/>...metadata}"]
    
    ReturnError1 --> LogError[Log Error]
    ReturnError2 --> LogError
    ReturnError3 --> LogError
    ReturnSuccess --> LogSuccess[Log Success]
    
    LogError --> BatchCollect[Batch Collector]
    LogSuccess --> BatchCollect
    
    BatchCollect --> CheckAllFailed{All PDFs<br/>Failed?}
    
    CheckAllFailed -->|Yes| RaiseException[Raise RuntimeError:<br/>'All X PDFs failed: [errors]']
    CheckAllFailed -->|No| ReturnPartial["Return Partial Results:<br/>Successful + Failed PDFs"]
    
    style ReturnError1 fill:#ffcdd2
    style ReturnError2 fill:#ffcdd2
    style ReturnError3 fill:#ffcdd2
    style ReturnSuccess fill:#c8e6c9
    style RaiseException fill:#ef5350
    style ReturnPartial fill:#fff9c4
```

---

## 4. FUNCTIONAL REQUIREMENTS

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR-01 | Processar PDF único retornando markdown e metadados | HIGH | Função retorna dicionário com 7 campos especificados |
| FR-02 | Processar múltiplos PDFs assincronamente | HIGH | Processa N PDFs em paralelo (N configurável) |
| FR-03 | Ler configurações de `.conf` | HIGH | Lê 5 variáveis de ambiente corretamente |
| FR-04 | Evitar reprocessamento de PDFs | MEDIUM | PDFs em `post` que existem em `pre` são ignorados |
| FR-05 | Retornar dados em memória (não salvar arquivos) | HIGH | Nenhum arquivo markdown é criado |
| FR-06 | Suportar 3 modos de processamento | HIGH | `pre`, `post`, `both` funcionam corretamente |
| FR-07 | Continuar processamento em caso de falha parcial | HIGH | Se 1 de 10 PDFs falhar, 9 são retornados |
| FR-08 | Lançar exceção se todos falharem | MEDIUM | Exception com detalhes de todos os erros |
| FR-09 | Integrar com `aneta.py` | HIGH | `run_pdf_reader()` usa `process_pdfs()` |
| FR-10 | Configurar limite de concorrência | MEDIUM | Variável `PDF_MAX_CONCURRENT` em `.conf` |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

| ID | Requirement | Priority | Metric |
|----|-------------|----------|--------|
| NFR-01 | Performance | HIGH | Processar 100 PDFs em < 5 minutos (avg 3s/PDF) |
| NFR-02 | Memory Efficiency | HIGH | Uso de memória < 2GB para 100 PDFs |
| NFR-03 | Error Resilience | HIGH | Sistema continua operando com 20% de falhas |
| NFR-04 | Logging | MEDIUM | Logs estruturados para debug |
| NFR-05 | Timeout per PDF | MEDIUM | 60s por PDF (configurável) |
| NFR-06 | Type Safety | HIGH | Type hints completos em todas as funções |
| NFR-07 | Backward Compatibility | LOW | Manter `read_pdfs_with_docling()` funcional |
| NFR-08 | Configuration Validation | MEDIUM | Validar caminhos e valores de .conf |

---

## 6. CONFIGURATION

### 6.1 New Variables for `.conf`

```bash
# Existing (already in .conf)
PATH_DATA=".data"
PDF_PRE_SELECTION_FOLDER="PDFs_PreSelection"
PDF_POST_SELECTION_FOLDER="PDFs"

# NEW - to be added
PDF_MAX_CONCURRENT=5           # Default: 5 PDFs in parallel
PDF_TIMEOUT_SECONDS=60         # Default: 60s per PDF
PDF_PROCESSING_MODE="both"     # Default: "both" | Options: "pre", "post", "both"
```

---

## 7. IMPLEMENTATION TIMELINE

| Phase | Tasks | Time | Priority |
|-------|-------|------|----------|
| **Phase 1** | Implement `read_single_pdf()` + tests | 4h | HIGH |
| **Phase 2** | Implement `read_pdfs_batch()` async + tests | 5h | HIGH |
| **Phase 3** | Implement `process_pdfs()` + optimization | 3h | HIGH |
| **Phase 4** | Update `aneta.py` + integration tests | 3h | HIGH |
| **Phase 5** | Code review + documentation | 4h | MEDIUM |
| **TOTAL** | | **19h** | |

**Estimated Duration**: 5 working days (4h/day)

---

## 8. RISKS AND MITIGATIONS

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| docling breaking changes | LOW | HIGH | Pin version in pyproject.toml |
| Memory exhaustion | MEDIUM | HIGH | Enforce max_concurrent limit |
| Slow processing | MEDIUM | MEDIUM | Set timeout (60s) |
| Config errors | MEDIUM | LOW | Validate all config values |

---

## 9. ACCEPTANCE CRITERIA

### 9.1 Success Criteria

- ✅ All 10 functional requirements met
- ✅ All 8 non-functional requirements met
- ✅ Unit test coverage > 80%
- ✅ Integration tests pass
- ✅ Performance benchmarks met
- ✅ Documentation complete

### 9.2 Test Scenarios

1. Process single PDF successfully
2. Process batch with all successes
3. Process batch with partial failures
4. Process batch with all failures (raises exception)
5. Mode `pre` only
6. Mode `post` only
7. Mode `both` with optimization
8. Invalid configuration handling
9. Timeout handling
10. Memory efficiency under load

---

## DOCUMENT APPROVAL

**Prepared by**: GitHub Copilot (Senior Software Architect)  
**Date**: 19 de outubro de 2025  
**Version**: 1.1  
**Status**: ✅ Approved

**Next Steps**:

1. ✅ DRSD Approved
2. ✅ Development Request Generated
3. ✅ Task List Generated
4. ⏭️ Begin Implementation