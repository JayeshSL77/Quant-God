"""
Inwezt Scraper Orchestrator - Optimized for EC2 overnight runs
Extracts COMPLETE PDF content (text/JSON) for RAG systems.
"""
import logging
import os
import json
from typing import List, Dict, Any, Optional
from .screener import ScreenerScraper
from api.core.document.pdf_engine import PDFEngine
from api.database.database import (
    save_annual_report, save_concall, 
    annual_report_exists, concall_exists, 
    get_stock_coverage
)

logger = logging.getLogger("ScraperOrchestrator")

# Year range for scraping (2015-2026)
MIN_YEAR = 2015
MAX_YEAR = 2026

# Coverage thresholds for automatic skipping
# If we have this many docs, we skip the stock entirely to save time/bandwidth
MIN_ANNUAL_REPORTS = 10
MIN_CONCALLS = 30


class ScraperOrchestrator:
    """
    Orchestrates the fetching, extraction, and storage of corporate documents.
    Optimized for complete PDF content extraction.
    """
    
    def __init__(self, instance_id: int = 0, concalls_only: bool = False):
        self.instance_id = instance_id
        self.concalls_only = concalls_only
        self.screener = ScreenerScraper()
        self.engine = PDFEngine()
        self.lock_file = f".scraper_{instance_id}.lock" if instance_id else ".scraper.lock"
        
        # Stats tracking
        self.stats = {
            "processed": 0,
            "ar_saved": 0,
            "concall_saved": 0,
            "errors": 0,
            "skipped": 0
        }

    def _acquire_lock(self) -> bool:
        if os.path.exists(self.lock_file):
            try:
                pid = open(self.lock_file).read().strip()
                # Check if process is still running
                if pid and os.path.exists(f"/proc/{pid}"):
                    logger.warning(f"Scraper lock exists for PID {pid}. Still running.")
                    return False
                # Stale lock, remove it
                os.remove(self.lock_file)
            except:
                pass
        with open(self.lock_file, "w") as f:
            f.write(str(os.getpid()))
        return True

    def _release_lock(self):
        if os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
            except:
                pass

    def _is_stock_fully_covered(self, symbol: str) -> bool:
        """Check if a stock already has sufficient coverage in the DB."""
        coverage = get_stock_coverage(symbol)
        return coverage['annual_reports'] >= MIN_ANNUAL_REPORTS and coverage['concalls'] >= MIN_CONCALLS

    def ingest_stock_data(self, symbol: str) -> Dict[str, int]:
        """
        Main entry point to fetch and process all documents for a stock.
        Returns stats for this stock.
        """
        stock_stats = {"ar_saved": 0, "concall_saved": 0, "errors": 0}
        
        # 1. Start ingestion (Always check for supplemental documents)
        logger.info(f"[{symbol}] Starting ingestion")
        
        # 1. Fetch metadata from Screener (primary source)
        metadata_list = []
        try:
            metadata_list = self.screener.fetch_metadata(symbol)
            if metadata_list:
                logger.info(f"[{symbol}] Found {len(metadata_list)} documents from Screener")
        except Exception as e:
            logger.error(f"[{symbol}] Screener fetch failed: {e}")
        
        if not metadata_list:
            logger.warning(f"[{symbol}] No documents found on Screener")
            return stock_stats
        
        if not metadata_list:
            logger.warning(f"[{symbol}] No documents found from any source")
            return stock_stats
                
        # 3. Filter by year range (2015-2026)
        filtered_metadata = []
        for meta in metadata_list:
            fy = meta.get('fiscal_year', 'Unknown')
            try:
                if fy == 'Unknown':
                    filtered_metadata.append(meta)
                    continue
                    
                year_int = int(fy) if str(fy).isdigit() else 0
                if MIN_YEAR <= year_int <= MAX_YEAR:
                    filtered_metadata.append(meta)
                else:
                    logger.debug(f"[{symbol}] Skipping {meta.get('title', 'doc')} - year {fy} outside {MIN_YEAR}-{MAX_YEAR}")
            except (ValueError, TypeError):
                # Keep documents with unknown or malformed year
                filtered_metadata.append(meta)

        total_docs = len(filtered_metadata)
        logger.info(f"[{symbol}] Processing {total_docs} documents ({MIN_YEAR}-{MAX_YEAR})")

        # 4. Process documents sequentially (more reliable for long runs)
        for i, meta in enumerate(filtered_metadata):
            try:
                result = self._process_single_document(symbol, meta, i+1, total_docs)
                if result == "ar_saved":
                    stock_stats["ar_saved"] += 1
                elif result == "concall_saved":
                    stock_stats["concall_saved"] += 1
            except Exception as e:
                stock_stats["errors"] += 1
                logger.error(f"[{symbol}] [{i+1}/{total_docs}] Failed: {e}")
        
        logger.info(f"[{symbol}] Completed: {stock_stats['ar_saved']} ARs, {stock_stats['concall_saved']} Concalls, {stock_stats['errors']} errors")
        return stock_stats

    def _process_single_document(self, symbol: str, meta: Dict[str, Any], index: int, total: int) -> Optional[str]:
        """Process a single document. Returns 'ar_saved', 'concall_saved', or None."""
        fy = meta.get('fiscal_year', 'Unknown')
        doc_type = meta.get('type', 'Document')
        
        if doc_type == 'Annual Report':
            if self.concalls_only:
                logger.debug(f"[{symbol}] [{index}/{total}] Skipping Annual Report (Concall-only mode)")
                return None
                
            if not annual_report_exists(symbol, fy):
                logger.info(f"[{symbol}] [{index}/{total}] Processing Annual Report FY{fy}")
                if self._process_annual_report(symbol, meta):
                    return "ar_saved"
            else:
                logger.debug(f"[{symbol}] [{index}/{total}] AR FY{fy} already exists")
                
        elif doc_type == 'Concall':
            quarter = meta.get('quarter', 'Unknown')
            logger.info(f"[{symbol}] [{index}/{total}] Processing Concall {quarter} FY{fy}")
            if self._process_concall(symbol, meta):
                return "concall_saved"
        
        elif doc_type == 'Announcement':
            # Always process announcements if they don't exist by URL
            if self._process_announcement(symbol, meta):
                return "concall_saved" 
        
        elif doc_type == 'Credit Rating':
            # Always process credit ratings if they don't exist by URL
            if self._process_credit_rating(symbol, meta):
                return "concall_saved"
        
        return None

    def _process_annual_report(self, symbol: str, meta: Dict[str, Any]) -> bool:
        """Download, extract COMPLETE content and save an annual report."""
        url = meta.get('url')
        if not url:
            logger.warning(f"[{symbol}] No URL for Annual Report")
            return False

        from api.database.database import annual_report_url_exists
        if annual_report_url_exists(url):
            logger.debug(f"[{symbol}] AR URL already exists: {url}")
            return False

        try:
            logger.info(f"[{symbol}] Downloading AR: {url}")
            response = self.screener._make_request(url)
            
            # Extract COMPLETE content from PDF
            extraction = self.engine.extract_content(response.content)
            
            if not extraction['full_text']:
                logger.warning(f"[{symbol}] Empty PDF extraction for {url}")
                return False
            
            # Build comprehensive key_metrics with ALL sections
            key_metrics = {}
            for section_name, section_content in extraction['sections'].items():
                if section_content:
                    key_metrics[section_name] = section_content
            
            # Add page count for reference
            key_metrics['_meta'] = {
                'page_count': extraction.get('page_count', 0),
                'text_length': len(extraction['full_text'])
            }

            report_data = {
                "fiscal_year": meta['fiscal_year'],
                "report_date": None,
                "title": meta.get('title', f"Annual Report {meta['fiscal_year']}"),
                "summary": extraction['full_text'],  # COMPLETE text content
                "key_metrics": key_metrics,  # All extracted sections as JSON
                "chairman_letter": extraction['sections'].get('chairman_letter', ''),
                "nuanced_summary": "",  # Can be filled by AI later
                "url": url,
                "source": meta.get('source', 'Screener')
            }
            
            save_annual_report(symbol, report_data)
            logger.info(f"[{symbol}] Saved AR FY{meta['fiscal_year']} ({extraction.get('page_count', 0)} pages, {len(extraction['full_text'])} chars)")
            return True
            
        except Exception as e:
            logger.error(f"[{symbol}] AR processing failed for {url}: {e}")
            return False

    def _process_concall(self, symbol: str, meta: Dict[str, Any]) -> bool:
        """
        Download, extract and save concall documents.
        Logic: Transcript (Priority) OR AI Summary, PLUS PPT (Supplemental).
        """
        links = meta.get('links', {})
        quarter = meta.get('quarter', 'Unknown')
        fy = meta['fiscal_year']
        saved_any = False
        
        from api.database.database import concall_url_exists, has_transcript_for_quarter
        
        # 1. Transcript (Priority 1)
        transcript_url = links.get('transcript')
        if transcript_url:
            if not concall_url_exists(transcript_url):
                logger.info(f"[{symbol}] Downloading Transcript: {transcript_url}")
                if self._process_individual_concall_link(symbol, meta, transcript_url, "transcript"):
                    saved_any = True
            else:
                saved_any = True # Already have it
                
        # 2. AI Summary (Priority 2 - Only if no Transcript exists)
        summary_url = links.get('ai_summary')
        if summary_url and not transcript_url:
            # Only save AI summary if we don't already have a full transcript for this quarter
            if not has_transcript_for_quarter(symbol, quarter, fy):
                if not concall_url_exists(summary_url):
                    logger.info(f"[{symbol}] Downloading AI Summary: {summary_url}")
                    if self._process_individual_concall_link(symbol, meta, summary_url, "ai_summary"):
                        saved_any = True
        
        # 3. PPT (Supplemental - Always capture)
        ppt_url = links.get('ppt')
        if ppt_url:
            if not concall_url_exists(ppt_url):
                logger.info(f"[{symbol}] Downloading PPT (supplemental): {ppt_url}")
                if self._process_individual_concall_link(symbol, meta, ppt_url, "ppt"):
                    saved_any = True
        
        return saved_any

    def _process_individual_concall_link(self, symbol: str, meta: Dict[str, Any], url: str, source_type: str) -> bool:
        """Helper to download and save a single link from a concall event."""
        try:
            response = self.screener._make_request(url)
            extraction = self.engine.extract_content(response.content)
            
            if not extraction['full_text']:
                logger.warning(f"[{symbol}] No content extracted for {source_type} at {url}")
                return False

            extra_sections = {k: v for k, v in extraction['sections'].items() if v}
            nuanced_json = json.dumps(extra_sections) if extra_sections else ""

            concall_data = {
                "quarter": meta.get('quarter', 'Unknown'),
                "fiscal_year": meta['fiscal_year'],
                "call_date": None,
                "title": meta.get('title', f"Concall {meta['fiscal_year']}") + (f" ({source_type})" if source_type != "transcript" else ""),
                "transcript": extraction['full_text'],
                "key_highlights": extraction['sections'].get('highlights', ''),
                "management_guidance": extraction['sections'].get('mda', ''),
                "nuanced_summary": nuanced_json,
                "url": url,
                "source": meta.get('source', 'Screener')
            }
            
            from api.database.database import save_concall
            save_concall(symbol, concall_data)
            return True
            
        except Exception as e:
            logger.error(f"[{symbol}] Concall processing failed: {e}")
            return False

    def _process_announcement(self, symbol: str, meta: Dict[str, Any]) -> bool:
        """Download and save a corporate announcement."""
        url = meta.get('url')
        if not url:
            return False
            
        from api.database.database import concall_url_exists
        if concall_url_exists(url):
            return False
            
        try:
            logger.info(f"[{symbol}] Downloading Announcement: {url}")
            response = self.screener._make_request(url)
            extraction = self.engine.extract_content(response.content)
            
            if not extraction['full_text']:
                return False
                
            concall_data = {
                "quarter": "Announcement",
                "fiscal_year": meta['fiscal_year'],
                "call_date": None,
                "title": f"Corporate Announcement: {meta['title']}",
                "transcript": extraction['full_text'],
                "key_highlights": "",
                "management_guidance": "",
                "nuanced_summary": json.dumps({"is_announcement": True}),
                "url": url,
                "source": "Screener"
            }
            
            save_concall(symbol, concall_data)
            logger.info(f"[{symbol}] Saved Announcement FY{meta['fiscal_year']} ({len(extraction['full_text'])} chars)")
            return True
            
        except Exception as e:
            logger.error(f"[{symbol}] Announcement processing failed: {e}")
            return False

    def _process_credit_rating(self, symbol: str, meta: Dict[str, Any]) -> bool:
        """Download and save a credit rating report."""
        url = meta.get('url')
        if not url:
            return False
            
        from api.database.database import concall_url_exists
        if concall_url_exists(url):
            return False
            
        try:
            logger.info(f"[{symbol}] Downloading Credit Rating: {url}")
            response = self.screener._make_request(url)
            extraction = self.engine.extract_content(response.content)
            
            if not extraction['full_text']:
                return False
                
            concall_data = {
                "quarter": "Credit Rating",
                "fiscal_year": meta['fiscal_year'],
                "call_date": None,
                "title": f"{meta['title']} ({meta.get('date_str', 'Unknown')})",
                "transcript": extraction['full_text'],
                "key_highlights": "",
                "management_guidance": "",
                "nuanced_summary": json.dumps({"is_credit_rating": True, "date": meta.get('date_str')}),
                "url": url,
                "source": "Screener"
            }
            
            save_concall(symbol, concall_data)
            logger.info(f"[{symbol}] Saved Credit Rating FY{meta['fiscal_year']} ({len(extraction['full_text'])} chars)")
            return True
            
        except Exception as e:
            logger.error(f"[{symbol}] Credit Rating processing failed: {e}")
            return False

    def get_stats(self) -> Dict[str, int]:
        """Return current processing stats."""
        return self.stats.copy()
