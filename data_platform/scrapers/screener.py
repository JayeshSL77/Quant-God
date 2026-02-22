"""
Screener.in Scraper - Optimized for complete document extraction
Handles annual reports from any year available, plus concalls with fallbacks.
"""
import logging
import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from .base import BaseScraper

logger = logging.getLogger("ScreenerScraper")


class ScreenerScraper(BaseScraper):
    """
    Scraper for Screener.in documents (Annual Reports, Concalls).
    Extracts all available documents regardless of year.
    """
    
    BASE_URL = "https://www.screener.in/company/"
    
    def fetch_metadata(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch all document metadata for a symbol from Screener."""
        logger.info(f"[{symbol}] Fetching from Screener.in")
        url = f"{self.BASE_URL}{symbol}/"
        results = []
        
        try:
            response = self._make_request(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Annual Reports - Find ALL available reports
            ar_results = self._extract_annual_reports(soup, symbol)
            results.extend(ar_results)
            # 2. Concalls - Find ALL available concalls
            concall_results = self._extract_concalls(soup, symbol)
            results.extend(concall_results)
            logger.info(f"[{symbol}] Found {len(concall_results)} Concalls")
            
            # 3. Announcements - Final fallback
            announcement_results = self._extract_announcements(soup, symbol)
            results.extend(announcement_results)
            logger.info(f"[{symbol}] Found {len(announcement_results)} Announcements")
            
            # 4. Credit Ratings
            rating_results = self._extract_credit_ratings(soup, symbol)
            results.extend(rating_results)
            logger.info(f"[{symbol}] Found {len(rating_results)} Credit Ratings")
            
        except Exception as e:
            logger.error(f"[{symbol}] Screener fetch failed: {e}")
            
        return results

    def _extract_annual_reports(self, soup: BeautifulSoup, symbol: str) -> List[Dict[str, Any]]:
        """Extract all annual report links from the page."""
        reports = []
        
        # Try multiple selectors to find the AR section
        ar_section = None
        
        # Method 1: Look for section by class
        ar_section = soup.find('div', class_=re.compile(r'annual-reports', re.I))
        
        # Method 2: Look for header containing "Annual"
        if not ar_section:
            for header in soup.find_all(['h2', 'h3', 'h4']):
                if re.search(r'Annual\s+Report', header.get_text(), re.I):
                    # Find the parent container
                    ar_section = header.find_parent('div', class_=re.compile(r'documents|card|flex|sub-cnt'))
                    if not ar_section:
                        ar_section = header.find_parent('section')
                    if not ar_section:
                        ar_section = header.parent
                    break
        
        # Method 3: Look for any section with document links
        if not ar_section:
            for section in soup.find_all('div', class_=re.compile(r'documents|filings')):
                if 'annual' in section.get_text().lower():
                    ar_section = section
                    break
        
        if ar_section:
            # Find all links in the section
            for link in ar_section.find_all('a', href=True):
                href = link.get('href', '')
                text = " ".join(link.get_text().split())
                
                # Filter for PDF links or links with year mentions
                if not href:
                    continue
                    
                # Accept PDF links or links with year patterns
                is_pdf = '.pdf' in href.lower()
                has_year = bool(re.search(r'20\d{2}|19\d{2}', text + href))
                is_annual = bool(re.search(r'annual|report|ar\d{4}', text + href, re.I))
                
                if is_pdf or (has_year and is_annual):
                    fiscal_year = self._extract_year(text + " " + href)
                    
                    # Build full URL if relative
                    full_url = href if href.startswith('http') else f"https://www.screener.in{href}"
                    
                    # Avoid duplicates
                    if not any(r['url'] == full_url for r in reports):
                        reports.append({
                            "symbol": symbol,
                            "fiscal_year": fiscal_year,
                            "title": f"Annual Report {text}" if text else f"Annual Report {fiscal_year}",
                            "url": full_url,
                            "type": "Annual Report",
                            "source": "Screener"
                        })
        
        # Also check for direct PDF links in the page header/downloads section
        for link in soup.find_all('a', href=re.compile(r'annual.*\.pdf|ar.*\.pdf', re.I)):
            href = link.get('href', '')
            if href and not any(r['url'] == href for r in reports):
                year = self._extract_year(href)
                full_url = href if href.startswith('http') else f"https://www.screener.in{href}"
                reports.append({
                    "symbol": symbol,
                    "fiscal_year": year,
                    "title": f"Annual Report {year}",
                    "url": full_url,
                    "type": "Annual Report",
                    "source": "Screener"
                })
        
        return reports

    def _extract_concalls(self, soup: BeautifulSoup, symbol: str) -> List[Dict[str, Any]]:
        """Extract all concall links with fallback support."""
        concalls = []
        
        # Find concall section
        concall_section = None
        
        # Method 1: Look for section by class
        concall_section = soup.find('div', class_=re.compile(r'concalls?', re.I))
        
        # Method 2: Look for header containing "Concall" or "Transcript"
        if not concall_section:
            for header in soup.find_all(['h2', 'h3', 'h4']):
                if re.search(r'Concall|Transcript|Earnings\s+Call', header.get_text(), re.I):
                    concall_section = header.find_parent('div', class_=re.compile(r'documents|card|flex|sub-cnt'))
                    if not concall_section:
                        concall_section = header.find_parent('section')
                    if not concall_section:
                        concall_section = header.parent
                    break
        
        if not concall_section:
            logger.debug(f"[{symbol}] No concall section found")
            return concalls
        
        # Find all list items (each represents one concall event)
        items = concall_section.find_all('li')
        if not items:
            # Try finding div rows instead
            items = concall_section.find_all('div', class_=re.compile(r'row|item|entry'))
        
        for row in items:
            text_content = row.get_text(separator=' ').strip()
            
            # Extract date from the row
            date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+20\d{2}', text_content)
            if not date_match:
                # Try other date formats
                date_match = re.search(r'(\d{1,2}[-/]\d{1,2}[-/]20\d{2})', text_content)
            
            if not date_match:
                continue
            
            date_str = date_match.group(0)
            fiscal_year = self._extract_fy_from_date(date_str)
            quarter = self._extract_quarter_from_date(date_str)
            
            # Extract all links from this row
            links = {}
            for a in row.find_all('a', href=True):
                link_text = a.get_text().strip().lower()
                href = a.get('href', '')
                
                if not href:
                    continue
                    
                full_url = href if href.startswith('http') else f"https://www.screener.in{href}"
                
                # Categorize the link
                if any(k in link_text for k in ['transcript', 'call', 'earning']):
                    links['transcript'] = full_url
                elif 'summary' in link_text:
                    links['ai_summary'] = full_url
                elif 'ppt' in link_text or 'presentation' in link_text:
                    links['ppt'] = full_url
                elif any(k in link_text for k in ['rec', 'audio', 'video']):
                    links['recording'] = full_url
                elif '.pdf' in href.lower():
                    # Generic PDF - assume transcript if no other
                    if 'transcript' not in links:
                        links['transcript'] = full_url

            if links:
                concalls.append({
                    "symbol": symbol,
                    "fiscal_year": fiscal_year,
                    "quarter": quarter,
                    "title": f"Concall {date_str}",
                    "date_str": date_str,
                    "links": links,
                    "type": "Concall",
                    "source": "Screener"
                })
        
        return concalls

    def _extract_fy_from_date(self, date_str: str) -> str:
        """Convert 'Nov 2025' to FY '2026'."""
        try:
            # Handle "Mon YYYY" format
            match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(20\d{2})', date_str)
            if match:
                month_str, year_str = match.groups()
                year = int(year_str)
                months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                month_idx = months.index(month_str) + 1
                # If Apr-Dec, FY is year + 1
                if month_idx >= 4:
                    return str(year + 1)
                else:
                    return str(year)
            
            # Handle "DD/MM/YYYY" format
            match = re.search(r'\d{1,2}[-/](\d{1,2})[-/](20\d{2})', date_str)
            if match:
                month, year = int(match.group(1)), int(match.group(2))
                if month >= 4:
                    return str(year + 1)
                return str(year)
                
        except Exception as e:
            logger.debug(f"FY extraction failed for '{date_str}': {e}")
        
        return self._extract_year(date_str)

    def _extract_quarter_from_date(self, date_str: str) -> str:
        """Convert 'Nov 2025' to Quarter."""
        try:
            match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', date_str)
            if match:
                month_str = match.group(1)
                if month_str in ['Apr', 'May', 'Jun']: return 'Q1'
                if month_str in ['Jul', 'Aug', 'Sep']: return 'Q2'
                if month_str in ['Oct', 'Nov', 'Dec']: return 'Q3'
                if month_str in ['Jan', 'Feb', 'Mar']: return 'Q4'
            
            # Handle numeric month
            match = re.search(r'[-/](\d{1,2})[-/]', date_str)
            if match:
                month = int(match.group(1))
                if 4 <= month <= 6: return 'Q1'
                if 7 <= month <= 9: return 'Q2'
                if 10 <= month <= 12: return 'Q3'
                if 1 <= month <= 3: return 'Q4'
                
        except Exception as e:
            logger.debug(f"Quarter extraction failed for '{date_str}': {e}")
        
        return "Unknown"

    def _extract_year(self, text: str) -> str:
        """Extract fiscal year from text."""
        # Look for 4-digit year (prefer 20XX)
        match = re.search(r'20\d{2}', text)
        if match:
            return match.group(0)
        
        # Fallback to any 4-digit year
        match = re.search(r'19\d{2}', text)
        if match:
            return match.group(0)
            
        return "Unknown"

    def _extract_quarter(self, text: str) -> str:
        """Extract quarter info if present."""
        if 'Q1' in text.upper(): return 'Q1'
        if 'Q2' in text.upper(): return 'Q2'
        if 'Q3' in text.upper(): return 'Q3'
        if 'Q4' in text.upper(): return 'Q4'
        return "Unknown"
    def _extract_announcements(self, soup: BeautifulSoup, symbol: str) -> List[Dict[str, Any]]:
        """Extract all corporate announcements from the page."""
        announcements = []
        
        # Find announcements section
        announcement_section = soup.find('div', class_=re.compile(r'announcements', re.I))
        
        if not announcement_section:
            # Look for header
            for header in soup.find_all(['h2', 'h3', 'h4']):
                if 'Announcements' in header.get_text():
                    announcement_section = header.find_parent('div', class_=re.compile(r'documents|card|flex|sub-cnt'))
                    if not announcement_section:
                        announcement_section = header.parent
                    break
        
        if not announcement_section:
            return announcements
            
        # Find links
        for link in announcement_section.find_all('a', href=True):
            href = link.get('href', '')
            text = " ".join(link.get_text().split())
            
            if not href or len(text) < 5:
                continue
                
            full_url = href if href.startswith('http') else f"https://www.screener.in{href}"
            
            # Extract date if possible (often in a sibling div or near the link)
            date_str = ""
            parent = link.parent
            # Typical Screener structure for announcements has date in a sibling div
            date_el = parent.find('div', class_=re.compile(r'fill-muted')) or parent.find('span', class_=re.compile(r'fill-muted'))
            if not date_el:
                # Try grandparent if parent doesn't have it
                gp = parent.parent
                date_el = gp.find('div', class_=re.compile(r'fill-muted')) or gp.find('span', class_=re.compile(r'fill-muted'))
                
            if date_el:
                date_str = date_el.get_text().strip()
                # Clean up if it has extra text
                date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+20\d{2}', date_str)
                if date_match:
                    date_str = date_match.group(0)
            
            fiscal_year = self._extract_fy_from_date(date_str) if date_str else "Unknown"
            
            announcements.append({
                "symbol": symbol,
                "fiscal_year": fiscal_year,
                "title": text,
                "url": full_url,
                "type": "Announcement",
                "source": "Screener",
                "date_str": date_str
            })
            
        return announcements
    def _extract_credit_ratings(self, soup: BeautifulSoup, symbol: str) -> List[Dict[str, Any]]:
        """Extract all credit rating documents from the page."""
        ratings = []
        
        # Find credit rating section
        rating_section = soup.find('div', class_=re.compile(r'credit-ratings', re.I))
        
        if not rating_section:
            # Look for header
            for header in soup.find_all(['h2', 'h3', 'h4']):
                if 'Credit rating' in header.get_text():
                    rating_section = header.find_parent('div', class_=re.compile(r'documents|card|flex|sub-cnt'))
                    if not rating_section:
                        rating_section = header.parent
                    break
        
        if not rating_section:
            return ratings
            
        # Find links
        for link in rating_section.find_all('a', href=True):
            href = link.get('href', '')
            text = " ".join(link.get_text().split())
            
            if not href or len(text) < 5:
                continue
                
            full_url = href if href.startswith('http') else f"https://www.screener.in{href}"
            
            # Extract date and agency
            date_str = ""
            agency = ""
            parent = link.parent
            # Typically structure: <div><a>Rating update</a><div class="fill-muted">28 Oct 2020 from care</div></div>
            info_el = parent.find('div', class_=re.compile(r'fill-muted')) or parent.find('span', class_=re.compile(r'fill-muted'))
            if info_el:
                info_text = info_el.get_text().strip()
                # Parse "28 Oct 2020 from care"
                date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+20\d{2}', info_text)
                if date_match:
                    date_str = date_match.group(0)
                
                agency_match = re.search(r'from\s+(.+)', info_text, re.I)
                if agency_match:
                    agency = agency_match.group(1).strip()
            
            fiscal_year = self._extract_fy_from_date(date_str) if date_str else "Unknown"
            
            ratings.append({
                "symbol": symbol,
                "fiscal_year": fiscal_year,
                "title": f"Credit Rating ({agency})" if agency else text,
                "url": full_url,
                "type": "Credit Rating",
                "source": "Screener",
                "date_str": date_str
            })
            
        return ratings
