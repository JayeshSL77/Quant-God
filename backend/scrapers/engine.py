import pdfplumber
import logging
import io
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("PDFEngine")

class PDFEngine:
    """
    High-fidelity PDF extraction engine with section awareness.
    """
    
    # Common headers to identify specific sections in Indian Annual Reports
    SECTION_HEADERS = {
        "chairman_letter": [r"CHAIRMAN(?:’|')S?\s+MESSAGE", r"CHAIRMAN(?:’|')S?\s+STATEMENT", r"LETTER\s+FROM\s+THE\s+CHAIRMAN"],
        "mda": [r"MANAGEMENT\s+DISCUSSION\s+AND\s+ANALYSIS", r"MDA\s+REPORT"],
        "highlights": [r"FINANCIAL\s+HIGHLIGHTS", r"PERFORMANCE\s+AT\s+A\s+GLANCE"],
        "revenue_growth": [r"REVENUE\s+GROWTH", r"SEGMENTAL\s+PERFORMANCE", r"BUSINESS\s+REVIEW"],
        "risks": [r"RISK\s+MANAGEMENT", r"KEY\s+RISKS", r"CHALLENGES\s+AND\s+RISKS"],
        "outlook": [r"FUTURE\s+OUTLOOK", r"STRATEGY\s+AND\s+OUTLOOK", r"THE\s+WAY\s+FORWARD"]
    }

    def __init__(self):
        pass

    def extract_content(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Extract sections and raw text from PDF bytes.
        Processes EVERY page for complete text extraction as requested.
        """
        sections = {k: "" for k in self.SECTION_HEADERS}
        full_text_list = []
        
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                total_pages = len(pdf.pages)
                
                for i in range(total_pages):
                    page = pdf.pages[i]
                    text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                    full_text_list.append(text)
                    
                    # Section identification
                    for section_name, patterns in self.SECTION_HEADERS.items():
                        if not sections[section_name]: # Only find the first occurrence
                            for pattern in patterns:
                                if re.search(pattern, text, re.IGNORECASE):
                                    logger.info(f"Found {section_name} on page {i+1}")
                                    # Extract this page and potentially the next few
                                    sections[section_name] = self._extract_range(pdf, i, 4)
                                    break
                
                return {
                    "full_text": "\n".join(full_text_list),
                    "sections": sections,
                    "page_count": total_pages
                }
                
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return {"full_text": "", "sections": {}, "page_count": 0}

    def _extract_range(self, pdf, start_idx: int, count: int) -> str:
        """Extract a range of pages for a specific section."""
        content = []
        for i in range(start_idx, min(start_idx + count, len(pdf.pages))):
            page_text = pdf.pages[i].extract_text()
            if page_text:
                content.append(page_text)
        return "\n".join(content)

    def clean_text(self, text: str) -> str:
        """Standardize text by removing extra whitespaces and junk characters."""
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('\u0000', '')
        return text.strip()
