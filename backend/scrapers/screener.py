import logging
import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from .base import BaseScraper

logger = logging.getLogger("ScreenerScraper")

class ScreenerScraper(BaseScraper):
    """
    Scraper for Screener.in documents (Annual Reports, Concalls).
    """
    
    BASE_URL = "https://www.screener.in/company/"
    
    def fetch_metadata(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch all document metadata for a symbol from Screener."""
        logger.info(f"Fetching Screener documents for {symbol}")
        url = f"{self.BASE_URL}{symbol}/"
        results = []
        
        try:
            response = self._make_request(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Annual Reports
            ar_section = soup.find('div', class_=re.compile(r'annual-reports'))
            if not ar_section:
                h3 = soup.find(lambda tag: tag.name in ['h3', 'h4'] and re.search(r'Annual reports', tag.get_text(), re.I))
                if h3:
                    # In Screener, the h3 is often in a header div, and the list is in a sibling or the same parent
                    # We go up until we find a container that likely holds the documents
                    ar_section = h3.find_parent('div', class_=re.compile(r'documents|card|flex-column'))
                    if not ar_section: ar_section = h3.find_parent('div')

            if ar_section:
                # If this section only contains the header, look for the next sibling that might be the list
                if not ar_section.find_all('a') and ar_section.next_sibling:
                    ar_section = ar_section.find_parent('div', class_=re.compile(r'documents|card|flex-column')) or ar_section
                
                for link in ar_section.find_all('a'):
                    href = link.get('href')
                    text = " ".join(link.get_text().split())
                    if href and ('Annual Report' in text or 'Financial Year' in text or '.pdf' in href.lower()):
                        fy = self._extract_year(text)
                        results.append({
                            "symbol": symbol,
                            "fiscal_year": fy,
                            "title": f"Annual Report {text}",
                            "url": href if href.startswith('http') else f"https://www.screener.in{href}",
                            "type": "Annual Report",
                            "source": "Screener"
                        })
            
            # 2. Concalls
            concall_section = soup.find('div', class_=re.compile(r'concalls'))
            if not concall_section:
                h3 = soup.find(lambda tag: tag.name in ['h3', 'h4'] and re.search(r'Concalls?|Transcripts?', tag.get_text(), re.I))
                if h3:
                    concall_section = h3.find_parent('div', class_=re.compile(r'documents|card|flex-column'))
                    if not concall_section: concall_section = h3.find_parent('div')

            if concall_section:
                # Find all list items - concalls are typically in an 'ul' list
                items = concall_section.find_all('li')
                for row in items:
                    text_content = row.text.strip()
                    date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+20\d{2}', text_content)
                    if not date_match:
                        continue
                    
                    date_str = date_match.group(0)
                    fiscal_year = self._extract_fy_from_date(date_str)
                    quarter = self._extract_quarter_from_date(date_str)
                    
                    links = {}
                    for a in row.find_all(['a', 'button']):
                        link_text = a.text.strip().lower()
                        href = a.get('href') or a.get('data-href')
                        if not href: continue
                        full_url = href if href.startswith('http') else f"https://www.screener.in{href}"
                        
                        if 'transcript' in link_text:
                            links['transcript'] = full_url
                        elif 'summary' in link_text:
                            links['ai_summary'] = full_url
                        elif 'ppt' in link_text:
                            links['ppt'] = full_url
                        elif 'rec' in link_text:
                            links['rec'] = full_url

                    if links:
                        results.append({
                            "symbol": symbol,
                            "fiscal_year": fiscal_year,
                            "quarter": quarter,
                            "title": f"Concall {date_str}",
                            "date_str": date_str,
                            "links": links,
                            "type": "Concall",
                            "source": "Screener"
                        })
                logger.info(f"Discovered {len([r for r in results if r['type'] == 'Concall'])} concall groups")
                        
        except Exception as e:
            logger.error(f"Screener fetch failed for {symbol}: {e}")
            
        return results

    def _extract_fy_from_date(self, date_str: str) -> str:
        """Convert 'Nov 2025' to FY '2026'."""
        try:
            month_str, year_str = date_str.split()
            year = int(year_str)
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            month_idx = months.index(month_str) + 1
            # If Apr-Dec, FY is year + 1
            if month_idx >= 4:
                return str(year + 1)
            else:
                return str(year)
        except:
            return self._extract_year(date_str)

    def _extract_quarter_from_date(self, date_str: str) -> str:
        """Convert 'Nov 2025' to Quarter."""
        try:
            month_str = date_str.split()[0]
            if month_str in ['Apr', 'May', 'Jun']: return 'Q1'
            if month_str in ['Jul', 'Aug', 'Sep']: return 'Q2'
            if month_str in ['Oct', 'Nov', 'Dec']: return 'Q3'
            if month_str in ['Jan', 'Feb', 'Mar']: return 'Q4'
        except:
            pass
        return "Unknown"

    def _extract_year(self, text: str) -> str:
        """Extract fiscal year (e.g., 'Mar 2023' -> '2023')"""
        match = re.search(r'20\d{2}', text)
        return match.group(0) if match else "Unknown"

    def _extract_quarter(self, text: str) -> str:
        """Extract quarter info if present."""
        if 'Q1' in text: return 'Q1'
        if 'Q2' in text: return 'Q2'
        if 'Q3' in text: return 'Q3'
        if 'Q4' in text: return 'Q4'
        return "Unknown"
