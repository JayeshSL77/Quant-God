"""
BSE India Corporate Filings Scraper
AI Native Supreme Hedge Fund — 11,000 Agent Swarm

Scrapes 11 filing types from BSE India's API:
1. Corporate Governance (Quarterly)
2. Shareholding Pattern
3. Related Party Transactions
4. Board Meetings
5. Shareholder Meetings (AGM/EGM)
6. Corporate Actions
7. Bulk & Block Deals
8. SDD-PIT Disclosures (Insider Trading)
9. Corp Announcements
10. Integrated Filing (Governance + Finance)
11. Investor Complaints

All endpoints return JSON. PDFs are downloaded and text-extracted for full content.
"""

import os
import re
import io
import json
import time
import logging
import requests
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BSEScraper")

# Try PDF extraction
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    try:
        from PyPDF2 import PdfReader
        HAS_PYPDF2 = True
    except ImportError:
        HAS_PYPDF2 = False

BASE_API = "https://api.bseindia.com/BseIndiaAPI/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
}


class BSEScraper:
    """
    Scrapes all corporate filing types from BSE India's API.
    
    Each method:
    1. Calls BSE API endpoint → gets JSON
    2. Extracts PDF/XBRL URLs from response if available
    3. Downloads and extracts full text from PDFs
    4. Returns structured data with full content
    """

    def __init__(self, rate_limit_delay: float = 2.5):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.base_delay = rate_limit_delay
        self.delay = rate_limit_delay
        self.max_delay = 30.0
        self._cookies_initialized = False
        self._consecutive_ok = 0
        self.stats = {
            "api_calls": 0,
            "pdfs_downloaded": 0,
            "errors": 0,
            "throttle_hits": 0,
        }

    def _init_cookies(self):
        """Visit BSE main page once to establish session cookies."""
        if self._cookies_initialized:
            return
        try:
            self.session.get("https://www.bseindia.com/", timeout=10)
            self._cookies_initialized = True
        except Exception:
            pass

    def _jitter(self):
        """Rate limit with jitter."""
        time.sleep(self.delay + random.uniform(0.5, 2.0))

    def _adapt_throttle(self, status_code: int):
        """Adapt delay based on response status. Increase on 429/403, decrease on success."""
        if status_code in (429, 403):
            old = self.delay
            self.delay = min(self.delay * 2, self.max_delay)
            self._consecutive_ok = 0
            self.stats["throttle_hits"] += 1
            logger.warning(f"⚠ Rate limited ({status_code})! Delay: {old:.1f}s → {self.delay:.1f}s")
            # Extra cooldown on rate limit
            time.sleep(self.delay * 3)
        elif status_code == 200:
            self._consecutive_ok += 1
            # Gradually recover after 20 consecutive successes
            if self._consecutive_ok >= 20 and self.delay > self.base_delay:
                self.delay = max(self.delay * 0.85, self.base_delay)
                self._consecutive_ok = 0
                logger.info(f"✅ Throttle recovering → {self.delay:.1f}s delay")

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout, ConnectionError))
    )
    def _api_call(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """Make a BSE API call with retries and adaptive throttling."""
        self._init_cookies()
        self._jitter()
        url = f"{BASE_API}/{endpoint}"
        resp = self.session.get(url, params=params, timeout=30)

        # Adaptive throttle BEFORE raise_for_status
        self._adapt_throttle(resp.status_code)

        resp.raise_for_status()
        self.stats["api_calls"] += 1

        # BSE sometimes returns empty string instead of JSON
        text = resp.text.strip()
        if not text or text == '""' or text == "null" or text == "{}":
            return []

        try:
            data = resp.json()
        except json.JSONDecodeError:
            if text.startswith('"') and text.endswith('"'):
                data = json.loads(text[1:-1])
            else:
                return []

        # BSE wraps all responses in {"Table": [...]}
        if isinstance(data, dict) and "Table" in data:
            return data["Table"] or []
        if isinstance(data, list):
            return data
        return []

    def extract_pdf_text(self, url: str) -> Optional[str]:
        """Download PDF and extract full text."""
        if not url or not url.startswith("http"):
            return None

        try:
            self._jitter()
            resp = self.session.get(url, timeout=60, stream=True)
            resp.raise_for_status()

            content = resp.content
            if len(content) < 100:
                return None

            self.stats["pdfs_downloaded"] += 1

            # Try PyMuPDF first (faster, better extraction)
            if HAS_PYMUPDF:
                doc = fitz.open(stream=content, filetype="pdf")
                text = ""
                for page in doc:
                    text += page.get_text() + "\n"
                doc.close()
                return text.strip() if text.strip() else None

            # Fallback to PyPDF2
            if HAS_PYPDF2:
                reader = PdfReader(io.BytesIO(content))
                text = ""
                for page in reader.pages:
                    text += (page.extract_text() or "") + "\n"
                return text.strip() if text.strip() else None

            logger.warning("No PDF library available (install PyMuPDF or PyPDF2)")
            return None

        except Exception as e:
            logger.warning(f"PDF extraction failed for {url}: {e}")
            return None

    def extract_xbrl_text(self, url: str) -> Optional[str]:
        """Download XBRL/HTML/XML file and extract full text content."""
        if not url or not url.startswith("http"):
            return None

        try:
            self._jitter()
            resp = self.session.get(url, timeout=60)
            self._adapt_throttle(resp.status_code)
            resp.raise_for_status()

            content = resp.text
            if len(content) < 50:
                return None

            self.stats["pdfs_downloaded"] += 1

            # Strip HTML/XML tags to get plain text
            # Remove script and style blocks first
            text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', content, flags=re.DOTALL | re.IGNORECASE)
            # Remove XML processing instructions
            text = re.sub(r'<\?.*?\?>', '', text)
            # Remove all HTML/XML tags
            text = re.sub(r'<[^>]+>', ' ', text)
            # Decode HTML entities
            text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ').replace('&quot;', '"')
            # Clean whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            # Remove very long runs of dashes or underscores
            text = re.sub(r'[-_=]{10,}', '', text)

            return text if len(text) > 20 else None

        except Exception as e:
            logger.warning(f"XBRL extraction failed for {url}: {e}")
            return None

    def _build_xbrl_url(self, xbrl_path: str) -> str:
        """Build full BSE URL from XBRL relative path. Skips broken/placeholder paths."""
        if not xbrl_path:
            return ""
        if xbrl_path.startswith("http"):
            return xbrl_path
        # Clean leading slashes
        xbrl_path = xbrl_path.lstrip("/")
        # Skip broken placeholder paths (e.g. "XBRL1/", "XBRL/", short paths with no filename)
        if len(xbrl_path) < 15 or "/" not in xbrl_path.rstrip("/"):
            return ""
        # Must contain an actual filename with extension
        parts = xbrl_path.rstrip("/").split("/")
        last_part = parts[-1] if parts else ""
        if "." not in last_part:
            return ""
        return f"https://www.bseindia.com/{xbrl_path}"

    # ============================================================
    # 1. Corporate Governance (Quarterly)
    # ============================================================
    def fetch_corporate_governance(self, scrip_code: str) -> List[Dict]:
        """Fetch quarterly corporate governance reports with full text extraction."""
        try:
            data = self._api_call("CGArchivewise/w", {"scripcode": scrip_code})
            if not data:
                return []

            results = []
            for item in data:
                # Build XBRL URL for full content extraction
                xbrl_url = self._build_xbrl_url(item.get("xbrlurl", ""))
                pdf_url = xbrl_url

                # Extract full text from XBRL/HTML
                content = None
                if xbrl_url:
                    content = self.extract_xbrl_text(xbrl_url)

                # Fallback to JSON metadata if extraction fails
                if not content:
                    content = json.dumps(item, indent=2, default=str)

                report = {
                    "quarter": item.get("Fld_QuarterId", ""),
                    "fiscal_year": item.get("Year", ""),
                    "report_date": item.get("Fld_EndDate", ""),
                    "pdf_url": pdf_url,
                    "raw_json": item,
                    "content": content,
                }
                results.append(report)

            logger.info(f"  CG: {len(results)} reports for scrip {scrip_code} ({self.stats['pdfs_downloaded']} texts extracted)")
            return results

        except Exception as e:
            logger.error(f"  CG error for {scrip_code}: {e}")
            self.stats["errors"] += 1
            return []

    # ============================================================
    # 2. Shareholding Pattern
    # ============================================================
    def fetch_shareholding_pattern(self, scrip_code: str) -> List[Dict]:
        """Fetch quarterly shareholding pattern data with full text extraction."""
        try:
            data = self._api_call("SHPQNewFormat/w", {"scripcode": scrip_code})
            if not data:
                return []

            results = []
            for item in data:
                # Extract full shareholding HTML
                xbrl_url = self._build_xbrl_url(item.get("xbrlurl", ""))
                content = None
                if xbrl_url:
                    content = self.extract_xbrl_text(xbrl_url)
                if not content:
                    content = json.dumps(item, indent=2, default=str)

                pattern = {
                    "quarter": item.get("qtr", ""),
                    "fiscal_year": item.get("yr", ""),
                    "promoter_holding": self._safe_float(item.get("PROMOTER_HOLDING")),
                    "public_holding": self._safe_float(item.get("PUBLIC_HOLDING")),
                    "institutional_holding": self._safe_float(item.get("Institutional_HOLDING")),
                    "dii_holding": self._safe_float(item.get("DII_HOLDING")),
                    "fii_holding": self._safe_float(item.get("FII_HOLDING")),
                    "raw_json": item,
                    "content": content,
                }
                results.append(pattern)

            logger.info(f"  SHP: {len(results)} quarters for scrip {scrip_code} ({self.stats['pdfs_downloaded']} texts extracted)")
            return results

        except Exception as e:
            logger.error(f"  SHP error for {scrip_code}: {e}")
            self.stats["errors"] += 1
            return []

    # ============================================================
    # 3. Related Party Transactions
    # ============================================================
    def fetch_related_party_transactions(self, scrip_code: str) -> List[Dict]:
        """Fetch related party transaction reports with full text extraction."""
        try:
            data = self._api_call("XbrlRelatedPartyTrans/w", {"scripcode": scrip_code})
            if not data:
                return []

            results = []
            for item in data:
                # Extract full RPT XBRL content
                xbrl_url = self._build_xbrl_url(item.get("xbrlurl", ""))
                content = None
                if xbrl_url:
                    content = self.extract_xbrl_text(xbrl_url)
                if not content:
                    content = json.dumps(item, indent=2, default=str)

                rpt = {
                    "fiscal_year": item.get("yr", ""),
                    "half_year": item.get("qtr", ""),
                    "report_date": item.get("filing_date_time", ""),
                    "raw_json": item,
                    "content": content,
                }
                results.append(rpt)

            logger.info(f"  RPT: {len(results)} filings for scrip {scrip_code} ({self.stats['pdfs_downloaded']} texts extracted)")
            return results

        except Exception as e:
            logger.error(f"  RPT error for {scrip_code}: {e}")
            self.stats["errors"] += 1
            return []

    # ============================================================
    # 4. Board Meetings
    # ============================================================
    def fetch_board_meetings(self, scrip_code: str) -> List[Dict]:
        """Fetch board meeting details."""
        try:
            data = self._api_call("BoardMeeting/w", {"scripcode": scrip_code})
            if not data:
                return []

            results = []
            for item in data:
                meeting = {
                    "meeting_type": "board",
                    "meeting_date": item.get("meeting_date", "") or item.get("tm", ""),
                    "purpose": item.get("Purpose_name", "") or item.get("PURPOSE", ""),
                    "agenda": item.get("Agenda", ""),
                    "raw_json": item,
                    "content": json.dumps(item, indent=2, default=str),
                }
                results.append(meeting)

            logger.info(f"  Board Meetings: {len(results)} for scrip {scrip_code}")
            return results

        except Exception as e:
            logger.error(f"  Board Meeting error for {scrip_code}: {e}")
            self.stats["errors"] += 1
            return []

    # ============================================================
    # 5. Shareholder Meetings (AGM/EGM)
    # ============================================================
    def fetch_shareholder_meetings(self, scrip_code: str) -> List[Dict]:
        """Fetch shareholder meeting details (AGM/EGM)."""
        try:
            data = self._api_call("ShareHolderMeeting/w", {"scripcode": scrip_code})
            if not data:
                return []

            results = []
            for item in data:
                purpose = item.get("PURPOSE_NAME", "") or item.get("Purpose", "")
                mtype = "agm" if "A.G.M" in purpose.upper() or "AGM" in purpose.upper() else "egm"
                meeting = {
                    "meeting_type": mtype,
                    "meeting_date": item.get("MEETING_DATE", "") or item.get("DT_TM", ""),
                    "purpose": purpose,
                    "agenda": item.get("Agenda", ""),
                    "raw_json": item,
                    "content": json.dumps(item, indent=2, default=str),
                }
                results.append(meeting)

            logger.info(f"  SH Meetings: {len(results)} for scrip {scrip_code}")
            return results

        except Exception as e:
            logger.error(f"  SH Meeting error for {scrip_code}: {e}")
            self.stats["errors"] += 1
            return []

    # ============================================================
    # 6. Corporate Actions
    # ============================================================
    def fetch_corporate_actions(self, scrip_code: str) -> List[Dict]:
        """Fetch corporate actions (dividends, splits, bonuses, etc.)."""
        try:
            data = self._api_call("CorporateAction/w", {"scripcode": scrip_code})
            if not data:
                return []

            results = []
            for item in data:
                action = {
                    "action_type": item.get("purpose_name", "") or item.get("Purpose", ""),
                    "ex_date": item.get("BCRD_from", ""),
                    "record_date": item.get("Record_Dt", ""),
                    "bc_start_date": item.get("BC_STRT_DT", ""),
                    "bc_end_date": item.get("BC_END_DT", ""),
                    "details": str(item.get("Amount", "")) if item.get("Amount") else json.dumps(item, indent=2, default=str),
                    "raw_json": item,
                }
                results.append(action)

            logger.info(f"  Corp Actions: {len(results)} for scrip {scrip_code}")
            return results

        except Exception as e:
            logger.error(f"  Corp Actions error for {scrip_code}: {e}")
            self.stats["errors"] += 1
            return []

    # ============================================================
    # 7. Bulk & Block Deals
    # ============================================================
    def fetch_bulk_block_deals(self, scrip_code: str) -> List[Dict]:
        """Fetch bulk and block deal data."""
        results = []
        # Type 1 = Bulk, Type 2 = Block
        for deal_type, deal_name in [(1, "bulk_deal"), (2, "block_deal")]:
            try:
                data = self._api_call("BulkblockDeal/w", {
                    "scripcode": scrip_code,
                    "fromdt": "",
                    "todt": "",
                    "type": deal_type,
                })
                if not data:
                    continue

                for item in data:
                    deal = {
                        "filing_type": deal_name,
                        "trade_date": item.get("DEAL_DATE", "") or item.get("DT_TM", ""),
                        "client_name": item.get("CLIENT_NAME", "") or item.get("ClientName", ""),
                        "buy_sell": item.get("TRANSACTION_TYPE", "") or item.get("BUYSELL", ""),
                        "quantity": self._safe_int(item.get("QUANTITY", 0)),
                        "price": self._safe_float(item.get("PRICE", 0)),
                        "raw_json": item,
                        "content": json.dumps(item, indent=2, default=str),
                    }
                    results.append(deal)

            except Exception as e:
                logger.error(f"  {deal_name} error for {scrip_code}: {e}")
                self.stats["errors"] += 1

        logger.info(f"  Deals: {len(results)} bulk/block for scrip {scrip_code}")
        return results

    # ============================================================
    # 8. SDD-PIT Disclosures (Insider Trading)
    # ============================================================
    def fetch_sdd_pit(self, scrip_code: str) -> List[Dict]:
        """Fetch insider trading disclosures (SAST/PIT)."""
        try:
            data = self._api_call("sddpit/w", {
                "scripcode": scrip_code,
                "fromdt": "",
                "todt": "",
            })
            if not data:
                return []

            results = []
            for item in data:
                disclosure = {
                    "filing_type": "insider_trade",
                    "trade_date": item.get("DT_TM", ""),
                    "client_name": item.get("Name_Of_Person", "") or item.get("Acq_Name", ""),
                    "buy_sell": item.get("Category", ""),
                    "quantity": self._safe_int(item.get("Buy_No_OF_Shares") or item.get("Sell_No_OF_Shares", 0)),
                    "price": self._safe_float(item.get("Buy_Avg_CAP") or item.get("Sell_Avg_CAP", 0)),
                    "raw_json": item,
                    "content": json.dumps(item, indent=2, default=str),
                }
                results.append(disclosure)

            logger.info(f"  SDD-PIT: {len(results)} disclosures for scrip {scrip_code}")
            return results

        except Exception as e:
            logger.error(f"  SDD-PIT error for {scrip_code}: {e}")
            self.stats["errors"] += 1
            return []

    # ============================================================
    # 9. Corp Announcements
    # ============================================================
    def fetch_corp_announcements(self, scrip_code: str, max_pages: int = 5) -> List[Dict]:
        """Fetch corporate announcements with full PDF extraction."""
        try:
            # AnnGetData also wraps in Table, but _api_call handles it
            data = self._api_call("AnnGetData/w", {
                "scripcode": scrip_code,
                "annession_id": "",
                "strCat": "-1",
                "strPrevDate": "",
                "strScrip": "",
                "strSearch": "",
                "strToDate": "",
                "strType": "",
            })
            if not data:
                return []

            results = []
            for item in data[:100]:  # Cap at 100 announcements per stock
                ann = {
                    "announcement_type": item.get("CATEGORYNAME", ""),
                    "announcement_date": item.get("DT_TM", ""),
                    "subject": item.get("SLONGNAME", "") or item.get("HEADLINE", ""),
                    "pdf_url": item.get("ATTACHMENTNAME", ""),
                    "raw_json": item,
                    "content": None,
                }

                # Extract PDF text for top announcements
                if ann["pdf_url"] and len(results) < 30:
                    if not ann["pdf_url"].startswith("http"):
                        ann["pdf_url"] = f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{ann['pdf_url']}"
                    ann["content"] = self.extract_pdf_text(ann["pdf_url"])

                results.append(ann)

            logger.info(f"  Announcements: {len(results)} for scrip {scrip_code}")
            return results

        except Exception as e:
            logger.error(f"  Announcements error for {scrip_code}: {e}")
            self.stats["errors"] += 1
            return []

    # ============================================================
    # 10. Integrated Filing (Governance)
    # ============================================================
    def fetch_integrated_filing(self, scrip_code: str) -> List[Dict]:
        """Fetch integrated filings (governance + finance) with full text extraction."""
        try:
            data = self._api_call("Integratedfiledata/w", {"scripcode": scrip_code})
            if not data:
                return []

            results = []
            for item in data:
                # Extract full integrated filing content
                xbrl_url = self._build_xbrl_url(item.get("xbrlurl", ""))
                content = None
                if xbrl_url:
                    content = self.extract_xbrl_text(xbrl_url)
                if not content:
                    content = json.dumps(item, indent=2, default=str)

                filing = {
                    "filing_type": item.get("category", "") or item.get("Category", ""),
                    "quarter": item.get("qtr", ""),
                    "fiscal_year": item.get("yr", ""),
                    "filing_date": item.get("filing_date_time", ""),
                    "raw_json": item,
                    "content": content,
                }
                results.append(filing)

            logger.info(f"  Integrated: {len(results)} filings for scrip {scrip_code} ({self.stats['pdfs_downloaded']} texts extracted)")
            return results

        except Exception as e:
            logger.error(f"  Integrated filing error for {scrip_code}: {e}")
            self.stats["errors"] += 1
            return []

    # ============================================================
    # 11. Investor Complaints
    # ============================================================
    def fetch_investor_complaints(self, scrip_code: str) -> List[Dict]:
        """Fetch statement of investor complaints with full text extraction."""
        try:
            data = self._api_call("XbrlInvestorComplaint/w", {"scripcode": scrip_code})
            if not data:
                return []

            results = []
            for item in data:
                # Extract full complaints HTML content
                xbrl_url = self._build_xbrl_url(item.get("xbrlurl", ""))
                content = None
                if xbrl_url:
                    content = self.extract_xbrl_text(xbrl_url)
                if not content:
                    content = json.dumps(item, indent=2, default=str)

                complaint = {
                    "quarter": item.get("qtr", "") or item.get("Quarter", ""),
                    "fiscal_year": item.get("yr", "") or item.get("Year", ""),
                    "raw_json": item,
                    "content": content,
                }
                results.append(complaint)

            logger.info(f"  Investor Complaints: {len(results)} for scrip {scrip_code} ({self.stats['pdfs_downloaded']} texts extracted)")
            return results

        except Exception as e:
            logger.error(f"  Investor Complaints error for {scrip_code}: {e}")
            self.stats["errors"] += 1
            return []

    # ============================================================
    # Combined: Fetch all filings for a stock
    # ============================================================
    def fetch_all_filings(self, scrip_code: str) -> Dict[str, List]:
        """Fetch ALL filing types for a single stock."""
        return {
            "corporate_governance": self.fetch_corporate_governance(scrip_code),
            "shareholding_pattern": self.fetch_shareholding_pattern(scrip_code),
            "related_party_transactions": self.fetch_related_party_transactions(scrip_code),
            "board_meetings": self.fetch_board_meetings(scrip_code),
            "shareholder_meetings": self.fetch_shareholder_meetings(scrip_code),
            "corporate_actions": self.fetch_corporate_actions(scrip_code),
            "bulk_block_deals": self.fetch_bulk_block_deals(scrip_code),
            "sdd_pit": self.fetch_sdd_pit(scrip_code),
            "corp_announcements": self.fetch_corp_announcements(scrip_code),
            "integrated_filing": self.fetch_integrated_filing(scrip_code),
            "investor_complaints": self.fetch_investor_complaints(scrip_code),
        }

    # ============================================================
    # Helpers
    # ============================================================
    def _safe_float(self, val) -> Optional[float]:
        try:
            if val is None or val == "" or val == "-":
                return None
            return float(str(val).replace(",", "").replace("%", ""))
        except (ValueError, TypeError):
            return None

    def _safe_int(self, val) -> Optional[int]:
        try:
            if val is None or val == "" or val == "-":
                return None
            return int(float(str(val).replace(",", "")))
        except (ValueError, TypeError):
            return None

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse BSE date formats to YYYY-MM-DD."""
        if not date_str:
            return None
        for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        # Try extracting from datetime strings like "2024-01-15T00:00:00"
        match = re.search(r'(\d{4}-\d{2}-\d{2})', date_str)
        if match:
            return match.group(1)
        return None


def test_single_stock():
    """Test with DLF (scrip code 532868)."""
    scraper = BSEScraper(rate_limit_delay=1.0)
    print("Testing BSE Scraper with DLF (532868)...")
    print("=" * 60)

    results = scraper.fetch_all_filings("532868")

    for filing_type, data in results.items():
        count = len(data)
        has_content = sum(1 for d in data if d.get("content"))
        print(f"  {filing_type}: {count} records ({has_content} with full text)")

    print(f"\nStats: {scraper.stats}")


if __name__ == "__main__":
    test_single_stock()
