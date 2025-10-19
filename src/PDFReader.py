"""
PDF Reader module using Docling library for parsing PDF documents.

This module provides functionality to read PDF documents from configurable folders
and optionally generate Markdown files from the parsed content.
"""

import os
import logging
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, List, Dict, Any
import traceback
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def read_single_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Process a single PDF file using docling and return structured data with metadata.
    
    This function converts a PDF to markdown format and collects comprehensive metadata
    about the processing operation. It handles errors gracefully by returning an error
    dictionary instead of raising exceptions.
    
    Args:
        pdf_path (str): Absolute or relative path to the PDF file to process
        
    Returns:
        Dict[str, Any]: Dictionary containing:
            - markdown (str): Converted markdown content (empty string on error)
            - filename (str): Name of the PDF file
            - page_count (int): Number of pages in the PDF (0 on error)
            - processing_time (float): Time taken to process in seconds
            - file_size_mb (float): File size in megabytes (0.0 on error)
            - success (bool): True if processing succeeded, False otherwise
            - error (Optional[str]): Error message if processing failed, None otherwise
            
    Examples:
        >>> result = read_single_pdf("path/to/paper.pdf")
        >>> if result["success"]:
        >>>     print(f"Processed {result['page_count']} pages")
        >>>     print(result["markdown"][:100])
        >>> else:
        >>>     print(f"Error: {result['error']}")
    """
    # Initialize result structure with default values
    start_time = time.time()
    pdf_file = Path(pdf_path)
    
    result: Dict[str, Any] = {
        "markdown": "",
        "filename": pdf_file.name if pdf_file else str(pdf_path),
        "page_count": 0,
        "processing_time": 0.0,
        "file_size_mb": 0.0,
        "success": False,
        "error": None
    }
    
    try:
        # Validate PDF file exists
        if not pdf_file.exists():
            error_msg = f"PDF file does not exist: {pdf_path}"
            logger.error(error_msg)
            result["error"] = error_msg
            result["processing_time"] = time.time() - start_time
            return result
        
        # Check if path is a file (not a directory)
        if not pdf_file.is_file():
            error_msg = f"Path is not a file: {pdf_path}"
            logger.error(error_msg)
            result["error"] = error_msg
            result["processing_time"] = time.time() - start_time
            return result
        
        # Collect file size metadata
        try:
            file_size_bytes = pdf_file.stat().st_size
            result["file_size_mb"] = round(file_size_bytes / (1024 * 1024), 2)
        except Exception as e:
            logger.warning(f"Could not get file size for {pdf_file.name}: {str(e)}")
            result["file_size_mb"] = 0.0
        
        # Log processing start
        logger.info(f"Starting PDF processing: {pdf_file.name} ({result['file_size_mb']} MB)")
        
        # Initialize Docling converter with PDF-specific configuration
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True  # Enable OCR for scanned PDFs
        pipeline_options.do_table_structure = True  # Extract table structure
        
        doc_converter = DocumentConverter(
            format_options={InputFormat.PDF: pipeline_options}
        )
        
        # Convert PDF using Docling (this is the time-intensive operation)
        try:
            conversion_result = doc_converter.convert(str(pdf_file))
            document = conversion_result.document
        except MemoryError as e:
            error_msg = f"Memory error while processing {pdf_file.name}: {str(e)}"
            logger.error(error_msg)
            result["error"] = error_msg
            result["processing_time"] = time.time() - start_time
            return result
        except Exception as e:
            error_msg = f"Docling conversion error for {pdf_file.name}: {str(e)}"
            logger.error(error_msg)
            logger.debug(f"Conversion error traceback: {traceback.format_exc()}")
            result["error"] = error_msg
            result["processing_time"] = time.time() - start_time
            return result
        
        # Extract markdown content
        try:
            markdown_content = document.export_to_markdown()
            result["markdown"] = markdown_content
        except Exception as e:
            error_msg = f"Markdown export error for {pdf_file.name}: {str(e)}"
            logger.error(error_msg)
            result["error"] = error_msg
            result["processing_time"] = time.time() - start_time
            return result
        
        # Collect metadata from document
        try:
            result["page_count"] = len(document.pages)
        except Exception as e:
            logger.warning(f"Could not get page count for {pdf_file.name}: {str(e)}")
            result["page_count"] = 0
        
        # Calculate processing time
        result["processing_time"] = round(time.time() - start_time, 2)
        
        # Mark as successful
        result["success"] = True
        
        # Log success
        logger.info(
            f"Successfully processed {pdf_file.name}: "
            f"{result['page_count']} pages, "
            f"{result['processing_time']}s"
        )
        
        return result
        
    except FileNotFoundError as e:
        error_msg = f"File not found: {pdf_path}"
        logger.error(error_msg)
        result["error"] = error_msg
        result["processing_time"] = time.time() - start_time
        return result
        
    except Exception as e:
        # Catch any unexpected errors
        error_msg = f"Unexpected error processing {pdf_file.name}: {str(e)}"
        logger.error(error_msg)
        logger.debug(f"Unexpected error traceback: {traceback.format_exc()}")
        result["error"] = error_msg
        result["processing_time"] = time.time() - start_time
        return result

async def read_pdfs_batch(folder_path: str, max_concurrent: int = 5) -> List[Dict[str, Any]]:
    """
    Process multiple PDF files asynchronously with controlled concurrency.
    
    This function processes all PDF files in a folder using parallel execution,
    with a configurable limit on how many PDFs are processed simultaneously.
    It continues processing even if some PDFs fail, and only raises an exception
    if ALL PDFs fail.
    
    Args:
        folder_path (str): Path to the folder containing PDF files to process
        max_concurrent (int): Maximum number of PDFs to process concurrently (default: 5)
        
    Returns:
        List[Dict[str, Any]]: List of result dictionaries from read_single_pdf(),
                              containing both successful and failed processing results
        
    Raises:
        ValueError: If folder_path does not exist or is not a directory
        RuntimeError: If ALL PDF files fail to process (contains error details)
        
    Examples:
        >>> results = await read_pdfs_batch("/path/to/pdfs", max_concurrent=3)
        >>> successful = [r for r in results if r["success"]]
        >>> print(f"Processed {len(successful)}/{len(results)} PDFs successfully")
        
        >>> # Handle mixed results
        >>> for result in results:
        >>>     if result["success"]:
        >>>         print(f"✓ {result['filename']}: {result['page_count']} pages")
        >>>     else:
        >>>         print(f"✗ {result['filename']}: {result['error']}")
    """
    # Validate folder exists
    folder = Path(folder_path)
    if not folder.exists():
        error_msg = f"Folder does not exist: {folder_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    if not folder.is_dir():
        error_msg = f"Path is not a directory: {folder_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Find all PDF files in folder
    pdf_files = list(folder.glob("*.pdf"))
    
    # Handle empty folder - return empty list (not an error)
    if not pdf_files:
        logger.info(f"No PDF files found in folder: {folder_path}")
        return []
    
    logger.info(f"Starting batch processing: {len(pdf_files)} PDFs with max_concurrent={max_concurrent}")
    
    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Get event loop
    loop = asyncio.get_event_loop()
    
    async def process_single_pdf_async(pdf_path: Path) -> Dict[str, Any]:
        """
        Async wrapper for read_single_pdf() with semaphore control.
        
        This function ensures that only max_concurrent PDFs are processed
        at the same time by acquiring a semaphore before processing.
        """
        async with semaphore:
            logger.debug(f"Acquired semaphore for {pdf_path.name}")
            
            # Run the blocking read_single_pdf() in a thread pool
            # This prevents blocking the event loop
            with ThreadPoolExecutor(max_workers=1) as executor:
                result = await loop.run_in_executor(
                    executor,
                    read_single_pdf,
                    str(pdf_path)
                )
            
            logger.debug(f"Released semaphore for {pdf_path.name}")
            return result
    
    # Create tasks for all PDFs
    tasks = [process_single_pdf_async(pdf_file) for pdf_file in pdf_files]
    
    # Execute all tasks concurrently, capturing exceptions as results
    # return_exceptions=True prevents one failure from canceling others
    logger.info(f"Launching {len(tasks)} async tasks...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results to separate successful from failed
    processed_results = []
    exception_count = 0
    
    for i, result in enumerate(results):
        # Handle exceptions that occurred during gather
        if isinstance(result, Exception):
            exception_count += 1
            error_result = {
                "markdown": "",
                "filename": pdf_files[i].name,
                "page_count": 0,
                "processing_time": 0.0,
                "file_size_mb": 0.0,
                "success": False,
                "error": f"Unexpected exception: {str(result)}"
            }
            processed_results.append(error_result)
            logger.error(f"Exception processing {pdf_files[i].name}: {str(result)}")
        else:
            processed_results.append(result)
    
    # Count successes and failures
    successful_count = sum(1 for r in processed_results if r["success"])
    failed_count = len(processed_results) - successful_count
    
    # Log summary
    logger.info(f"Batch processing complete: {successful_count} successful, {failed_count} failed")
    
    # Check if ALL PDFs failed - this is an exceptional case
    if successful_count == 0 and len(processed_results) > 0:
        # Collect all error messages
        all_errors = [
            f"{r['filename']}: {r['error']}"
            for r in processed_results
            if not r["success"]
        ]
        error_summary = "\n".join(all_errors)
        error_msg = f"All {len(processed_results)} PDFs failed to process:\n{error_summary}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    # Return all results (successful and failed mixed)
    return processed_results

def read_pdfs_with_docling(folder_path: str, generate_markdown: bool = False, markdown_output_folder: Optional[str] = None) -> bool:
    """
    Parse PDF documents using Docling and optionally generate Markdown files.
    
    Args:
        folder_path (str): Path to the folder containing PDF files
        generate_markdown (bool): Whether to generate Markdown output files
        markdown_output_folder (str, optional): Path to save Markdown files
        
    Returns:
        bool: True if the operation was completed successfully, False otherwise
    """
    try:
        # Validate folder path
        pdf_folder = Path(folder_path)
        if not pdf_folder.exists():
            logger.warning(f"PDF folder does not exist: {folder_path}")
            logger.info(f"Creating directory: {folder_path}")
            pdf_folder.mkdir(parents=True, exist_ok=True)
            return True  # Return True as folder was created successfully
        
        if not pdf_folder.is_dir():
            logger.error(f"Path is not a directory: {folder_path}")
            return False
        
        # Find PDF files
        pdf_files = list(pdf_folder.glob("*.pdf"))
        if not pdf_files:
            logger.info(f"No PDF files found in: {folder_path}")
            return True  # Not an error, just no files to process
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        # Setup Markdown output folder if needed
        markdown_folder = None
        if generate_markdown and markdown_output_folder:
            markdown_folder = Path(markdown_output_folder)
            markdown_folder.mkdir(parents=True, exist_ok=True)
            logger.info(f"Markdown files will be saved to: {markdown_output_folder}")
        
        # Initialize Docling converter with PDF-specific configuration
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True  # Enable OCR for scanned PDFs
        pipeline_options.do_table_structure = True  # Extract table structure
        
        doc_converter = DocumentConverter(
            format_options={InputFormat.PDF: pipeline_options,}
        )
        
        # Process each PDF file
        successful_conversions = 0
        failed_conversions = 0
        
        for pdf_file in pdf_files:
            try:
                logger.info(f"Processing: {pdf_file.name}")
                
                # Convert PDF using Docling
                conversion_result = doc_converter.convert(str(pdf_file))
                document = conversion_result.document
                
                # Log basic document information
                logger.info(f"Successfully parsed PDF: {pdf_file.name}")
                logger.info(f"Document has {len(document.pages)} pages")
                
                # Generate Markdown if requested
                if generate_markdown and markdown_folder:
                    markdown_content = document.export_to_markdown()
                    
                    # Create output filename
                    markdown_filename = pdf_file.stem + ".md"
                    markdown_filepath = markdown_folder / markdown_filename
                    
                    # Write Markdown content
                    with open(markdown_filepath, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    
                    logger.info(f"Generated Markdown: {markdown_filename}")
                
                successful_conversions += 1
                
            except Exception as e:
                logger.error(f"Failed to process {pdf_file.name}: {str(e)}")
                logger.debug(f"Error traceback: {traceback.format_exc()}")
                failed_conversions += 1
                continue
        
        # Summary logging
        logger.info(f"PDF processing completed:")
        logger.info(f"  - Successful conversions: {successful_conversions}")
        logger.info(f"  - Failed conversions: {failed_conversions}")
        logger.info(f"  - Total files processed: {len(pdf_files)}")
        
        if generate_markdown and successful_conversions > 0:
            logger.info(f"  - Markdown files generated: {successful_conversions}")
        
        # Return True if at least some files were processed successfully
        return successful_conversions > 0 or len(pdf_files) == 0
        
    except Exception as e:
        logger.error(f"Unexpected error in PDF processing: {str(e)}")
        logger.debug(f"Error traceback: {traceback.format_exc()}")
        return False


def get_pdf_files_info(folder_path: str) -> List[dict]:
    """
    Get information about PDF files in a folder.
    
    Args:
        folder_path (str): Path to the folder containing PDF files
        
    Returns:
        List[dict]: List of dictionaries with file information
    """
    try:
        pdf_folder = Path(folder_path)
        if not pdf_folder.exists():
            return []
        
        pdf_files = list(pdf_folder.glob("*.pdf"))
        files_info = []
        
        for pdf_file in pdf_files:
            file_info = {
                'name': pdf_file.name,
                'path': str(pdf_file),
                'size_bytes': pdf_file.stat().st_size,
                'size_mb': round(pdf_file.stat().st_size / (1024 * 1024), 2)
            }
            files_info.append(file_info)
        
        return files_info
        
    except Exception as e:
        logger.error(f"Error getting PDF files info: {str(e)}")
        return []