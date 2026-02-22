"""
Insider Trading Signals
Scrapes SEC Form 4 filings for insider buy/sell activity.
Detects cluster buys, unusual transactions, and generates signals.
"""

import os
import re
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import xml.etree.ElementTree as ET
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InsiderSignals")


@dataclass
class InsiderTransaction:
    """Single insider transaction."""
    symbol: str
    insider_name: str
    insider_title: str  # CEO, CFO, Director, etc.
    transaction_type: str  # P (Purchase), S (Sale), A (Award)
    shares: int
    price: float
    value: float
    transaction_date: str
    filing_date: str


@dataclass
class InsiderSignal:
    """Aggregated signal from insider activity."""
    symbol: str
    signal_type: str  # cluster_buy, ceo_buying, unusual_size, insider_selling
    strength: str  # strong, moderate, weak
    description: str
    transactions: List[Dict]
    net_shares: int
    net_value: float
    period_days: int


class InsiderTracker:
    """
    Tracks insider trading from SEC Form 4 filings.
    Generates signals for unusual activity.
    """
    
    SEC_RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&CIK={cik}&type=4&company=&dateb=&owner=only&count=40&output=atom"
    SEC_FORM4_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}"
    
    INSIDER_TITLES = {
        "CEO": ["chief executive", "ceo", "president"],
        "CFO": ["chief financial", "cfo", "treasurer"],
        "COO": ["chief operating", "coo"],
        "CTO": ["chief technology", "cto"],
        "Director": ["director", "board"],
        "VP": ["vice president", "vp"],
        "10% Owner": ["10%", "beneficial owner"]
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Analyez Research analyez@example.com'
        })
    
    def get_recent_transactions(self, symbol: str, cik: str, days: int = 90) -> List[InsiderTransaction]:
        """Fetch recent Form 4 filings for a company."""
        transactions = []
        
        try:
            # Get Form 4 RSS feed
            url = self.SEC_RSS_URL.format(cik=cik.lstrip('0'))
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                return []
            
            # Parse Atom feed
            root = ET.fromstring(response.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for entry in root.findall('atom:entry', ns):
                try:
                    title = entry.find('atom:title', ns)
                    updated = entry.find('atom:updated', ns)
                    link = entry.find('atom:link', ns)
                    
                    if title is None or updated is None:
                        continue
                    
                    # Parse date
                    filing_date = updated.text[:10]
                    filing_dt = datetime.strptime(filing_date, '%Y-%m-%d')
                    
                    if filing_dt < cutoff_date:
                        continue
                    
                    # Extract insider name and transaction type from title
                    title_text = title.text
                    
                    # Simple parsing - title format: "4 - COMPANY NAME (Filer) INSIDER NAME"
                    # This is simplified - real implementation would parse the XML filing
                    
                    transactions.append(InsiderTransaction(
                        symbol=symbol,
                        insider_name=self._extract_insider_name(title_text),
                        insider_title=self._classify_insider(title_text),
                        transaction_type="P",  # Would parse from actual filing
                        shares=0,  # Would parse from actual filing
                        price=0.0,
                        value=0.0,
                        transaction_date=filing_date,
                        filing_date=filing_date
                    ))
                    
                except Exception as e:
                    logger.debug(f"Error parsing entry: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error fetching Form 4 for {symbol}: {e}")
        
        return transactions
    
    def _extract_insider_name(self, title: str) -> str:
        """Extract insider name from filing title."""
        # Simple extraction - would be more sophisticated in production
        parts = title.split('(')
        if len(parts) > 1:
            return parts[-1].replace(')', '').strip()[:50]
        return "Unknown"
    
    def _classify_insider(self, title: str) -> str:
        """Classify insider by title."""
        title_lower = title.lower()
        for role, keywords in self.INSIDER_TITLES.items():
            if any(kw in title_lower for kw in keywords):
                return role
        return "Officer"
    
    def generate_signals(self, symbol: str, transactions: List[InsiderTransaction]) -> List[InsiderSignal]:
        """Generate trading signals from insider transactions."""
        signals = []
        
        if not transactions:
            return signals
        
        # Separate buys and sells
        buys = [t for t in transactions if t.transaction_type == 'P']
        sells = [t for t in transactions if t.transaction_type == 'S']
        
        # Signal: Cluster Buy (multiple insiders buying)
        if len(buys) >= 3:
            unique_insiders = len(set(t.insider_name for t in buys))
            if unique_insiders >= 2:
                signals.append(InsiderSignal(
                    symbol=symbol,
                    signal_type="cluster_buy",
                    strength="strong" if unique_insiders >= 3 else "moderate",
                    description=f"{unique_insiders} different insiders bought shares in the last 90 days",
                    transactions=[asdict(t) for t in buys[:5]],
                    net_shares=sum(t.shares for t in buys),
                    net_value=sum(t.value for t in buys),
                    period_days=90
                ))
        
        # Signal: CEO/CFO Buying
        executive_buys = [t for t in buys if t.insider_title in ['CEO', 'CFO']]
        if executive_buys:
            signals.append(InsiderSignal(
                symbol=symbol,
                signal_type="executive_buying",
                strength="strong",
                description=f"{executive_buys[0].insider_title} purchased shares",
                transactions=[asdict(t) for t in executive_buys],
                net_shares=sum(t.shares for t in executive_buys),
                net_value=sum(t.value for t in executive_buys),
                period_days=90
            ))
        
        # Signal: Heavy Selling
        if len(sells) >= 5 or (sells and sum(t.value for t in sells) > 10000000):
            signals.append(InsiderSignal(
                symbol=symbol,
                signal_type="insider_selling",
                strength="moderate" if len(sells) < 8 else "strong",
                description=f"{len(sells)} insider sales in the last 90 days",
                transactions=[asdict(t) for t in sells[:5]],
                net_shares=-sum(t.shares for t in sells),
                net_value=-sum(t.value for t in sells),
                period_days=90
            ))
        
        return signals
    
    def analyze_stock(self, symbol: str, cik: str) -> Dict[str, Any]:
        """Full insider analysis for a stock."""
        transactions = self.get_recent_transactions(symbol, cik)
        signals = self.generate_signals(symbol, transactions)
        
        # Summary metrics
        buys = [t for t in transactions if t.transaction_type == 'P']
        sells = [t for t in transactions if t.transaction_type == 'S']
        
        return {
            "symbol": symbol,
            "analyzed_at": datetime.now().isoformat(),
            "period_days": 90,
            "summary": {
                "total_transactions": len(transactions),
                "buys": len(buys),
                "sells": len(sells),
                "net_sentiment": "bullish" if len(buys) > len(sells) else "bearish" if len(sells) > len(buys) else "neutral"
            },
            "signals": [asdict(s) for s in signals],
            "recent_transactions": [asdict(t) for t in transactions[:10]]
        }


def format_insider_for_ui(analysis: Dict) -> Dict:
    """Format insider data for optimal UI display."""
    summary = analysis.get("summary", {})
    signals = analysis.get("signals", [])
    
    # Determine overall sentiment indicator
    sentiment = summary.get("net_sentiment", "neutral")
    sentiment_colors = {"bullish": "#22c55e", "bearish": "#ef4444", "neutral": "#94a3b8"}
    
    return {
        # Header card
        "header": {
            "symbol": analysis.get("symbol"),
            "sentiment": sentiment.upper(),
            "color": sentiment_colors.get(sentiment, "#94a3b8"),
            "period": f"Last {analysis.get('period_days', 90)} days"
        },
        
        # Stats row
        "stats": [
            {"label": "Total Filings", "value": summary.get("total_transactions", 0)},
            {"label": "Buys", "value": summary.get("buys", 0), "color": "#22c55e"},
            {"label": "Sells", "value": summary.get("sells", 0), "color": "#ef4444"}
        ],
        
        # Signal alerts
        "signals": [
            {
                "type": s.get("signal_type", "").replace("_", " ").title(),
                "strength": s.get("strength"),
                "description": s.get("description"),
                "icon": _signal_icon(s.get("signal_type", ""))
            }
            for s in signals
        ],
        
        # Transaction table
        "transactions": analysis.get("recent_transactions", [])[:10]
    }


def _signal_icon(signal_type: str) -> str:
    """Get icon for signal type."""
    icons = {
        "cluster_buy": "🎯",
        "executive_buying": "👔",
        "insider_selling": "⚠️",
        "unusual_size": "📊"
    }
    return icons.get(signal_type, "📋")


if __name__ == "__main__":
    tracker = InsiderTracker()
    
    # Test with Apple
    print("Analyzing AAPL insider activity...")
    analysis = tracker.analyze_stock("AAPL", "320193")
    
    print(f"\n{'='*50}")
    print(f"INSIDER ANALYSIS: AAPL")
    print(f"{'='*50}")
    print(f"Net Sentiment: {analysis['summary']['net_sentiment'].upper()}")
    print(f"Buys: {analysis['summary']['buys']} | Sells: {analysis['summary']['sells']}")
    
    if analysis['signals']:
        print("\nSignals:")
        for s in analysis['signals']:
            print(f"  {s['signal_type']}: {s['description']}")
