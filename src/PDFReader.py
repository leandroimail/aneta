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
from dotenv import load_dotenv

# Load environment variables from .conf file
load_dotenv('.conf')

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


def _get_pdf_filenames(folder_path: Path) -> set[str]:
    """
    Get set of PDF filenames in a folder.
    
    Helper function that returns only the filenames (not full paths) of all PDF files
    in a folder. Used for efficient deduplication between folders.
    
    Args:
        folder_path (Path): Path object pointing to the folder to scan
        
    Returns:
        set[str]: Set of PDF filenames (e.g., {"paper1.pdf", "paper2.pdf"})
        
    Examples:
        >>> folder = Path("/data/pdfs")
        >>> filenames = _get_pdf_filenames(folder)
        >>> print(f"Found {len(filenames)} unique PDF filenames")
    """
    try:
        if not folder_path.exists() or not folder_path.is_dir():
            logger.warning(f"Folder does not exist or is not a directory: {folder_path}")
            return set()
        
        # Get all PDF files and extract just the filenames
        pdf_files = folder_path.glob("*.pdf")
        filenames = {pdf_file.name for pdf_file in pdf_files}
        
        logger.debug(f"Found {len(filenames)} PDF filenames in {folder_path}")
        return filenames
        
    except Exception as e:
        logger.error(f"Error getting PDF filenames from {folder_path}: {str(e)}")
        return set()


def _optimize_post_processing(pre_folder: Path, post_folder: Path) -> List[Path]:
    """
    Get list of PDFs from post folder that don't exist in pre folder.
    
    This function implements deduplication optimization by filtering out PDFs
    from the post-selection folder that already exist in the pre-selection folder.
    Uses set operations for O(n) performance.
    
    Args:
        pre_folder (Path): Path to pre-selection folder
        post_folder (Path): Path to post-selection folder
        
    Returns:
        List[Path]: List of Path objects for PDFs in post folder that should be processed
        
    Examples:
        >>> pre = Path("/data/PDFs_PreSelection")
        >>> post = Path("/data/PDFs")
        >>> unique_pdfs = _optimize_post_processing(pre, post)
        >>> print(f"Processing {len(unique_pdfs)} unique PDFs from post folder")
    """
    try:
        # Get filenames from pre folder
        pre_filenames = _get_pdf_filenames(pre_folder)
        logger.info(f"Pre-selection folder has {len(pre_filenames)} PDFs")
        
        # Get all PDFs from post folder
        if not post_folder.exists() or not post_folder.is_dir():
            logger.warning(f"Post folder does not exist or is not a directory: {post_folder}")
            return []
        
        all_post_pdfs = list(post_folder.glob("*.pdf"))
        logger.info(f"Post-selection folder has {len(all_post_pdfs)} PDFs")
        
        # Filter out PDFs that exist in pre folder (using set for O(1) lookups)
        unique_post_pdfs = [
            pdf_file for pdf_file in all_post_pdfs
            if pdf_file.name not in pre_filenames
        ]
        
        # Calculate optimization statistics
        duplicates_skipped = len(all_post_pdfs) - len(unique_post_pdfs)
        if duplicates_skipped > 0:
            logger.info(
                f"Optimization: Skipping {duplicates_skipped} duplicate PDFs "
                f"already processed in pre-selection folder"
            )
        
        logger.info(f"Will process {len(unique_post_pdfs)} unique PDFs from post folder")
        return unique_post_pdfs
        
    except Exception as e:
        logger.error(f"Error optimizing post processing: {str(e)}")
        logger.debug(f"Optimization error traceback: {traceback.format_exc()}")
        # On error, return all post PDFs (no optimization)
        try:
            return list(post_folder.glob("*.pdf"))
        except Exception:
            return []


def process_pdfs(mode: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Main orchestrator function to process PDFs from configured folders.
    
    This function reads configuration from .conf file, processes PDFs from
    pre-selection and/or post-selection folders based on the mode, and optimizes
    by avoiding duplicate processing of PDFs that exist in both folders.
    
    Args:
        mode (Optional[str]): Processing mode override. Valid values:
            - "pre": Process only pre-selection folder
            - "post": Process only post-selection folder
            - "both": Process both folders with deduplication (default)
            - None: Use mode from configuration file
            
    Returns:
        Dict[str, List[Dict[str, Any]]]: Dictionary with keys "pre" and "post",
                                         each containing a list of result dictionaries
                                         from read_single_pdf()
        
    Raises:
        ValueError: If configuration is invalid or mode is not valid
        FileNotFoundError: If base data path does not exist
        
    Examples:
        >>> # Process both folders using config
        >>> results = process_pdfs()
        >>> print(f"Pre: {len(results['pre'])}, Post: {len(results['post'])}")
        
        >>> # Process only pre-selection folder
        >>> results = process_pdfs(mode="pre")
        >>> print(f"Processed {len(results['pre'])} pre-selection PDFs")
        
        >>> # Check for failures
        >>> all_results = results['pre'] + results['post']
        >>> failures = [r for r in all_results if not r['success']]
        >>> print(f"Failed: {len(failures)}")
    """
    # Load configuration from .conf file
    logger.info("Loading configuration from .conf file...")
    
    # Get base data path
    path_data = os.getenv('PATH_DATA')
    if not path_data:
        error_msg = "PATH_DATA not found in configuration (.conf file)"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate base path exists
    base_path = Path(path_data)
    if not base_path.exists():
        error_msg = f"Base data path does not exist: {path_data}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # Get PDF folder paths
    pre_folder_name = os.getenv('PDF_PRE_SELECTION_FOLDER', 'PDFs_PreSelection')
    post_folder_name = os.getenv('PDF_POST_SELECTION_FOLDER', 'PDFs')
    
    pre_folder_path = base_path / pre_folder_name
    post_folder_path = base_path / post_folder_name
    
    # Get processing configuration
    max_concurrent_str = os.getenv('PDF_MAX_CONCURRENT', '5')
    try:
        max_concurrent = int(max_concurrent_str)
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
    except ValueError as e:
        error_msg = f"Invalid PDF_MAX_CONCURRENT value '{max_concurrent_str}': {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    timeout_str = os.getenv('PDF_TIMEOUT_SECONDS', '60')
    try:
        timeout = int(timeout_str)
        if timeout < 1:
            raise ValueError("timeout must be >= 1")
    except ValueError as e:
        error_msg = f"Invalid PDF_TIMEOUT_SECONDS value '{timeout_str}': {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Determine processing mode
    if mode is None:
        mode = os.getenv('PDF_PROCESSING_MODE', 'both')
    
    # Validate mode
    valid_modes = ['pre', 'post', 'both']
    if mode not in valid_modes:
        error_msg = f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Log configuration
    logger.info(f"Configuration loaded successfully:")
    logger.info(f"  - Base path: {path_data}")
    logger.info(f"  - Pre-selection folder: {pre_folder_path}")
    logger.info(f"  - Post-selection folder: {post_folder_path}")
    logger.info(f"  - Max concurrent: {max_concurrent}")
    logger.info(f"  - Timeout: {timeout}s")
    logger.info(f"  - Processing mode: {mode}")
    
    # Initialize result structure
    results: Dict[str, List[Dict[str, Any]]] = {
        "pre": [],
        "post": []
    }
    
    # Process based on mode
    try:
        if mode in ["pre", "both"]:
            # Process pre-selection folder
            logger.info("=" * 60)
            logger.info("Processing PRE-SELECTION folder...")
            logger.info("=" * 60)
            
            if pre_folder_path.exists():
                # Use asyncio.run to execute async function in sync context
                pre_results = asyncio.run(
                    read_pdfs_batch(str(pre_folder_path), max_concurrent)
                )
                results["pre"] = pre_results
                
                # Log summary
                successful = sum(1 for r in pre_results if r["success"])
                logger.info(
                    f"Pre-selection processing complete: "
                    f"{successful}/{len(pre_results)} successful"
                )
            else:
                logger.warning(f"Pre-selection folder does not exist: {pre_folder_path}")
        
        if mode in ["post", "both"]:
            # Process post-selection folder with optimization
            logger.info("=" * 60)
            logger.info("Processing POST-SELECTION folder...")
            logger.info("=" * 60)
            
            if post_folder_path.exists():
                # Determine which PDFs to process
                if mode == "both":
                    # Apply deduplication optimization
                    logger.info("Applying deduplication optimization...")
                    post_pdfs = _optimize_post_processing(pre_folder_path, post_folder_path)
                    
                    if post_pdfs:
                        # Create temporary folder reference for batch processing
                        # We'll process the specific list of files
                        post_results = []
                        
                        # Process the filtered list using individual calls wrapped in async
                        async def process_optimized_batch():
                            semaphore = asyncio.Semaphore(max_concurrent)
                            loop = asyncio.get_event_loop()
                            
                            async def process_pdf_async(pdf_path: Path):
                                async with semaphore:
                                    with ThreadPoolExecutor(max_workers=1) as executor:
                                        result = await loop.run_in_executor(
                                            executor,
                                            read_single_pdf,
                                            str(pdf_path)
                                        )
                                    return result
                            
                            tasks = [process_pdf_async(pdf) for pdf in post_pdfs]
                            return await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Execute optimized batch
                        raw_results = asyncio.run(process_optimized_batch())
                        
                        # Process results (handle exceptions)
                        for i, result in enumerate(raw_results):
                            if isinstance(result, Exception):
                                error_result = {
                                    "markdown": "",
                                    "filename": post_pdfs[i].name,
                                    "page_count": 0,
                                    "processing_time": 0.0,
                                    "file_size_mb": 0.0,
                                    "success": False,
                                    "error": f"Unexpected exception: {str(result)}"
                                }
                                post_results.append(error_result)
                            else:
                                post_results.append(result)
                        
                        results["post"] = post_results
                        
                        # Log summary
                        successful = sum(1 for r in post_results if r["success"])
                        logger.info(
                            f"Post-selection processing complete: "
                            f"{successful}/{len(post_results)} successful"
                        )
                    else:
                        logger.info("No unique PDFs to process in post-selection folder")
                else:
                    # Process all PDFs in post folder (mode == "post")
                    post_results = asyncio.run(
                        read_pdfs_batch(str(post_folder_path), max_concurrent)
                    )
                    results["post"] = post_results
                    
                    # Log summary
                    successful = sum(1 for r in post_results if r["success"])
                    logger.info(
                        f"Post-selection processing complete: "
                        f"{successful}/{len(post_results)} successful"
                    )
            else:
                logger.warning(f"Post-selection folder does not exist: {post_folder_path}")
        
        # Final summary
        logger.info("=" * 60)
        logger.info("PROCESSING COMPLETE")
        logger.info("=" * 60)
        total_pre = len(results["pre"])
        total_post = len(results["post"])
        total_successful = (
            sum(1 for r in results["pre"] if r["success"]) +
            sum(1 for r in results["post"] if r["success"])
        )
        total_pdfs = total_pre + total_post
        
        logger.info(f"Total PDFs processed: {total_pdfs}")
        logger.info(f"  - Pre-selection: {total_pre}")
        logger.info(f"  - Post-selection: {total_post}")
        logger.info(f"  - Successful: {total_successful}/{total_pdfs}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in process_pdfs orchestration: {str(e)}")
        logger.debug(f"Orchestration error traceback: {traceback.format_exc()}")
        raise


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