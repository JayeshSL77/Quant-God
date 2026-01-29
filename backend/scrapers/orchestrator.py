import logging
import os
from typing import List, Dict, Any
from .bse import BSEScraper
from .screener import ScreenerScraper
from backend.core.document.pdf_engine import PDFEngine
from backend.database.database import save_annual_report, save_concall, annual_report_exists, concall_exists, get_stock_coverage

logger = logging.getLogger("ScraperOrchestrator")

# Coverage thresholds for skipping
MIN_ANNUAL_REPORTS = 5  # At least 5 ARs to be considered "full"
MIN_CONCALLS = 15       # At least 15 Concalls to be considered "full"

class ScraperOrchestrator:
    """
    Orchestrates the fetching, extraction, and storage of corporate documents.
    """
    
    def __init__(self):
        self.bse = BSEScraper()
        self.screener = ScreenerScraper()
        self.engine = PDFEngine()
        self.lock_file = ".scraper.lock"

    def _acquire_lock(self):
        if os.path.exists(self.lock_file):
            pid = open(self.lock_file).read().strip()
            logger.warning(f"Scraper lock exists for PID {pid}. Check if it's still running.")
            return False
        with open(self.lock_file, "w") as f:
            f.write(str(os.getpid()))
        return True

    def _release_lock(self):
        if os.path.exists(self.lock_file):
            os.remove(self.lock_file)

    def _is_stock_fully_covered(self, symbol: str) -> bool:
        """Check if a stock already has sufficient coverage in the DB."""
        coverage = get_stock_coverage(symbol)
        return coverage['annual_reports'] >= MIN_ANNUAL_REPORTS and coverage['concalls'] >= MIN_CONCALLS

    def ingest_stock_data(self, symbol: str):
        """Main entry point to fetch and process all documents for a stock."""
        # Early exit if stock is already fully covered
        if self._is_stock_fully_covered(symbol):
            logger.info(f"Skipping {symbol} - already fully covered (AR >= {MIN_ANNUAL_REPORTS}, Concalls >= {MIN_CONCALLS})")
            return
        
        logger.info(f"Starting ingestion process for {symbol}")
        
        # 1. Fetch metadata from both sources
        metadata_list = self.screener.fetch_metadata(symbol)
        if not metadata_list:
             metadata_list = self.bse.fetch_metadata(symbol)
             
        # Filter metadata by year first to reduce parallel workload
        filtered_metadata = []
        for meta in metadata_list:
            fy = meta.get('fiscal_year', 'Unknown')
            try:
                year_int = int(fy) if str(fy).isdigit() else 0
                if 2020 <= year_int <= 2026:
                    filtered_metadata.append(meta)
                else:
                    logger.debug(f"Skipping {meta['title']} - outside target range")
            except ValueError:
                filtered_metadata.append(meta) # Keep if unsure

        total_docs = len(filtered_metadata)
        logger.info(f"Filtered to {total_docs} documents for {symbol} (2020-2026)")

        # 2. Process documents in parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i, meta in enumerate(filtered_metadata):
                futures.append(executor.submit(self._process_single_document, symbol, meta, i+1, total_docs))
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Worker thread failed: {e}")

    def _process_single_document(self, symbol: str, meta: Dict[str, Any], index: int, total: int):
        """Helper to process a single document with progress logging."""
        try:
            fy = meta.get('fiscal_year', 'Unknown')
            type_str = meta.get('type', 'Document')
            logger.info(f"[{index}/{total}] Starting {type_str} for {symbol} FY{fy}")
            
            if meta['type'] == 'Annual Report':
                if not annual_report_exists(symbol, fy):
                    self._process_annual_report(symbol, meta)
                else:
                    logger.info(f"[{index}/{total}] Annual Report {fy} already exists")
            elif meta['type'] == 'Concall':
                quarter = meta.get('quarter', 'Unknown')
                if not concall_exists(symbol, quarter, fy):
                    self._process_concall(symbol, meta)
                else:
                    logger.info(f"[{index}/{total}] Concall {fy} {quarter} already exists")
        except Exception as e:
            logger.error(f"[{index}/{total}] Failed to process {meta.get('title')}: {e}")

    def _process_annual_report(self, symbol: str, meta: Dict[str, Any]):
        """Download, extract and save an annual report."""
        url = meta.get('url')
        if not url:
            return

        from backend.database.database import annual_report_url_exists
        if annual_report_url_exists(url):
            logger.info(f"Annual Report URL already exists in DB: {url}")
            return

        logger.info(f"Processing Annual Report: {url}")
        response = self.screener._make_request(meta['url'])
        extraction = self.engine.extract_content(response.content)
        
        # Store new sections in key_metrics to avoid schema changes
        key_metrics = {
            "highlights": extraction['sections'].get('highlights', ''),
            "revenue_growth": extraction['sections'].get('revenue_growth', ''),
            "risks": extraction['sections'].get('risks', ''),
            "outlook": extraction['sections'].get('outlook', '')
        }

        report_data = {
            "fiscal_year": meta['fiscal_year'],
            "report_date": None,
            "title": meta['title'],
            "summary": extraction['full_text'], 
            "key_metrics": key_metrics, 
            "chairman_letter": extraction['sections'].get('chairman_letter', ''),
            "nuanced_summary": "",
            "url": meta['url'],
            "source": meta['source']
        }
        
        save_annual_report(symbol, report_data)
        logger.info(f"Successfully saved annual report for {symbol} {meta['fiscal_year']}")

    def _process_concall(self, symbol: str, meta: Dict[str, Any]):
        """Download, extract and save a concall transcript with fallback support."""
        links = meta.get('links', {})
        transcript_url = links.get('transcript')
        ppt_url = links.get('ppt')
        summary_url = links.get('ai_summary')
        
        target_url = transcript_url or summary_url or ppt_url
        if not target_url:
            logger.warning(f"No valid links found for concall {meta['title']}")
            return

        from backend.database.database import concall_url_exists
        if concall_url_exists(target_url):
            logger.info(f"Concall URL already exists in DB: {target_url}")
            return

        content = ""
        highlights = ""
        mda = ""
        extra_sections = {}
        
        if transcript_url:
            logger.info(f"Processing Concall Transcript: {transcript_url}")
            resp_head = self.screener._make_request(transcript_url, method="HEAD")
            size = resp_head.headers.get('Content-Length', 'unknown')
            logger.info(f"Downloading {size} bytes from {transcript_url}")
            
            response = self.screener._make_request(transcript_url)
            extraction = self.engine.extract_content(response.content)
            content = extraction['full_text']
            highlights = extraction['sections'].get('highlights', '')
            mda = extraction['sections'].get('mda', '')
            # Capture other sections in metadata/JSON if needed in future
            extra_sections = {k: v for k, v in extraction['sections'].items() if k not in ['highlights', 'mda', 'chairman_letter']}
        else:
            combined_text = []
            if summary_url:
                resp = self.screener._make_request(summary_url)
                ext = self.engine.extract_content(resp.content)
                combined_text.append("--- AI SUMMARY CONTENT ---\n" + ext['full_text'])
                highlights = ext['sections'].get('highlights', '')
            
            if ppt_url:
                resp = self.screener._make_request(ppt_url)
                ext = self.engine.extract_content(resp.content)
                combined_text.append("--- PPT CONTENT ---\n" + ext['full_text'])
                if not highlights: highlights = ext['sections'].get('highlights', '')
                mda = ext['sections'].get('mda', '')

            content = "\n\n".join(combined_text)

        concall_data = {
            "quarter": meta.get('quarter', 'Unknown'),
            "fiscal_year": meta['fiscal_year'],
            "call_date": None,
            "title": meta['title'] + (" (Fallback)" if not transcript_url else ""),
            "transcript": content,
            "key_highlights": highlights,
            "management_guidance": mda,
            "nuanced_summary": str(extra_sections) if extra_sections else "", # Use existing col for extra data
            "url": target_url,
            "source": meta['source']
        }
        
        save_concall(symbol, concall_data)
        logger.info(f"Successfully saved concall for {symbol} FY{meta['fiscal_year']} {meta.get('quarter')}")
