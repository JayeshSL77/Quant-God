import logging
import io
import sys
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestPDFEngine")

# Add paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from api.core.document.pdf_engine import PDFEngine

def test_pdf_extraction_empty():
    engine = PDFEngine()
    result = engine.extract_content(b"")
    assert result["full_text"] == ""
    assert result["page_count"] == 0
    logger.info("Test empty PDF passed")

def test_pdf_extraction_invalid():
    engine = PDFEngine()
    result = engine.extract_content(b"not a pdf")
    assert result["full_text"] == ""
    logger.info("Test invalid PDF passed")

if __name__ == "__main__":
    test_pdf_extraction_empty()
    test_pdf_extraction_invalid()
    print("All basic PDF engine tests passed!")
