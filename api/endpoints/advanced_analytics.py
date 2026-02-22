"""
Advanced Analytics API
Unified API for Level 2-3 features: Insider Signals, ESG, Sentiment,
Agent Swarm, Thesis Generator, Contrarian Finder.
"""

from flask import Blueprint, request, jsonify
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.insider_signals import InsiderTracker, format_insider_for_ui
from analytics.sentiment_trends import SentimentAnalyzer, format_sentiment_for_ui
from analytics.esg_scoring import ESGAnalyzer, format_esg_for_ui
from agents.agent_swarm import AgentSwarm, format_swarm_for_ui
from agents.thesis_generator import ThesisGenerator, format_thesis_for_ui
from agents.contrarian_finder import ContrarianAnalyzer, format_contrarian_for_ui

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AdvancedAnalyticsAPI")

advanced_bp = Blueprint('advanced', __name__)


# ========== LEVEL 2 ENDPOINTS ==========

@advanced_bp.route('/api/insider/<symbol>', methods=['GET'])
def get_insider_signals(symbol: str):
    """
    Get insider trading signals for a stock.
    
    Response includes buy/sell transactions, cluster detection, and signals.
    """
    try:
        cik = request.args.get('cik', '')  # Optional CIK for US stocks
        
        tracker = InsiderTracker()
        analysis = tracker.analyze_stock(symbol.upper(), cik)
        
        return jsonify({
            "success": True,
            "data": format_insider_for_ui(analysis)
        })
        
    except Exception as e:
        logger.error(f"Insider signals error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@advanced_bp.route('/api/sentiment-trend/<symbol>', methods=['GET'])
def get_sentiment_trend(symbol: str):
    """
    Get earnings call sentiment trend across quarters.
    
    Query params:
        market: india|us (default: india)
        quarters: number of quarters to analyze (default: 8)
    """
    try:
        market = request.args.get('market', 'india')
        quarters = int(request.args.get('quarters', 8))
        
        analyzer = SentimentAnalyzer(market=market)
        trend = analyzer.analyze_trend(symbol.upper(), quarters)
        
        return jsonify({
            "success": True,
            "data": format_sentiment_for_ui(trend)
        })
        
    except Exception as e:
        logger.error(f"Sentiment trend error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@advanced_bp.route('/api/esg/<symbol>', methods=['GET'])
def get_esg_score(symbol: str):
    """
    Get ESG (Environmental, Social, Governance) score.
    
    Query params:
        market: india|us (default: india)
    """
    try:
        market = request.args.get('market', 'india')
        
        analyzer = ESGAnalyzer(market=market)
        score = analyzer.score_company(symbol.upper())
        
        return jsonify({
            "success": True,
            "data": format_esg_for_ui(score)
        })
        
    except Exception as e:
        logger.error(f"ESG scoring error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ========== LEVEL 3 ENDPOINTS ==========

@advanced_bp.route('/api/swarm-analysis/<symbol>', methods=['GET'])
def get_swarm_analysis(symbol: str):
    """
    Run multi-agent swarm analysis.
    
    Deploys multiple specialized AI agents to analyze the stock.
    
    Query params:
        market: india|us (default: india)
    """
    try:
        market = request.args.get('market', 'india')
        
        swarm = AgentSwarm(market=market)
        report = swarm.run_analysis(symbol.upper())
        
        return jsonify({
            "success": True,
            "data": format_swarm_for_ui(report)
        })
        
    except Exception as e:
        logger.error(f"Swarm analysis error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@advanced_bp.route('/api/thesis/<symbol>', methods=['GET'])
def get_investment_thesis(symbol: str):
    """
    Generate comprehensive investment thesis.
    
    Query params:
        market: india|us (default: india)
    """
    try:
        market = request.args.get('market', 'india')
        
        generator = ThesisGenerator(market=market)
        thesis = generator.generate(symbol.upper())
        
        return jsonify({
            "success": True,
            "data": format_thesis_for_ui(thesis)
        })
        
    except Exception as e:
        logger.error(f"Thesis generation error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@advanced_bp.route('/api/contrarian', methods=['GET'])
def find_contrarian():
    """
    Find contrarian opportunities.
    
    Query params:
        market: india|us (default: india)
        symbols: comma-separated symbols (optional)
        limit: max results (default: 10)
    """
    try:
        market = request.args.get('market', 'india')
        symbols_str = request.args.get('symbols', '')
        limit = int(request.args.get('limit', 10))
        
        symbols = [s.strip().upper() for s in symbols_str.split(',')] if symbols_str else None
        
        analyzer = ContrarianAnalyzer(market=market)
        opportunities = analyzer.find_contrarian_opportunities(symbols=symbols, limit=limit)
        
        return jsonify({
            "success": True,
            "data": format_contrarian_for_ui(opportunities)
        })
        
    except Exception as e:
        logger.error(f"Contrarian finder error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ========== COMBINED ENDPOINTS ==========

@advanced_bp.route('/api/deep-dive/<symbol>', methods=['GET'])
def get_deep_dive(symbol: str):
    """
    Complete deep dive analysis combining all Level 2-3 features.
    
    Returns: ESG, Sentiment Trends, Agent Swarm, Investment Thesis
    """
    try:
        market = request.args.get('market', 'india')
        symbol = symbol.upper()
        
        results = {}
        
        # ESG
        try:
            esg_analyzer = ESGAnalyzer(market=market)
            results['esg'] = format_esg_for_ui(esg_analyzer.score_company(symbol))
        except:
            results['esg'] = None
        
        # Sentiment Trends
        try:
            sentiment_analyzer = SentimentAnalyzer(market=market)
            results['sentiment_trend'] = format_sentiment_for_ui(
                sentiment_analyzer.analyze_trend(symbol, 8)
            )
        except:
            results['sentiment_trend'] = None
        
        # Agent Swarm
        try:
            swarm = AgentSwarm(market=market)
            results['swarm_analysis'] = format_swarm_for_ui(swarm.run_analysis(symbol))
        except:
            results['swarm_analysis'] = None
        
        # Investment Thesis
        try:
            generator = ThesisGenerator(market=market)
            results['thesis'] = format_thesis_for_ui(generator.generate(symbol))
        except:
            results['thesis'] = None
        
        return jsonify({
            "success": True,
            "symbol": symbol,
            "data": results
        })
        
    except Exception as e:
        logger.error(f"Deep dive error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Standalone test server
if __name__ == "__main__":
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(advanced_bp)
    
    print("Starting Advanced Analytics API on http://localhost:5003")
    print("\nLevel 2 Endpoints:")
    print("  GET /api/insider/<symbol>       - Insider trading signals")
    print("  GET /api/sentiment-trend/<symbol> - Earnings sentiment trends")
    print("  GET /api/esg/<symbol>           - ESG scoring")
    print("\nLevel 3 Endpoints:")
    print("  GET /api/swarm-analysis/<symbol> - Multi-agent swarm")
    print("  GET /api/thesis/<symbol>         - Investment thesis")
    print("  GET /api/contrarian             - Contrarian opportunities")
    print("  GET /api/deep-dive/<symbol>     - Complete analysis")
    
    app.run(port=5003, debug=True)
