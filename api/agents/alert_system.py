"""
Real-Time Alert System
Monitors news sentiment and triggers alerts based on thresholds.
Works for both India and US markets.
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AlertSystem")


@dataclass
class Alert:
    """A triggered alert."""
    id: str
    symbol: str
    market: str
    alert_type: str  # sentiment_drop, sentiment_surge, price_move, news_volume
    severity: str  # low, medium, high, critical
    title: str
    description: str
    data: Dict[str, Any]
    triggered_at: str


class AlertSystem:
    """
    Real-time alert system for portfolio monitoring.
    
    Alert types:
    - sentiment_drop: Sentiment drops below threshold
    - sentiment_surge: Sentiment spikes above threshold
    - news_volume: Unusual news volume
    - earnings_surprise: Earnings beat/miss
    """
    
    # Alert thresholds
    THRESHOLDS = {
        "sentiment_drop": -0.3,
        "sentiment_surge": 0.5,
        "news_spike_multiplier": 3,  # 3x normal volume
    }
    
    def __init__(self):
        self.alerts: List[Alert] = []
        self.watchlist: Dict[str, Dict] = {}  # symbol -> {market, last_sentiment, last_check}
    
    def add_to_watchlist(self, symbol: str, market: str = "india"):
        """Add a symbol to the watchlist."""
        self.watchlist[symbol.upper()] = {
            "market": market,
            "last_sentiment": None,
            "last_check": None,
            "baseline_news_count": 5
        }
        logger.info(f"Added {symbol} to watchlist ({market})")
    
    def remove_from_watchlist(self, symbol: str):
        """Remove a symbol from the watchlist."""
        if symbol.upper() in self.watchlist:
            del self.watchlist[symbol.upper()]
            logger.info(f"Removed {symbol} from watchlist")
    
    def check_sentiment_alert(self, symbol: str, current_sentiment: float) -> Optional[Alert]:
        """Check if sentiment triggers an alert."""
        if symbol not in self.watchlist:
            return None
        
        info = self.watchlist[symbol]
        last_sentiment = info.get('last_sentiment')
        
        # Update tracking
        info['last_sentiment'] = current_sentiment
        info['last_check'] = datetime.now().isoformat()
        
        # Check for significant drop
        if current_sentiment <= self.THRESHOLDS["sentiment_drop"]:
            return Alert(
                id=f"{symbol}_{int(time.time())}",
                symbol=symbol,
                market=info['market'],
                alert_type="sentiment_drop",
                severity="high" if current_sentiment <= -0.5 else "medium",
                title=f"⚠️ Negative Sentiment Alert: {symbol}",
                description=f"Sentiment dropped to {current_sentiment:.2f} (threshold: {self.THRESHOLDS['sentiment_drop']})",
                data={"sentiment_score": current_sentiment, "previous": last_sentiment},
                triggered_at=datetime.now().isoformat()
            )
        
        # Check for positive surge
        if current_sentiment >= self.THRESHOLDS["sentiment_surge"]:
            return Alert(
                id=f"{symbol}_{int(time.time())}",
                symbol=symbol,
                market=info['market'],
                alert_type="sentiment_surge",
                severity="low",
                title=f"📈 Positive Sentiment Surge: {symbol}",
                description=f"Sentiment surged to {current_sentiment:.2f} (threshold: {self.THRESHOLDS['sentiment_surge']})",
                data={"sentiment_score": current_sentiment, "previous": last_sentiment},
                triggered_at=datetime.now().isoformat()
            )
        
        return None
    
    def check_news_volume_alert(self, symbol: str, news_count: int) -> Optional[Alert]:
        """Check if news volume is unusually high."""
        if symbol not in self.watchlist:
            return None
        
        info = self.watchlist[symbol]
        baseline = info.get('baseline_news_count', 5)
        threshold = baseline * self.THRESHOLDS["news_spike_multiplier"]
        
        if news_count >= threshold:
            return Alert(
                id=f"{symbol}_news_{int(time.time())}",
                symbol=symbol,
                market=info['market'],
                alert_type="news_volume",
                severity="medium",
                title=f"📰 High News Volume: {symbol}",
                description=f"Unusual news activity ({news_count} articles vs normal {baseline})",
                data={"news_count": news_count, "baseline": baseline},
                triggered_at=datetime.now().isoformat()
            )
        
        return None
    
    def process_alerts(self, alerts: List[Alert]):
        """Process triggered alerts (store, notify, etc.)."""
        for alert in alerts:
            self.alerts.append(alert)
            logger.info(f"ALERT: {alert.title}")
            
            # TODO: Send push notification
            # TODO: Store in database
            # TODO: Send email/webhook
    
    def get_recent_alerts(self, limit: int = 20) -> List[Dict]:
        """Get recent alerts."""
        return [asdict(a) for a in self.alerts[-limit:]]
    
    def to_json(self, alerts: List[Alert]) -> str:
        """Convert alerts to JSON."""
        return json.dumps([asdict(a) for a in alerts], indent=2)


# Flask API for alerts
def create_alerts_blueprint():
    """Create Flask blueprint for alert API."""
    from flask import Blueprint, request, jsonify
    
    alerts_bp = Blueprint('alerts', __name__)
    alert_system = AlertSystem()
    
    @alerts_bp.route('/api/alerts/watchlist', methods=['POST'])
    def add_watchlist():
        data = request.get_json()
        symbol = data.get('symbol')
        market = data.get('market', 'india')
        
        if not symbol:
            return jsonify({"error": "Missing symbol"}), 400
        
        alert_system.add_to_watchlist(symbol, market)
        return jsonify({"success": True, "symbol": symbol, "market": market})
    
    @alerts_bp.route('/api/alerts/watchlist', methods=['GET'])
    def get_watchlist():
        return jsonify({"watchlist": list(alert_system.watchlist.keys())})
    
    @alerts_bp.route('/api/alerts/recent', methods=['GET'])
    def get_alerts():
        limit = request.args.get('limit', 20, type=int)
        return jsonify({"alerts": alert_system.get_recent_alerts(limit)})
    
    return alerts_bp


if __name__ == "__main__":
    # Test alert system
    system = AlertSystem()
    
    # Add to watchlist
    system.add_to_watchlist("RELIANCE", "india")
    system.add_to_watchlist("AAPL", "us")
    
    # Simulate sentiment check
    alert = system.check_sentiment_alert("RELIANCE", -0.4)
    if alert:
        print(f"\n{alert.title}")
        print(alert.description)
    
    alert = system.check_sentiment_alert("AAPL", 0.6)
    if alert:
        print(f"\n{alert.title}")
        print(alert.description)
