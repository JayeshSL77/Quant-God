"""
Sector Exposure Analyzer
Visual breakdown of sector/industry exposure with concentration warnings.
"""

import os
import logging
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
import json
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SectorExposure")

# Database URLs
INDIA_DB = os.getenv("DATABASE_URL", 
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")
US_DB = os.getenv("US_DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/usmarkets")


@dataclass
class SectorData:
    """Sector exposure data."""
    name: str
    weight: float
    stocks: List[str]
    color: str


@dataclass
class ExposureAnalysis:
    """Complete exposure analysis for UI."""
    sectors: List[SectorData]
    industries: List[Dict]
    concentration_score: int  # 0-100 (100 = perfectly diversified)
    top_holdings: List[Dict]
    warnings: List[str]
    hhi_index: float  # Herfindahl-Hirschman Index


class ExposureAnalyzer:
    """
    Analyzes sector and industry exposure.
    Returns data optimized for treemap and heatmap visualizations.
    """
    
    # Sector colors for visualization
    SECTOR_COLORS = {
        "Technology": "#3b82f6",
        "Information Technology": "#3b82f6",
        "Healthcare": "#10b981",
        "Health Care": "#10b981",
        "Financials": "#8b5cf6",
        "Consumer Discretionary": "#f59e0b",
        "Consumer Staples": "#84cc16",
        "Industrials": "#6366f1",
        "Energy": "#ef4444",
        "Materials": "#14b8a6",
        "Utilities": "#a855f7",
        "Real Estate": "#ec4899",
        "Communication Services": "#06b6d4",
        "Other": "#94a3b8"
    }
    
    def __init__(self, market: str = "india"):
        self.market = market
        self.db_url = INDIA_DB if market == "india" else US_DB
    
    def get_sector_mapping(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get sector/industry for each symbol."""
        if self.market == "us":
            return self._get_us_sectors(symbols)
        else:
            return self._get_india_sectors(symbols)
    
    def _get_us_sectors(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get US sector data from database."""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT symbol, company_name, sector, industry
                FROM company_metadata
                WHERE symbol = ANY(%s)
            """, (symbols,))
            
            mapping = {}
            for row in cur.fetchall():
                mapping[row['symbol']] = {
                    "company_name": row['company_name'],
                    "sector": row['sector'] or "Other",
                    "industry": row['industry'] or "Other"
                }
            
            cur.close()
            conn.close()
            return mapping
            
        except Exception as e:
            logger.error(f"Error getting US sectors: {e}")
            return {}
    
    def _get_india_sectors(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get India sector data (may need external API or manual mapping)."""
        # For now, return placeholder - can be enhanced with actual data
        # Could use Yahoo Finance, BSE/NSE data, or manual mapping
        try:
            import yfinance as yf
            
            mapping = {}
            for symbol in symbols:
                try:
                    # Try with .NS suffix for NSE
                    ticker = yf.Ticker(f"{symbol}.NS")
                    info = ticker.info
                    mapping[symbol] = {
                        "company_name": info.get("longName", symbol),
                        "sector": info.get("sector", "Other"),
                        "industry": info.get("industry", "Other")
                    }
                except:
                    mapping[symbol] = {
                        "company_name": symbol,
                        "sector": "Other",
                        "industry": "Other"
                    }
            
            return mapping
            
        except Exception as e:
            logger.error(f"Error getting India sectors: {e}")
            return {}
    
    def analyze(self, stocks: List[Dict]) -> ExposureAnalysis:
        """
        Analyze sector/industry exposure.
        
        Args:
            stocks: List of {symbol, weight, company_name?}
        """
        symbols = [s["symbol"] for s in stocks]
        sector_mapping = self.get_sector_mapping(symbols)
        
        # Aggregate by sector
        sector_weights = {}
        industry_weights = {}
        
        for stock in stocks:
            symbol = stock["symbol"]
            weight = stock["weight"]
            
            info = sector_mapping.get(symbol, {"sector": "Other", "industry": "Other"})
            sector = info.get("sector", "Other")
            industry = info.get("industry", "Other")
            
            if sector not in sector_weights:
                sector_weights[sector] = {"weight": 0, "stocks": []}
            sector_weights[sector]["weight"] += weight
            sector_weights[sector]["stocks"].append(symbol)
            
            if industry not in industry_weights:
                industry_weights[industry] = {"weight": 0, "stocks": []}
            industry_weights[industry]["weight"] += weight
            industry_weights[industry]["stocks"].append(symbol)
        
        # Create sector data
        sectors = []
        for name, data in sorted(sector_weights.items(), key=lambda x: -x[1]["weight"]):
            sectors.append(SectorData(
                name=name,
                weight=round(data["weight"], 2),
                stocks=data["stocks"],
                color=self.SECTOR_COLORS.get(name, "#94a3b8")
            ))
        
        # Create industry data (top 10)
        industries = []
        for name, data in sorted(industry_weights.items(), key=lambda x: -x[1]["weight"])[:10]:
            industries.append({
                "name": name,
                "weight": round(data["weight"], 2),
                "count": len(data["stocks"])
            })
        
        # Top holdings
        top_holdings = sorted(stocks, key=lambda x: -x["weight"])[:10]
        top_holdings = [{
            "symbol": s["symbol"],
            "weight": round(s["weight"], 2),
            "company_name": sector_mapping.get(s["symbol"], {}).get("company_name", s["symbol"])
        } for s in top_holdings]
        
        # Concentration score (inverse of HHI)
        weights = [s["weight"] for s in stocks]
        hhi = sum((w/100) ** 2 for w in weights) * 10000  # HHI scale
        
        # Score: 100 = perfectly diversified (HHI at minimum), 0 = single stock
        min_hhi = 10000 / len(stocks) if stocks else 10000
        concentration_score = int(100 - ((hhi - min_hhi) / (10000 - min_hhi) * 100))
        concentration_score = max(0, min(100, concentration_score))
        
        # Warnings
        warnings = []
        for sector in sectors:
            if sector.weight > 30:
                warnings.append(f"High concentration in {sector.name} ({sector.weight}%)")
        
        for holding in top_holdings[:3]:
            if holding["weight"] > 15:
                warnings.append(f"Single stock risk: {holding['symbol']} is {holding['weight']}%")
        
        if len(sectors) < 4:
            warnings.append("Limited sector diversification - consider adding more sectors")
        
        return ExposureAnalysis(
            sectors=sectors,
            industries=industries,
            concentration_score=concentration_score,
            top_holdings=top_holdings,
            warnings=warnings,
            hhi_index=round(hhi, 0)
        )


def format_exposure_for_ui(analysis: ExposureAnalysis) -> Dict:
    """Format exposure analysis for optimal UI display."""
    return {
        # Treemap data
        "treemap": {
            "data": [
                {
                    "name": s.name,
                    "value": s.weight,
                    "color": s.color,
                    "stocks": s.stocks
                }
                for s in analysis.sectors
            ]
        },
        
        # Sector pie/donut chart
        "sector_chart": {
            "type": "donut",
            "data": [
                {"name": s.name, "value": s.weight, "color": s.color}
                for s in analysis.sectors
            ]
        },
        
        # Concentration gauge
        "concentration": {
            "score": analysis.concentration_score,
            "label": _concentration_label(analysis.concentration_score),
            "hhi": analysis.hhi_index,
            "color": _concentration_color(analysis.concentration_score)
        },
        
        # Industry breakdown
        "industries": analysis.industries,
        
        # Top holdings table
        "top_holdings": analysis.top_holdings,
        
        # Warnings
        "warnings": [
            {"type": "warning", "message": w}
            for w in analysis.warnings
        ]
    }


def _concentration_label(score: int) -> str:
    """Get label for concentration score."""
    if score >= 75:
        return "Well Diversified"
    if score >= 50:
        return "Moderately Diversified"
    if score >= 25:
        return "Concentrated"
    return "Highly Concentrated"


def _concentration_color(score: int) -> str:
    """Get color for concentration score."""
    if score >= 75:
        return "#22c55e"  # Green
    if score >= 50:
        return "#eab308"  # Yellow
    if score >= 25:
        return "#f97316"  # Orange
    return "#ef4444"  # Red


if __name__ == "__main__":
    # Test with sample data
    analyzer = ExposureAnalyzer(market="us")
    
    test_stocks = [
        {"symbol": "AAPL", "weight": 20},
        {"symbol": "MSFT", "weight": 18},
        {"symbol": "GOOGL", "weight": 15},
        {"symbol": "AMZN", "weight": 12},
        {"symbol": "NVDA", "weight": 10},
        {"symbol": "JPM", "weight": 8},
        {"symbol": "JNJ", "weight": 7},
        {"symbol": "PG", "weight": 5},
        {"symbol": "XOM", "weight": 3},
        {"symbol": "NEE", "weight": 2}
    ]
    
    analysis = analyzer.analyze(test_stocks)
    ui_data = format_exposure_for_ui(analysis)
    
    print("\n" + "="*50)
    print("SECTOR EXPOSURE ANALYSIS")
    print("="*50)
    print(f"Concentration Score: {analysis.concentration_score}/100")
    print(f"HHI Index: {analysis.hhi_index}")
    print("\nSectors:")
    for s in analysis.sectors:
        print(f"  {s.name}: {s.weight}%")
    print("\nWarnings:")
    for w in analysis.warnings:
        print(f"  ⚠️ {w}")
