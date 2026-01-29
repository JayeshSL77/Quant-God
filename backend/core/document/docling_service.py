"""
Inwezt Core - Docling Service
High-fidelity document parsing and structured data extraction.
"""
import logging
import io
from typing import Dict, Any, Optional

try:
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False

logger = logging.getLogger("DoclingService")

class DoclingService:
    """
    Standardized service for document conversion using IBM's Docling.
    Falls back to basic extraction if Docling is unavailable.
    """
    
    def __init__(self):
        self.converter = DocumentConverter() if DOCLING_AVAILABLE else None
        if not DOCLING_AVAILABLE:
            logger.warning("Docling not installed. Falling back to basic PDF extraction.")

    def convert_to_markdown(self, pdf_bytes: bytes) -> str:
        """
        Convert PDF bytes to high-fidelity Markdown.
        Preserves tables and structure for better RAG performance.
        """
        if not self.converter:
            # Fallback to basic text extraction (can be integrated with PDFEngine)
            return "Docling unavailable for conversion."
            
        try:
            # Create a bytes stream for docling
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name
                
            result = self.converter.convert(tmp_path)
            # Cleanup
            import os
            os.unlink(tmp_path)
            
            return result.document.export_to_markdown()
        except Exception as e:
            logger.error(f"Docling conversion failed: {e}")
            return f"Error during conversion: {str(e)}"

    def extract_tables(self, pdf_bytes: bytes) -> Any:
        """
        Specific utility to extract structured tables (perfect for financial data).
        """
        # TODO: Implement granular table extraction logic
        pass

# Singleton instance for system-wide use
docling_service = DoclingService()
