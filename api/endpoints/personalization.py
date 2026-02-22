"""
Inwezt AI - User Personalization Engine
Self-learning system that builds user profiles from interaction history
to deliver uniquely personalized responses.
"""
import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from collections import Counter
import re

from api.endpoints.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class UserProfile:
    """
    Learned profile of a user based on their interaction history.
    This profile evolves with each interaction.
    """
    user_id: str
    
    # Investment Style - learned from query patterns
    risk_appetite: str = "moderate"  # conservative, moderate, aggressive
    investment_horizon: str = "medium"  # short, medium, long
    preferred_sectors: List[str] = field(default_factory=list)
    favorite_stocks: List[str] = field(default_factory=list)
    avoided_stocks: List[str] = field(default_factory=list)
    
    # Communication Preferences - learned from interactions
    preferred_language: str = "english"  # english, hinglish, hindi
    verbosity_preference: str = "concise"  # concise, detailed, elaborate
    technical_level: str = "intermediate"  # beginner, intermediate, expert
    prefers_charts: bool = False
    prefers_numbers: bool = True
    
    # Behavioral Patterns - automatically tracked
    query_count: int = 0
    avg_session_length: int = 0
    most_active_hours: List[int] = field(default_factory=list)
    common_query_types: List[str] = field(default_factory=list)
    
    # Personal Context - extracted from conversations
    portfolio_mentions: List[str] = field(default_factory=list)  # stocks they own
    price_targets_mentioned: Dict[str, float] = field(default_factory=dict)
    concerns: List[str] = field(default_factory=list)  # tax, volatility, etc.
    
    # Timestamps
    first_seen: str = ""
    last_seen: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "UserProfile":
        return cls(**data)


class UserPersonalizationEngine:
    """
    Self-learning engine that:
    1. Extracts insights from each user interaction
    2. Builds and updates user profiles over time
    3. Generates personalized context for LLM prompts
    """
    
    # Storage directory for user profiles (file-based for simplicity)
    PROFILES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "user_profiles")
    
    def __init__(self):
        os.makedirs(self.PROFILES_DIR, exist_ok=True)
        self._cache: Dict[str, UserProfile] = {}
        
        # Keywords for learning patterns
        self.RISK_KEYWORDS = {
            "aggressive": ["yolo", "double", "multibagger", "high growth", "alpha", "momentum", "swing trade"],
            "conservative": ["safe", "stable", "dividend", "blue chip", "low risk", "fd", "government"],
            "moderate": ["balanced", "diversified", "index", "etf", "sip"]
        }
        
        self.HORIZON_KEYWORDS = {
            "short": ["intraday", "short term", "quick", "this week", "tomorrow", "swing"],
            "long": ["long term", "10 year", "retire", "wealth", "compound", "hold forever"],
            "medium": ["1 year", "few months", "medium term"]
        }
        
        self.SECTOR_PATTERNS = {
            "banking": ["bank", "hdfc", "icici", "kotak", "axis", "sbi", "nifty bank"],
            "it": ["tcs", "infosys", "wipro", "tech mahindra", "hcl", "it sector", "software"],
            "pharma": ["pharma", "sun pharma", "dr reddy", "cipla", "biocon", "healthcare"],
            "auto": ["auto", "tata motors", "maruti", "m&m", "bajaj", "eicher", "ev"],
            "fmcg": ["fmcg", "hindustan unilever", "itc", "nestle", "dabur", "marico"],
            "energy": ["reliance", "oil", "ongc", "power", "adani power", "tata power"],
            "metals": ["tata steel", "hindalco", "vedanta", "coal india", "nmdc"]
        }
        
        self.CONCERN_KEYWORDS = ["risk", "loss", "volatile", "crash", "fall"]
        
    def _get_profile_path(self, user_id: str) -> str:
        """Get file path for user profile."""
        # Hash user_id for privacy
        hashed = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        return os.path.join(self.PROFILES_DIR, f"{hashed}.json")
    
    def get_or_create_profile(self, user_id: str) -> UserProfile:
        """Load existing profile or create new one."""
        if not user_id:
            return UserProfile(user_id="anonymous")
        
        # Check cache first
        if user_id in self._cache:
            return self._cache[user_id]
        
        profile_path = self._get_profile_path(user_id)
        
        if os.path.exists(profile_path):
            try:
                with open(profile_path, 'r') as f:
                    data = json.load(f)
                    profile = UserProfile.from_dict(data)
                    self._cache[user_id] = profile
                    logger.info(f"Loaded profile for user {user_id[:8]}... (queries: {profile.query_count})")
                    return profile
            except Exception as e:
                logger.error(f"Error loading profile: {e}")
        
        # Create new profile
        profile = UserProfile(
            user_id=user_id,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat()
        )
        self._cache[user_id] = profile
        return profile
    
    def save_profile(self, profile: UserProfile):
        """Persist profile to storage."""
        if not profile.user_id or profile.user_id == "anonymous":
            return
        
        profile.updated_at = datetime.now().isoformat()
        profile_path = self._get_profile_path(profile.user_id)
        
        try:
            with open(profile_path, 'w') as f:
                json.dump(profile.to_dict(), f, indent=2)
            logger.info(f"Saved profile for user {profile.user_id[:8]}...")
        except Exception as e:
            logger.error(f"Error saving profile: {e}")
    
    def learn_from_interaction(
        self, 
        user_id: str, 
        query: str, 
        response: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> UserProfile:
        """
        Analyze interaction and update user profile.
        This is the core learning function.
        """
        profile = self.get_or_create_profile(user_id)
        query_lower = query.lower()
        
        # Update basic stats
        profile.query_count += 1
        profile.last_seen = datetime.now().isoformat()
        current_hour = datetime.now().hour
        if current_hour not in profile.most_active_hours:
            profile.most_active_hours.append(current_hour)
            profile.most_active_hours = profile.most_active_hours[-10:]  # Keep last 10
        
        # Learn language preference
        if self._detect_hinglish(query):
            profile.preferred_language = "hinglish"
        elif self._detect_hindi(query):
            profile.preferred_language = "hindi"
        
        # Learn risk appetite
        for risk_level, keywords in self.RISK_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                profile.risk_appetite = risk_level
                break
        
        # Learn investment horizon
        for horizon, keywords in self.HORIZON_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                profile.investment_horizon = horizon
                break
        
        # Learn sector preferences
        for sector, patterns in self.SECTOR_PATTERNS.items():
            if any(p in query_lower for p in patterns):
                if sector not in profile.preferred_sectors:
                    profile.preferred_sectors.append(sector)
                    profile.preferred_sectors = profile.preferred_sectors[-5:]  # Top 5
        
        # Extract stock mentions and add to favorites
        stock_mentions = self._extract_stock_tickers(query)
        for stock in stock_mentions:
            if stock not in profile.favorite_stocks:
                profile.favorite_stocks.append(stock)
                profile.favorite_stocks = profile.favorite_stocks[-10:]  # Top 10
        
        # Learn concerns
        for concern in self.CONCERN_KEYWORDS:
            if concern in query_lower and concern not in profile.concerns:
                profile.concerns.append(concern)
                profile.concerns = profile.concerns[-5:]
        
        # Learn verbosity preference from query style
        if len(query) > 100:
            profile.verbosity_preference = "detailed"
        elif "quick" in query_lower or "briefly" in query_lower:
            profile.verbosity_preference = "concise"
        
        # Learn technical level
        technical_terms = ["pe ratio", "eps", "roce", "ebitda", "dcf", "intrinsic value", "beta", "sharpe"]
        if any(term in query_lower for term in technical_terms):
            profile.technical_level = "expert"
        
        # Learn chart preference
        if "chart" in query_lower or "graph" in query_lower:
            profile.prefers_charts = True
        
        # Detect portfolio mentions (stocks they own)
        portfolio_patterns = ["i have", "i own", "my portfolio", "i bought", "i hold"]
        if any(p in query_lower for p in portfolio_patterns):
            for stock in stock_mentions:
                if stock not in profile.portfolio_mentions:
                    profile.portfolio_mentions.append(stock)
        
        # Save updated profile
        self.save_profile(profile)
        
        return profile
    
    def _detect_hinglish(self, text: str) -> bool:
        """Detect if text is Hinglish."""
        hinglish_markers = ["kya", "hai", "nahi", "acha", "kitna", "kaisa", "kaise", "bhai", "yaar"]
        return any(marker in text.lower() for marker in hinglish_markers)
    
    def _detect_hindi(self, text: str) -> bool:
        """Detect if text contains Hindi script."""
        return bool(re.search(r'[\u0900-\u097F]', text))
    
    def _extract_stock_tickers(self, text: str) -> List[str]:
        """Extract potential stock tickers from text."""
        # Common Indian stock patterns
        known_stocks = [
            "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "WIPRO", "SBIN",
            "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "ITC", "HINDUNILVR",
            "BAJFINANCE", "ASIANPAINT", "MARUTI", "TITAN", "SUNPHARMA", "ULTRACEMCO",
            "ONGC", "NTPC", "POWERGRID", "COALINDIA", "TATAMOTORS", "TATASTEEL",
            "HDFC BANK", "ICICI BANK", "SBI", "AXIS BANK", "KOTAK", "BAJAJ FINANCE",
            "ASIAN PAINTS", "SUN PHARMA", "TATA MOTORS", "TATA STEEL", "COAL INDIA"
        ]
        
        text_upper = text.upper()
        found = []
        for stock in known_stocks:
            if stock in text_upper:
                # Normalize to standard ticker
                normalized = stock.replace(" ", "").upper()
                if normalized not in found:
                    found.append(normalized)
        
        return found
    
    def generate_personalized_context(self, profile: UserProfile) -> str:
        """
        Generate a context string to inject into LLM prompts
        for personalized responses.
        """
        if profile.query_count < 2:
            return ""  # Not enough data yet
        
        context_parts = []
        
        # User persona summary
        context_parts.append("## User Persona (Learned from past interactions)")
        
        # Investment style
        if profile.risk_appetite != "moderate":
            context_parts.append(f"- Risk Appetite: {profile.risk_appetite.upper()}")
        if profile.investment_horizon != "medium":
            context_parts.append(f"- Investment Horizon: {profile.investment_horizon.upper()}")
        
        # Sector preferences
        if profile.preferred_sectors:
            context_parts.append(f"- Preferred Sectors: {', '.join(profile.preferred_sectors)}")
        
        # Favorite stocks
        if profile.favorite_stocks:
            context_parts.append(f"- Frequently Asked Stocks: {', '.join(profile.favorite_stocks[:5])}")
        
        # Portfolio context
        if profile.portfolio_mentions:
            context_parts.append(f"- User's Portfolio Includes: {', '.join(profile.portfolio_mentions)}")
        
        # Known concerns
        if profile.concerns:
            context_parts.append(f"- Key Concerns: {', '.join(profile.concerns)}")
        
        # Communication style
        style_notes = []
        if profile.preferred_language == "hinglish":
            style_notes.append("Respond in Hinglish (mix of Hindi and English)")
        if profile.verbosity_preference == "detailed":
            style_notes.append("User prefers detailed explanations")
        elif profile.verbosity_preference == "concise":
            style_notes.append("User prefers brief, to-the-point answers")
        if profile.technical_level == "expert":
            style_notes.append("User understands technical financial terms")
        elif profile.technical_level == "beginner":
            style_notes.append("Explain concepts simply, avoid jargon")
        
        if style_notes:
            context_parts.append(f"- Communication Style: {'; '.join(style_notes)}")
        
        # Engagement level
        if profile.query_count > 50:
            context_parts.append(f"- Engagement: Power user ({profile.query_count} interactions)")
        elif profile.query_count > 10:
            context_parts.append(f"- Engagement: Regular user ({profile.query_count} interactions)")
        
        if len(context_parts) <= 1:
            return ""
        
        return "\n".join(context_parts)
    
    def get_personalization_hints(self, profile: UserProfile) -> Dict[str, Any]:
        """
        Get structured personalization hints for the response generator.
        """
        return {
            "language": profile.preferred_language,
            "verbosity": profile.verbosity_preference,
            "technical_level": profile.technical_level,
            "risk_appetite": profile.risk_appetite,
            "horizon": profile.investment_horizon,
            "favorite_stocks": profile.favorite_stocks[:5],
            "portfolio": profile.portfolio_mentions,
            "concerns": profile.concerns,
            "is_returning_user": profile.query_count > 1,
            "is_power_user": profile.query_count > 50
        }


# Global instance
personalization_engine = UserPersonalizationEngine()
