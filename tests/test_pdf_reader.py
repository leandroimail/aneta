"""
Unit tests for PDFReader module.

Tests cover:
- Single PDF processing
- Batch async processing
- Error handling
- Metadata collection
- Configuration integration
"""

import os
import sys
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PDFReader import read_single_pdf, read_pdfs_batch, process_pdfs, _get_pdf_filenames, _optimize_post_processing


class TestReadSinglePDF:
    """Test suite for read_single_pdf() function."""
    
    def test_nonexistent_file_returns_error_dict(self):
        """Test that non-existent file returns error dict instead of raising exception."""
        result = read_single_pdf("/nonexistent/path/fake.pdf")
        
        assert result["success"] is False
        assert result["error"] is not None
        assert "does not exist" in result["error"].lower()
        assert result["markdown"] == ""
        assert result["page_count"] == 0
        assert result["file_size_mb"] == 0.0
        assert result["processing_time"] >= 0
        assert result["filename"] == "fake.pdf"
    
    def test_directory_path_returns_error(self):
        """Test that passing a directory instead of file returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = read_single_pdf(tmpdir)
            
            assert result["success"] is False
            assert result["error"] is not None
            assert "not a file" in result["error"].lower()
    
    @patch('PDFReader.DocumentConverter')
    def test_successful_pdf_processing(self, mock_converter_class):
        """Test successful PDF processing with mocked docling."""
        # Create a temporary dummy PDF file with enough content
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp_pdf:
            # Write enough content to get a measurable file size
            tmp_pdf.write(b'%PDF-1.4 dummy content ' + b'X' * 1024)  # Add 1KB of data
            tmp_pdf_path = tmp_pdf.name
        
        try:
            # Mock the docling converter and document
            mock_document = Mock()
            mock_document.export_to_markdown.return_value = "# Test Markdown\n\nContent here"
            mock_document.pages = [Mock(), Mock(), Mock()]  # 3 pages
            
            mock_conversion_result = Mock()
            mock_conversion_result.document = mock_document
            
            mock_converter_instance = Mock()
            mock_converter_instance.convert.return_value = mock_conversion_result
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute
            result = read_single_pdf(tmp_pdf_path)
            
            # Assertions
            assert result["success"] is True
            assert result["error"] is None
            assert result["markdown"] == "# Test Markdown\n\nContent here"
            assert result["page_count"] == 3
            assert result["file_size_mb"] >= 0  # File size should be collected
            assert result["processing_time"] >= 0  # Can be 0 for very fast operations
            assert result["filename"] == Path(tmp_pdf_path).name
            
            # Verify docling was called correctly
            mock_converter_instance.convert.assert_called_once()
            mock_document.export_to_markdown.assert_called_once()
            
        finally:
            # Cleanup
            if os.path.exists(tmp_pdf_path):
                os.unlink(tmp_pdf_path)
    
    @patch('PDFReader.DocumentConverter')
    def test_docling_conversion_error(self, mock_converter_class):
        """Test handling of docling conversion errors."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp_pdf:
            tmp_pdf.write(b'%PDF-1.4 dummy content')
            tmp_pdf_path = tmp_pdf.name
        
        try:
            # Mock docling to raise an exception
            mock_converter_instance = Mock()
            mock_converter_instance.convert.side_effect = Exception("Docling parsing error")
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute
            result = read_single_pdf(tmp_pdf_path)
            
            # Assertions
            assert result["success"] is False
            assert result["error"] is not None
            assert "Docling conversion error" in result["error"]
            assert result["markdown"] == ""
            assert result["page_count"] == 0
            
        finally:
            if os.path.exists(tmp_pdf_path):
                os.unlink(tmp_pdf_path)
    
    @patch('PDFReader.DocumentConverter')
    def test_memory_error_handling(self, mock_converter_class):
        """Test handling of MemoryError during PDF processing."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp_pdf:
            tmp_pdf.write(b'%PDF-1.4 dummy content')
            tmp_pdf_path = tmp_pdf.name
        
        try:
            # Mock docling to raise MemoryError
            mock_converter_instance = Mock()
            mock_converter_instance.convert.side_effect = MemoryError("Out of memory")
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute
            result = read_single_pdf(tmp_pdf_path)
            
            # Assertions
            assert result["success"] is False
            assert result["error"] is not None
            assert "Memory error" in result["error"]
            
        finally:
            if os.path.exists(tmp_pdf_path):
                os.unlink(tmp_pdf_path)
    
    @patch('PDFReader.DocumentConverter')
    def test_markdown_export_error(self, mock_converter_class):
        """Test handling of markdown export errors."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp_pdf:
            tmp_pdf.write(b'%PDF-1.4 dummy content')
            tmp_pdf_path = tmp_pdf.name
        
        try:
            # Mock successful conversion but failed markdown export
            mock_document = Mock()
            mock_document.export_to_markdown.side_effect = Exception("Export failed")
            mock_document.pages = [Mock()]
            
            mock_conversion_result = Mock()
            mock_conversion_result.document = mock_document
            
            mock_converter_instance = Mock()
            mock_converter_instance.convert.return_value = mock_conversion_result
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute
            result = read_single_pdf(tmp_pdf_path)
            
            # Assertions
            assert result["success"] is False
            assert result["error"] is not None
            assert "Markdown export error" in result["error"]
            
        finally:
            if os.path.exists(tmp_pdf_path):
                os.unlink(tmp_pdf_path)
    
    @patch('PDFReader.DocumentConverter')
    def test_metadata_collection_accuracy(self, mock_converter_class):
        """Test that metadata is collected accurately."""
        # Create a temporary file with known size
        test_content = b'%PDF-1.4 ' + b'X' * 1024 * 100  # ~100KB
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp_pdf:
            tmp_pdf.write(test_content)
            tmp_pdf_path = tmp_pdf.name
        
        try:
            # Mock docling
            mock_document = Mock()
            mock_document.export_to_markdown.return_value = "# Test"
            mock_document.pages = [Mock() for _ in range(5)]  # 5 pages
            
            mock_conversion_result = Mock()
            mock_conversion_result.document = mock_document
            
            mock_converter_instance = Mock()
            mock_converter_instance.convert.return_value = mock_conversion_result
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute
            result = read_single_pdf(tmp_pdf_path)
            
            # Assertions
            assert result["success"] is True
            assert result["page_count"] == 5
            assert result["file_size_mb"] > 0.09  # Should be around 0.1 MB
            assert result["file_size_mb"] < 0.15
            assert result["processing_time"] >= 0  # Can be 0 for very fast operations
            assert result["filename"] == Path(tmp_pdf_path).name
            
        finally:
            if os.path.exists(tmp_pdf_path):
                os.unlink(tmp_pdf_path)
    
    @patch('PDFReader.DocumentConverter')
    def test_processing_time_measurement(self, mock_converter_class):
        """Test that processing time is measured correctly."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as tmp_pdf:
            tmp_pdf.write(b'%PDF-1.4 test')
            tmp_pdf_path = tmp_pdf.name
        
        try:
            # Mock docling with a small delay
            import time
            
            def slow_convert(*args, **kwargs):
                time.sleep(0.1)  # 100ms delay
                mock_document = Mock()
                mock_document.export_to_markdown.return_value = "# Test"
                mock_document.pages = [Mock()]
                mock_result = Mock()
                mock_result.document = mock_document
                return mock_result
            
            mock_converter_instance = Mock()
            mock_converter_instance.convert.side_effect = slow_convert
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute
            result = read_single_pdf(tmp_pdf_path)
            
            # Assertions
            assert result["success"] is True
            assert result["processing_time"] >= 0.1  # Should be at least 100ms
            assert isinstance(result["processing_time"], float)
            
        finally:
            if os.path.exists(tmp_pdf_path):
                os.unlink(tmp_pdf_path)
    
    def test_return_structure_completeness(self):
        """Test that returned dictionary has all required keys."""
        result = read_single_pdf("/nonexistent/file.pdf")
        
        required_keys = {
            "markdown", "filename", "page_count", 
            "processing_time", "file_size_mb", 
            "success", "error"
        }
        
        assert set(result.keys()) == required_keys
        assert isinstance(result["markdown"], str)
        assert isinstance(result["filename"], str)
        assert isinstance(result["page_count"], int)
        assert isinstance(result["processing_time"], float)
        assert isinstance(result["file_size_mb"], float)
        assert isinstance(result["success"], bool)
        assert result["error"] is None or isinstance(result["error"], str)


class TestReadPDFsBatch:
    """Test suite for read_pdfs_batch() async function."""
    
    @pytest.mark.asyncio
    async def test_nonexistent_folder_raises_valueerror(self):
        """Test that non-existent folder raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await read_pdfs_batch("/nonexistent/folder/path")
        
        assert "does not exist" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_file_path_instead_of_folder_raises_valueerror(self):
        """Test that passing a file instead of folder raises ValueError."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file_path = tmp_file.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                await read_pdfs_batch(tmp_file_path)
            
            assert "not a directory" in str(exc_info.value).lower()
        finally:
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
    
    @pytest.mark.asyncio
    async def test_empty_folder_returns_empty_list(self):
        """Test that empty folder returns empty list without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = await read_pdfs_batch(tmpdir)
            
            assert results == []
            assert isinstance(results, list)
    
    @pytest.mark.asyncio
    @patch('PDFReader.DocumentConverter')
    async def test_successful_batch_processing_all_succeed(self, mock_converter_class):
        """Test batch processing where all PDFs succeed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 3 dummy PDF files
            pdf_paths = []
            for i in range(3):
                pdf_path = Path(tmpdir) / f"test_{i}.pdf"
                with open(pdf_path, 'wb') as f:
                    f.write(b'%PDF-1.4 ' + f'test{i}'.encode() * 100)
                pdf_paths.append(pdf_path)
            
            # Mock docling to succeed for all PDFs
            def create_mock_document(page_count):
                mock_doc = Mock()
                mock_doc.export_to_markdown.return_value = f"# Test Document\n\nContent here"
                mock_doc.pages = [Mock() for _ in range(page_count)]
                mock_result = Mock()
                mock_result.document = mock_doc
                return mock_result
            
            mock_converter_instance = Mock()
            mock_converter_instance.convert.side_effect = [
                create_mock_document(2),
                create_mock_document(3),
                create_mock_document(1)
            ]
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute batch processing
            results = await read_pdfs_batch(tmpdir, max_concurrent=2)
            
            # Assertions
            assert len(results) == 3
            assert all(r["success"] for r in results)
            assert all(r["error"] is None for r in results)
            assert all(len(r["markdown"]) > 0 for r in results)
            
            # Check page counts
            page_counts = sorted([r["page_count"] for r in results])
            assert page_counts == [1, 2, 3]
    
    @pytest.mark.asyncio
    @patch('PDFReader.DocumentConverter')
    async def test_partial_failure_returns_mixed_results(self, mock_converter_class):
        """Test batch processing with some PDFs failing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 5 dummy PDF files
            for i in range(5):
                pdf_path = Path(tmpdir) / f"test_{i}.pdf"
                with open(pdf_path, 'wb') as f:
                    f.write(b'%PDF-1.4 test content')
            
            # Mock docling: succeed for 3, fail for 2
            def mock_convert_with_failures(pdf_path):
                # Fail on test_1.pdf and test_3.pdf
                if "test_1.pdf" in str(pdf_path) or "test_3.pdf" in str(pdf_path):
                    raise Exception("Simulated conversion error")
                
                # Succeed on others
                mock_doc = Mock()
                mock_doc.export_to_markdown.return_value = "# Success"
                mock_doc.pages = [Mock(), Mock()]
                mock_result = Mock()
                mock_result.document = mock_doc
                return mock_result
            
            mock_converter_instance = Mock()
            mock_converter_instance.convert.side_effect = mock_convert_with_failures
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute batch processing
            results = await read_pdfs_batch(tmpdir, max_concurrent=3)
            
            # Assertions
            assert len(results) == 5
            
            successful = [r for r in results if r["success"]]
            failed = [r for r in results if not r["success"]]
            
            assert len(successful) == 3
            assert len(failed) == 2
            
            # Check failed results have error messages
            assert all(r["error"] is not None for r in failed)
            assert all("error" in r["error"].lower() for r in failed)
    
    @pytest.mark.asyncio
    @patch('PDFReader.DocumentConverter')
    async def test_total_failure_raises_runtimeerror(self, mock_converter_class):
        """Test that all PDFs failing raises RuntimeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 3 dummy PDF files
            for i in range(3):
                pdf_path = Path(tmpdir) / f"test_{i}.pdf"
                with open(pdf_path, 'wb') as f:
                    f.write(b'%PDF-1.4 test')
            
            # Mock docling to fail for all PDFs
            mock_converter_instance = Mock()
            mock_converter_instance.convert.side_effect = Exception("All PDFs corrupted")
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute and expect RuntimeError
            with pytest.raises(RuntimeError) as exc_info:
                await read_pdfs_batch(tmpdir, max_concurrent=2)
            
            assert "all" in str(exc_info.value).lower()
            assert "failed" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    @patch('PDFReader.DocumentConverter')
    async def test_concurrency_limit_respected_max_1(self, mock_converter_class):
        """Test that concurrency limit is respected with max_concurrent=1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 3 dummy PDF files
            for i in range(3):
                pdf_path = Path(tmpdir) / f"test_{i}.pdf"
                with open(pdf_path, 'wb') as f:
                    f.write(b'%PDF-1.4 test')
            
            # Track concurrent executions
            concurrent_count = 0
            max_concurrent_seen = 0
            
            def mock_convert_tracking(*args, **kwargs):
                nonlocal concurrent_count, max_concurrent_seen
                concurrent_count += 1
                max_concurrent_seen = max(max_concurrent_seen, concurrent_count)
                
                # Simulate some processing time
                import time
                time.sleep(0.05)
                
                concurrent_count -= 1
                
                mock_doc = Mock()
                mock_doc.export_to_markdown.return_value = "# Test"
                mock_doc.pages = [Mock()]
                mock_result = Mock()
                mock_result.document = mock_doc
                return mock_result
            
            mock_converter_instance = Mock()
            mock_converter_instance.convert.side_effect = mock_convert_tracking
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute with max_concurrent=1
            results = await read_pdfs_batch(tmpdir, max_concurrent=1)
            
            # Assertions
            assert len(results) == 3
            assert all(r["success"] for r in results)
            
            # With max_concurrent=1, we should never see more than 1 concurrent
            # Note: This is a best-effort test and may not always catch violations
            assert max_concurrent_seen <= 1
    
    @pytest.mark.asyncio
    @patch('PDFReader.DocumentConverter')
    async def test_concurrency_limit_respected_max_3(self, mock_converter_class):
        """Test that concurrency limit is respected with max_concurrent=3."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 10 dummy PDF files
            for i in range(10):
                pdf_path = Path(tmpdir) / f"test_{i}.pdf"
                with open(pdf_path, 'wb') as f:
                    f.write(b'%PDF-1.4 test')
            
            # Track concurrent executions
            concurrent_count = 0
            max_concurrent_seen = 0
            lock = asyncio.Lock()
            
            def mock_convert_tracking(*args, **kwargs):
                nonlocal concurrent_count, max_concurrent_seen
                concurrent_count += 1
                if concurrent_count > max_concurrent_seen:
                    max_concurrent_seen = concurrent_count
                
                # Simulate processing time
                import time
                time.sleep(0.05)
                
                concurrent_count -= 1
                
                mock_doc = Mock()
                mock_doc.export_to_markdown.return_value = "# Test"
                mock_doc.pages = [Mock()]
                mock_result = Mock()
                mock_result.document = mock_doc
                return mock_result
            
            mock_converter_instance = Mock()
            mock_converter_instance.convert.side_effect = mock_convert_tracking
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute with max_concurrent=3
            results = await read_pdfs_batch(tmpdir, max_concurrent=3)
            
            # Assertions
            assert len(results) == 10
            assert all(r["success"] for r in results)
            
            # With max_concurrent=3, we should never see more than 3 concurrent
            # Note: This is a best-effort test
            assert max_concurrent_seen <= 3
    
    @pytest.mark.asyncio
    @patch('PDFReader.DocumentConverter')
    async def test_large_batch_processing(self, mock_converter_class):
        """Test processing a larger batch of PDFs (10 files)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 10 dummy PDF files
            for i in range(10):
                pdf_path = Path(tmpdir) / f"paper_{i:02d}.pdf"
                with open(pdf_path, 'wb') as f:
                    f.write(b'%PDF-1.4 ' + f'content{i}'.encode() * 50)
            
            # Mock docling to succeed for all
            mock_doc = Mock()
            mock_doc.export_to_markdown.return_value = "# Paper\n\nContent"
            mock_doc.pages = [Mock() for _ in range(5)]
            mock_result = Mock()
            mock_result.document = mock_doc
            
            mock_converter_instance = Mock()
            mock_converter_instance.convert.return_value = mock_result
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute batch processing
            results = await read_pdfs_batch(tmpdir, max_concurrent=5)
            
            # Assertions
            assert len(results) == 10
            assert all(r["success"] for r in results)
            assert all(r["page_count"] == 5 for r in results)
            
            # Verify all filenames are present
            filenames = {r["filename"] for r in results}
            expected_filenames = {f"paper_{i:02d}.pdf" for i in range(10)}
            assert filenames == expected_filenames
    
    @pytest.mark.asyncio
    @patch('PDFReader.DocumentConverter')
    async def test_result_structure_consistency(self, mock_converter_class):
        """Test that all results have consistent structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create PDFs
            for i in range(3):
                pdf_path = Path(tmpdir) / f"test_{i}.pdf"
                with open(pdf_path, 'wb') as f:
                    f.write(b'%PDF-1.4 test')
            
            # Mock: 1 success, 1 failure
            call_count = [0]
            
            def mock_convert_mixed(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 2:
                    raise Exception("Simulated error")
                
                mock_doc = Mock()
                mock_doc.export_to_markdown.return_value = "# Test"
                mock_doc.pages = [Mock()]
                mock_result = Mock()
                mock_result.document = mock_doc
                return mock_result
            
            mock_converter_instance = Mock()
            mock_converter_instance.convert.side_effect = mock_convert_mixed
            mock_converter_class.return_value = mock_converter_instance
            
            # Execute
            results = await read_pdfs_batch(tmpdir, max_concurrent=2)
            
            # Check all results have required keys
            required_keys = {
                "markdown", "filename", "page_count",
                "processing_time", "file_size_mb",
                "success", "error"
            }
            
            for result in results:
                assert set(result.keys()) == required_keys


class TestProcessPDFs:
    """Test suite for process_pdfs() orchestration function."""
    
    def test_invalid_mode_raises_valueerror(self):
        """Test that invalid mode raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            process_pdfs(mode="invalid_mode")
        
        assert "invalid mode" in str(exc_info.value).lower()
    
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_path_data_raises_valueerror(self):
        """Test that missing PATH_DATA configuration raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            process_pdfs()
        
        assert "path_data not found" in str(exc_info.value).lower()
    
    @patch.dict(os.environ, {
        'PATH_DATA': '/nonexistent/path',
        'PDF_PRE_SELECTION_FOLDER': 'PDFs_PreSelection',
        'PDF_POST_SELECTION_FOLDER': 'PDFs',
        'PDF_MAX_CONCURRENT': '5',
        'PDF_TIMEOUT_SECONDS': '60',
        'PDF_PROCESSING_MODE': 'both'
    })
    def test_nonexistent_base_path_raises_filenotfounderror(self):
        """Test that non-existent base path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            process_pdfs()
        
        assert "base data path does not exist" in str(exc_info.value).lower()
    
    @patch.dict(os.environ, {
        'PATH_DATA': 'invalid',
        'PDF_MAX_CONCURRENT': 'abc',
    })
    def test_invalid_max_concurrent_raises_valueerror(self):
        """Test that invalid max_concurrent value raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ['PATH_DATA'] = tmpdir
            
            with pytest.raises(ValueError) as exc_info:
                process_pdfs()
            
            assert "invalid pdf_max_concurrent" in str(exc_info.value).lower()
    
    @patch('PDFReader.DocumentConverter')
    @patch('PDFReader.asyncio.run')
    def test_mode_pre_only_processes_pre_folder(self, mock_asyncio_run, mock_converter):
        """Test that mode='pre' only processes pre-selection folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup folders
            pre_folder = Path(tmpdir) / "PDFs_PreSelection"
            post_folder = Path(tmpdir) / "PDFs"
            pre_folder.mkdir()
            post_folder.mkdir()
            
            # Create dummy PDFs
            (pre_folder / "pre1.pdf").write_bytes(b'%PDF-1.4 dummy')
            (post_folder / "post1.pdf").write_bytes(b'%PDF-1.4 dummy')
            
            # Mock async function to return results
            mock_asyncio_run.return_value = [
                {
                    "markdown": "# Pre PDF",
                    "filename": "pre1.pdf",
                    "page_count": 1,
                    "processing_time": 0.5,
                    "file_size_mb": 0.01,
                    "success": True,
                    "error": None
                }
            ]
            
            # Configure environment
            with patch.dict(os.environ, {
                'PATH_DATA': tmpdir,
                'PDF_PRE_SELECTION_FOLDER': 'PDFs_PreSelection',
                'PDF_POST_SELECTION_FOLDER': 'PDFs',
                'PDF_MAX_CONCURRENT': '5',
                'PDF_PROCESSING_MODE': 'both'
            }):
                # Execute with mode override
                results = process_pdfs(mode="pre")
            
            # Assertions
            assert len(results["pre"]) == 1
            assert len(results["post"]) == 0
            assert results["pre"][0]["filename"] == "pre1.pdf"
    
    @patch('PDFReader.DocumentConverter')
    @patch('PDFReader.asyncio.run')
    def test_mode_post_only_processes_post_folder(self, mock_asyncio_run, mock_converter):
        """Test that mode='post' only processes post-selection folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup folders
            pre_folder = Path(tmpdir) / "PDFs_PreSelection"
            post_folder = Path(tmpdir) / "PDFs"
            pre_folder.mkdir()
            post_folder.mkdir()
            
            # Create dummy PDFs
            (pre_folder / "pre1.pdf").write_bytes(b'%PDF-1.4 dummy')
            (post_folder / "post1.pdf").write_bytes(b'%PDF-1.4 dummy')
            
            # Mock async function to return results
            mock_asyncio_run.return_value = [
                {
                    "markdown": "# Post PDF",
                    "filename": "post1.pdf",
                    "page_count": 1,
                    "processing_time": 0.5,
                    "file_size_mb": 0.01,
                    "success": True,
                    "error": None
                }
            ]
            
            # Configure environment
            with patch.dict(os.environ, {
                'PATH_DATA': tmpdir,
                'PDF_PRE_SELECTION_FOLDER': 'PDFs_PreSelection',
                'PDF_POST_SELECTION_FOLDER': 'PDFs',
                'PDF_MAX_CONCURRENT': '5',
                'PDF_PROCESSING_MODE': 'both'
            }):
                # Execute with mode override
                results = process_pdfs(mode="post")
            
            # Assertions
            assert len(results["pre"]) == 0
            assert len(results["post"]) == 1
            assert results["post"][0]["filename"] == "post1.pdf"
    
    @patch('PDFReader.DocumentConverter')
    @patch('PDFReader.asyncio.run')
    def test_mode_both_applies_deduplication(self, mock_asyncio_run, mock_converter):
        """Test that mode='both' applies deduplication to post folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup folders
            pre_folder = Path(tmpdir) / "PDFs_PreSelection"
            post_folder = Path(tmpdir) / "PDFs"
            pre_folder.mkdir()
            post_folder.mkdir()
            
            # Create dummy PDFs - duplicate.pdf exists in both
            (pre_folder / "duplicate.pdf").write_bytes(b'%PDF-1.4 dummy')
            (pre_folder / "pre_only.pdf").write_bytes(b'%PDF-1.4 dummy')
            (post_folder / "duplicate.pdf").write_bytes(b'%PDF-1.4 dummy')
            (post_folder / "post_only.pdf").write_bytes(b'%PDF-1.4 dummy')
            
            # Mock async function - first call for pre, second for post
            mock_asyncio_run.side_effect = [
                # Pre-selection results (both files)
                [
                    {
                        "markdown": "# Pre",
                        "filename": "duplicate.pdf",
                        "page_count": 1,
                        "processing_time": 0.5,
                        "file_size_mb": 0.01,
                        "success": True,
                        "error": None
                    },
                    {
                        "markdown": "# Pre Only",
                        "filename": "pre_only.pdf",
                        "page_count": 1,
                        "processing_time": 0.5,
                        "file_size_mb": 0.01,
                        "success": True,
                        "error": None
                    }
                ],
                # Post-selection results (only post_only.pdf - duplicate filtered out)
                [
                    {
                        "markdown": "# Post Only",
                        "filename": "post_only.pdf",
                        "page_count": 1,
                        "processing_time": 0.5,
                        "file_size_mb": 0.01,
                        "success": True,
                        "error": None
                    }
                ]
            ]
            
            # Configure environment
            with patch.dict(os.environ, {
                'PATH_DATA': tmpdir,
                'PDF_PRE_SELECTION_FOLDER': 'PDFs_PreSelection',
                'PDF_POST_SELECTION_FOLDER': 'PDFs',
                'PDF_MAX_CONCURRENT': '5',
                'PDF_PROCESSING_MODE': 'both'
            }):
                # Execute
                results = process_pdfs(mode="both")
            
            # Assertions
            assert len(results["pre"]) == 2  # Both pre PDFs processed
            assert len(results["post"]) == 1  # Only unique post PDF processed
            
            # Verify duplicate.pdf is NOT in post results
            post_filenames = [r["filename"] for r in results["post"]]
            assert "duplicate.pdf" not in post_filenames
            assert "post_only.pdf" in post_filenames
    
    @patch('PDFReader.DocumentConverter')
    @patch('PDFReader.asyncio.run')
    def test_empty_folders_return_empty_results(self, mock_asyncio_run, mock_converter):
        """Test that empty folders return empty result lists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup empty folders
            pre_folder = Path(tmpdir) / "PDFs_PreSelection"
            post_folder = Path(tmpdir) / "PDFs"
            pre_folder.mkdir()
            post_folder.mkdir()
            
            # Mock returns empty list for empty folders
            mock_asyncio_run.return_value = []
            
            # Configure environment
            with patch.dict(os.environ, {
                'PATH_DATA': tmpdir,
                'PDF_PRE_SELECTION_FOLDER': 'PDFs_PreSelection',
                'PDF_POST_SELECTION_FOLDER': 'PDFs',
                'PDF_MAX_CONCURRENT': '5',
                'PDF_PROCESSING_MODE': 'both'
            }):
                results = process_pdfs()
            
            # Assertions
            assert len(results["pre"]) == 0
            assert len(results["post"]) == 0
    
    def test_get_pdf_filenames_helper(self):
        """Test _get_pdf_filenames() helper function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            
            # Create test PDFs
            (folder / "file1.pdf").write_bytes(b'dummy')
            (folder / "file2.pdf").write_bytes(b'dummy')
            (folder / "file3.txt").write_bytes(b'dummy')  # Not a PDF
            
            filenames = _get_pdf_filenames(folder)
            
            assert len(filenames) == 2
            assert "file1.pdf" in filenames
            assert "file2.pdf" in filenames
            assert "file3.txt" not in filenames
    
    def test_optimize_post_processing_helper(self):
        """Test _optimize_post_processing() helper function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pre_folder = Path(tmpdir) / "pre"
            post_folder = Path(tmpdir) / "post"
            pre_folder.mkdir()
            post_folder.mkdir()
            
            # Create PDFs - duplicate.pdf in both
            (pre_folder / "duplicate.pdf").write_bytes(b'dummy')
            (pre_folder / "pre_only.pdf").write_bytes(b'dummy')
            (post_folder / "duplicate.pdf").write_bytes(b'dummy')
            (post_folder / "post_unique.pdf").write_bytes(b'dummy')
            
            # Get optimized list
            optimized = _optimize_post_processing(pre_folder, post_folder)
            
            # Should only return post_unique.pdf
            assert len(optimized) == 1
            assert optimized[0].name == "post_unique.pdf"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
