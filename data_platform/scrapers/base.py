"""
Base Scraper - Industry-standard with built-in resilience
Optimized for long-running EC2 overnight jobs.
"""
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
    Features:
    - Automatic retries with exponential backoff
    - Random user agents to avoid detection
    - Request jittering to be respectful
    - Configurable timeouts
    """
    
    def __init__(self):
        try:
            self.ua = UserAgent()
        except Exception:
            self.ua = None
            logger.warning("UserAgent initialization failed, using default")
        
        self.session = requests.Session()
        self.timeout = 30  # Increased timeout for large PDFs
        self.max_retries = 3
        
    def _get_headers(self) -> Dict[str, str]:
        """Generate random headers to avoid detection."""
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        if self.ua:
            try:
                user_agent = self.ua.random
            except:
                pass
                
        return {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=3, max=30),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout, ConnectionError))
    )
    def _make_request(
        self, 
        url: str, 
        method: str = "GET", 
        params: Optional[Dict] = None, 
        data: Optional[Dict] = None,
        stream: bool = False
    ) -> requests.Response:
        """
        Execute request with automatic retries and exponential backoff.
        
        Args:
            url: Target URL
            method: HTTP method (GET, POST, HEAD)
            params: Query parameters
            data: POST data
            stream: Whether to stream the response (for large files)
        
        Returns:
            requests.Response object
        """
        headers = self._get_headers()
        
        # Add random jitter between requests (1.5 - 4 seconds)
        jitter = random.uniform(1.5, 4.0)
        time.sleep(jitter)
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                timeout=self.timeout,
                stream=stream,
                allow_redirects=True
            )
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Rate limited - wait longer
                logger.warning(f"Rate limited on {url}, waiting 60s...")
                time.sleep(60)
                raise  # Will be retried
            elif e.response.status_code == 403:
                logger.error(f"Access forbidden for {url}")
                raise
            elif e.response.status_code == 404:
                logger.warning(f"Not found: {url}")
                raise
            else:
                logger.error(f"HTTP error {e.response.status_code} for {url}")
                raise
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout for {url}")
            raise
            
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error for {url}")
            raise

    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()

    @abstractmethod
    def fetch_metadata(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch report/concall metadata for a given symbol."""
        pass
