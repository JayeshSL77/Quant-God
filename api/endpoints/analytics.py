"""
Analytics API
Unified API for backtesting, risk metrics, and sector exposure.
All endpoints return UI-optimized data.
"""

from flask import Blueprint, request, jsonify
import logging
import sys
import os
from datetime import datetime, timedelta

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.backtester import Backtester, format_for_ui as format_backtest
from analytics.risk_metrics import RiskCalculator, format_risk_for_ui
from analytics.sector_exposure import ExposureAnalyzer, format_exposure_for_ui

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnalyticsAPI")

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/api/analytics/backtest', methods=['POST'])
def backtest():
    """
    Backtest a generated index.
    
    Request:
    {
        "stocks": [{"symbol": "AAPL", "weight": 25}, ...],
        "start_date": "2020-01-01",
        "end_date": "2025-01-01",
        "initial_investment": 100000,
        "market": "us"
    }
    
    Response:
    {
        "success": true,
        "data": {
            "hero": {...},
            "metrics": [...],
            "chart": {...},
            "rolling_returns": {...}
        }
    }
    """
    try:
        data = request.get_json()
        
        stocks = data.get('stocks', [])
        market = data.get('market', 'india')
        start_date = data.get('start_date', (datetime.now() - timedelta(days=1825)).strftime('%Y-%m-%d'))
        end_date = data.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        initial = data.get('initial_investment', 100000)
        
        if not stocks:
            return jsonify({"success": False, "error": "No stocks provided"}), 400
        
        backtester = Backtester(market=market)
        result = backtester.run_backtest(
            stocks=stocks,
            start_date=start_date,
            end_date=end_date,
            initial_investment=initial
        )
        
        return jsonify({
            "success": True,
            "data": format_backtest(result)
        })
        
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@analytics_bp.route('/api/analytics/risk', methods=['POST'])
def risk_metrics():
    """
    Calculate risk metrics for an index.
    
    Request:
    {
        "stocks": [{"symbol": "AAPL", "weight": 25}, ...],
        "period_days": 252,
        "market": "us"
    }
    
    Response:
    {
        "success": true,
        "data": {
            "gauge": {...},
            "primary_metrics": [...],
            "detailed_metrics": {...}
        }
    }
    """
    try:
        data = request.get_json()
        
        stocks = data.get('stocks', [])
        market = data.get('market', 'india')
        period_days = data.get('period_days', 252)  # Default 1 year
        
        if not stocks:
            return jsonify({"success": False, "error": "No stocks provided"}), 400
        
        # Get historical returns
        import yfinance as yf
        
        symbols = [s["symbol"] for s in stocks]
        weights = {s["symbol"]: s["weight"] / 100 for s in stocks}
        
        benchmark = "^NSEI" if market == "india" else "^GSPC"
        
        # Fetch data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days + 30)
        
        # Get portfolio returns
        portfolio_returns = []
        benchmark_returns = []
        
        try:
            # Get benchmark returns
            bench_hist = yf.Ticker(benchmark).history(start=start_date, end=end_date)
            if not bench_hist.empty:
                bench_close = bench_hist["Close"].tolist()
                benchmark_returns = [(bench_close[i] / bench_close[i-1]) - 1 
                                    for i in range(1, len(bench_close))]
            
            # Get weighted portfolio returns
            stock_returns = {}
            for symbol in symbols:
                try:
                    suffix = ".NS" if market == "india" else ""
                    hist = yf.Ticker(f"{symbol}{suffix}").history(start=start_date, end=end_date)
                    if not hist.empty:
                        closes = hist["Close"].tolist()
                        stock_returns[symbol] = [(closes[i] / closes[i-1]) - 1 
                                                for i in range(1, len(closes))]
                except:
                    pass
            
            # Combine into portfolio returns
            if stock_returns:
                min_len = min(len(r) for r in stock_returns.values())
                for i in range(min_len):
                    daily_return = 0
                    for symbol, returns in stock_returns.items():
                        if i < len(returns):
                            daily_return += weights.get(symbol, 0) * returns[i]
                    portfolio_returns.append(daily_return)
        except Exception as e:
            logger.error(f"Error fetching returns: {e}")
        
        # Calculate metrics
        calculator = RiskCalculator()
        metrics = calculator.calculate(portfolio_returns, benchmark_returns)
        
        return jsonify({
            "success": True,
            "data": format_risk_for_ui(metrics)
        })
        
    except Exception as e:
        logger.error(f"Risk metrics error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@analytics_bp.route('/api/analytics/exposure', methods=['POST'])
def sector_exposure():
    """
    Analyze sector/industry exposure.
    
    Request:
    {
        "stocks": [{"symbol": "AAPL", "weight": 25}, ...],
        "market": "us"
    }
    
    Response:
    {
        "success": true,
        "data": {
            "treemap": {...},
            "sector_chart": {...},
            "concentration": {...},
            "warnings": [...]
        }
    }
    """
    try:
        data = request.get_json()
        
        stocks = data.get('stocks', [])
        market = data.get('market', 'india')
        
        if not stocks:
            return jsonify({"success": False, "error": "No stocks provided"}), 400
        
        analyzer = ExposureAnalyzer(market=market)
        analysis = analyzer.analyze(stocks)
        
        return jsonify({
            "success": True,
            "data": format_exposure_for_ui(analysis)
        })
        
    except Exception as e:
        logger.error(f"Exposure analysis error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@analytics_bp.route('/api/analytics/full', methods=['POST'])
def full_analytics():
    """
    Get all analytics in one call (backtest + risk + exposure).
    
    Request:
    {
        "stocks": [...],
        "market": "us",
        "backtest_years": 5,
        "initial_investment": 100000
    }
    
    Response:
    {
        "success": true,
        "data": {
            "backtest": {...},
            "risk": {...},
            "exposure": {...}
        }
    }
    """
    try:
        data = request.get_json()
        
        stocks = data.get('stocks', [])
        market = data.get('market', 'india')
        years = data.get('backtest_years', 5)
        initial = data.get('initial_investment', 100000)
        
        if not stocks:
            return jsonify({"success": False, "error": "No stocks provided"}), 400
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime('%Y-%m-%d')
        
        # Run all analytics
        backtester = Backtester(market=market)
        backtest_result = backtester.run_backtest(stocks, start_date, end_date, initial)
        
        # Extract returns for risk calculation
        chart_data = backtest_result.chart_data
        if len(chart_data) > 1:
            portfolio_returns = []
            benchmark_returns = []
            for i in range(1, len(chart_data)):
                p_return = (chart_data[i]['portfolio'] / chart_data[i-1]['portfolio']) - 1
                b_return = (chart_data[i]['benchmark'] / chart_data[i-1]['benchmark']) - 1
                portfolio_returns.append(p_return)
                benchmark_returns.append(b_return)
            
            calculator = RiskCalculator()
            risk_result = calculator.calculate(portfolio_returns, benchmark_returns)
        else:
            risk_result = RiskCalculator()._default_metrics()
        
        analyzer = ExposureAnalyzer(market=market)
        exposure_result = analyzer.analyze(stocks)
        
        return jsonify({
            "success": True,
            "data": {
                "backtest": format_backtest(backtest_result),
                "risk": format_risk_for_ui(risk_result),
                "exposure": format_exposure_for_ui(exposure_result)
            }
        })
        
    except Exception as e:
        logger.error(f"Full analytics error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Standalone test server
if __name__ == "__main__":
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(analytics_bp)
    
    print("Starting Analytics API on http://localhost:5002")
    print("\nEndpoints:")
    print("  POST /api/analytics/backtest  - Run backtest")
    print("  POST /api/analytics/risk      - Get risk metrics")
    print("  POST /api/analytics/exposure  - Sector exposure")
    print("  POST /api/analytics/full      - All in one")
    
    app.run(port=5002, debug=True)
