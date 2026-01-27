import requests
import random
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("BaseScraper")

class BaseScraper(ABC):
    """
    Industry-standard base scraper with built-in resilience.
    """
    
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        self.timeout = 20
        
    def _get_headers(self) -> Dict[str, str]:
        """Generate random headers to avoid detection."""
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, Exception))
    )
    def _make_request(self, url: str, method: str = "GET", params: Optional[Dict] = None, data: Optional[Dict] = None) -> requests.Response:
        """Execute request with automatic retries and exponential backoff."""
        headers = self._get_headers()
        logger.info(f"Requesting: {url}")
        
        # Add random jitter between requests
        time.sleep(random.uniform(1.0, 3.0))
        
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=data,
            timeout=self.timeout
        )
        
        response.raise_for_status()
        return response

    @abstractmethod
    def fetch_metadata(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch report/concall metadata for a given symbol."""
        pass
