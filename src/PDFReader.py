"""
PDF Reader module using Docling library for parsing PDF documents.

This module provides functionality to read PDF documents from configurable folders
and optionally generate Markdown files from the parsed content.
"""

import os
import logging
from pathlib import Path
from typing import Optional, List
import traceback
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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