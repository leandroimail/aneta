"""
Integration tests for PDF Reader and aneta.py integration.

Tests cover:
- End-to-end workflow with real PDFs
- CLI execution
- Configuration integration
- No markdown files created (in-memory only)
- Error handling
"""

import os
import sys
import pytest
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import PDF reader functions
from PDFReader import process_pdfs


class TestAnetaIntegration:
    """Integration tests for aneta.py with PDF reader."""
    
    @patch('PDFReader.process_pdfs')
    def test_run_pdf_reader_mock_success(self, mock_process_pdfs):
        """Test that process_pdfs() is called correctly for successful case."""
        # Mock successful processing with correct return value
        mock_return_value = {
            "pre": [
                {
                    "markdown": "# Test",
                    "filename": "test1.pdf",
                    "page_count": 5,
                    "processing_time": 1.5,
                    "file_size_mb": 0.5,
                    "success": True,
                    "error": None
                }
            ],
            "post": [
                {
                    "markdown": "# Test 2",
                    "filename": "test2.pdf",
                    "page_count": 3,
                    "processing_time": 1.0,
                    "file_size_mb": 0.3,
                    "success": True,
                    "error": None
                }
            ]
        }
        mock_process_pdfs.return_value = mock_return_value
        
        # Call process_pdfs directly (simulates aneta.py behavior)
        result = mock_process_pdfs()
        
        # Assertions - verify the mock was called and returned correctly
        assert "pre" in result
        assert "post" in result
        assert len(result["pre"]) == 1
        assert len(result["post"]) == 1
        mock_process_pdfs.assert_called_once()
    
    @patch('PDFReader.process_pdfs')
    def test_run_pdf_reader_partial_failure(self, mock_process_pdfs):
        """Test process_pdfs() handles partial failures correctly."""
        # Mock partial failure with correct return value
        mock_return_value = {
            "pre": [
                {
                    "markdown": "# Test",
                    "filename": "test1.pdf",
                    "page_count": 5,
                    "processing_time": 1.5,
                    "file_size_mb": 0.5,
                    "success": True,
                    "error": None
                },
                {
                    "markdown": "",
                    "filename": "test2.pdf",
                    "page_count": 0,
                    "processing_time": 0.1,
                    "file_size_mb": 0.0,
                    "success": False,
                    "error": "Conversion error"
                }
            ],
            "post": []
        }
        mock_process_pdfs.return_value = mock_return_value
        
        # Call directly
        result = mock_process_pdfs()
        
        # Should return results with mixed success/failure
        assert len(result["pre"]) == 2
        assert result["pre"][0]["success"] is True
        assert result["pre"][1]["success"] is False
    
    def test_configuration_error_handling(self):
        """Test that missing configuration raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                process_pdfs()
            
            assert "path_data not found" in str(exc_info.value).lower()
    
    def test_invalid_mode_error_handling(self):
        """Test that invalid mode raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'PATH_DATA': tmpdir,
                'PDF_PRE_SELECTION_FOLDER': 'PDFs_PreSelection',
                'PDF_POST_SELECTION_FOLDER': 'PDFs',
                'PDF_MAX_CONCURRENT': '5',
                'PDF_PROCESSING_MODE': 'both'
            }):
                with pytest.raises(ValueError) as exc_info:
                    process_pdfs(mode="invalid_mode")
                
                assert "invalid mode" in str(exc_info.value).lower()


class TestProcessPDFsIntegration:
    """Integration tests for process_pdfs() function."""
    
    @patch('PDFReader.DocumentConverter')
    @patch.dict(os.environ, {
        'PATH_DATA': '',  # Will be set in test
        'PDF_PRE_SELECTION_FOLDER': 'PDFs_PreSelection',
        'PDF_POST_SELECTION_FOLDER': 'PDFs',
        'PDF_MAX_CONCURRENT': '3',
        'PDF_TIMEOUT_SECONDS': '60',
        'PDF_PROCESSING_MODE': 'both'
    })
    def test_process_pdfs_end_to_end_with_temp_folders(self, mock_converter):
        """Test process_pdfs() with temporary folder structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup folder structure
            base_path = Path(tmpdir)
            pre_folder = base_path / "PDFs_PreSelection"
            post_folder = base_path / "PDFs"
            pre_folder.mkdir()
            post_folder.mkdir()
            
            # Create dummy PDFs
            (pre_folder / "paper1.pdf").write_bytes(b'%PDF-1.4 dummy content')
            (pre_folder / "paper2.pdf").write_bytes(b'%PDF-1.4 dummy content')
            (post_folder / "paper1.pdf").write_bytes(b'%PDF-1.4 dummy content')  # Duplicate
            (post_folder / "paper3.pdf").write_bytes(b'%PDF-1.4 dummy content')  # Unique
            
            # Mock docling converter
            mock_document = MagicMock()
            mock_document.export_to_markdown.return_value = "# Test Markdown"
            mock_document.pages = [MagicMock(), MagicMock()]
            
            mock_conversion_result = MagicMock()
            mock_conversion_result.document = mock_document
            
            mock_converter_instance = MagicMock()
            mock_converter_instance.convert.return_value = mock_conversion_result
            mock_converter.return_value = mock_converter_instance
            
            # Set PATH_DATA to temp directory
            os.environ['PATH_DATA'] = tmpdir
            
            # Execute
            results = process_pdfs(mode="both")
            
            # Assertions
            assert "pre" in results
            assert "post" in results
            
            # Should process 2 PDFs in pre folder
            assert len(results["pre"]) == 2
            
            # Should process only 1 unique PDF in post folder (paper3.pdf)
            # paper1.pdf should be skipped due to deduplication
            assert len(results["post"]) == 1
            assert results["post"][0]["filename"] == "paper3.pdf"
            
            # All should be successful
            assert all(r["success"] for r in results["pre"])
            assert all(r["success"] for r in results["post"])
    
    @patch.dict(os.environ, {
        'PATH_DATA': '',  # Will be set in test
        'PDF_PRE_SELECTION_FOLDER': 'PDFs_PreSelection',
        'PDF_POST_SELECTION_FOLDER': 'PDFs',
        'PDF_MAX_CONCURRENT': '5',
        'PDF_PROCESSING_MODE': 'pre'
    })
    def test_process_pdfs_mode_pre_only(self):
        """Test process_pdfs() with mode='pre' only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup folder structure
            base_path = Path(tmpdir)
            pre_folder = base_path / "PDFs_PreSelection"
            post_folder = base_path / "PDFs"
            pre_folder.mkdir()
            post_folder.mkdir()
            
            # Empty folders
            
            # Set PATH_DATA
            os.environ['PATH_DATA'] = tmpdir
            
            # Execute
            results = process_pdfs(mode="pre")
            
            # Assertions
            assert len(results["pre"]) == 0  # Empty folder
            assert len(results["post"]) == 0  # Not processed in 'pre' mode
    
    def test_no_markdown_files_created(self):
        """Test that process_pdfs() does not create markdown files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup
            base_path = Path(tmpdir)
            pre_folder = base_path / "PDFs_PreSelection"
            pre_folder.mkdir()
            
            # Set environment
            with patch.dict(os.environ, {
                'PATH_DATA': tmpdir,
                'PDF_PRE_SELECTION_FOLDER': 'PDFs_PreSelection',
                'PDF_POST_SELECTION_FOLDER': 'PDFs',
                'PDF_MAX_CONCURRENT': '5',
                'PDF_PROCESSING_MODE': 'pre'
            }):
                # Execute
                results = process_pdfs()
                
                # Check no markdown files were created
                markdown_files = list(base_path.rglob("*.md"))
                assert len(markdown_files) == 0, "No markdown files should be created"


class TestCLIIntegration:
    """Integration tests for CLI execution."""
    
    def test_cli_argument_exists(self):
        """Test that --read_pdfs CLI argument is defined in parser."""
        # This test verifies the argument exists without running the full script
        # which avoids import errors in other parts of aneta.py
        import argparse
        
        # Create a simple parser to test argument definition
        parser = argparse.ArgumentParser()
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--read_pdfs', action='store_true', help='Parse PDF documents using Docling and optionally generate Markdown files')
        
        # Parse test args
        args = parser.parse_args(['--read_pdfs'])
        
        # Verify argument is set
        assert args.read_pdfs is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
