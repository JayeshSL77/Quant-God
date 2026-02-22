"""
Backtesting Engine
Shows historical performance of generated indices with graphical data.
"If you had bought this 5 years ago, your return trajectory would be..."
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Backtester")


@dataclass
class BacktestPoint:
    """A single point in the backtest timeline."""
    date: str
    portfolio_value: float
    benchmark_value: float
    return_pct: float  # Cumulative return %
    benchmark_return_pct: float
    alpha: float  # Outperformance vs benchmark


@dataclass
class BacktestResult:
    """Complete backtest results optimized for UI/UX."""
    # Summary metrics (for cards)
    total_return_pct: float
    cagr: float
    benchmark_return_pct: float
    alpha: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    
    # Chart data (for graphs)
    chart_data: List[Dict]  # [{date, portfolio, benchmark, drawdown}]
    
    # Rolling returns (for bar charts)
    rolling_1y: float
    rolling_3y: float
    rolling_5y: float
    
    # Drawdown periods (for visualization)
    drawdown_periods: List[Dict]
    
    # Summary for display
    summary_text: str
    
    # Metadata
    start_date: str
    end_date: str
    initial_investment: float
    final_value: float


class Backtester:
    """
    Backtests generated indices against benchmarks.
    Returns data optimized for frontend visualization.
    """
    
    BENCHMARKS = {
        "india": "^NSEI",  # Nifty 50
        "us": "^GSPC",     # S&P 500
    }
    
    def __init__(self, market: str = "india"):
        self.market = market
        self.benchmark = self.BENCHMARKS.get(market, "^GSPC")
    
    def get_historical_prices(self, symbols: List[str], start_date: str, end_date: str) -> Dict[str, List[Dict]]:
        """Fetch historical prices for backtesting."""
        try:
            import yfinance as yf
            
            prices = {}
            
            for symbol in symbols:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(start=start_date, end=end_date)
                
                if not hist.empty:
                    prices[symbol] = [
                        {"date": d.strftime("%Y-%m-%d"), "close": round(row["Close"], 2)}
                        for d, row in hist.iterrows()
                    ]
            
            return prices
            
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return {}
    
    def run_backtest(
        self,
        stocks: List[Dict],  # [{symbol, weight}]
        start_date: str,
        end_date: str,
        initial_investment: float = 100000,
        rebalance_frequency: str = "quarterly"
    ) -> BacktestResult:
        """
        Run backtest and return UI-optimized results.
        
        Args:
            stocks: List of {symbol, weight} dicts
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            initial_investment: Starting amount
            rebalance_frequency: quarterly, monthly, annual
        """
        symbols = [s["symbol"] for s in stocks]
        weights = {s["symbol"]: s["weight"] / 100 for s in stocks}
        
        # Fetch prices
        all_symbols = symbols + [self.benchmark]
        prices = self.get_historical_prices(all_symbols, start_date, end_date)
        
        if not prices or self.benchmark not in prices:
            return self._empty_result(start_date, end_date, initial_investment)
        
        # Calculate daily portfolio value
        benchmark_prices = {p["date"]: p["close"] for p in prices[self.benchmark]}
        dates = sorted(benchmark_prices.keys())
        
        if not dates:
            return self._empty_result(start_date, end_date, initial_investment)
        
        # Normalize all prices to start at 1.0
        normalized = {}
        for symbol in symbols:
            if symbol in prices and prices[symbol]:
                symbol_prices = {p["date"]: p["close"] for p in prices[symbol]}
                first_price = next((symbol_prices.get(d) for d in dates if d in symbol_prices), None)
                if first_price:
                    normalized[symbol] = {d: symbol_prices.get(d, first_price) / first_price 
                                         for d in dates if d in symbol_prices}
        
        # Calculate portfolio value over time
        chart_data = []
        portfolio_values = []
        benchmark_values = []
        
        first_benchmark = benchmark_prices[dates[0]]
        
        for date in dates:
            # Portfolio return (weighted average of normalized returns)
            portfolio_return = 0
            active_weight = 0
            
            for symbol, weight in weights.items():
                if symbol in normalized and date in normalized[symbol]:
                    portfolio_return += weight * normalized[symbol][date]
                    active_weight += weight
            
            if active_weight > 0:
                portfolio_return /= active_weight  # Normalize for missing stocks
            else:
                portfolio_return = 1.0
            
            # Benchmark return
            benchmark_return = benchmark_prices[date] / first_benchmark
            
            portfolio_value = initial_investment * portfolio_return
            benchmark_value = initial_investment * benchmark_return
            
            portfolio_values.append(portfolio_value)
            benchmark_values.append(benchmark_value)
            
            chart_data.append({
                "date": date,
                "portfolio": round(portfolio_value, 2),
                "benchmark": round(benchmark_value, 2),
                "portfolio_return": round((portfolio_return - 1) * 100, 2),
                "benchmark_return": round((benchmark_return - 1) * 100, 2)
            })
        
        # Calculate metrics
        final_portfolio = portfolio_values[-1] if portfolio_values else initial_investment
        final_benchmark = benchmark_values[-1] if benchmark_values else initial_investment
        
        total_return = ((final_portfolio / initial_investment) - 1) * 100
        benchmark_return = ((final_benchmark / initial_investment) - 1) * 100
        
        # CAGR
        years = max((datetime.strptime(end_date, "%Y-%m-%d") - 
                    datetime.strptime(start_date, "%Y-%m-%d")).days / 365, 0.01)
        cagr = ((final_portfolio / initial_investment) ** (1 / years) - 1) * 100
        
        # Volatility and Sharpe
        daily_returns = []
        for i in range(1, len(portfolio_values)):
            daily_return = (portfolio_values[i] / portfolio_values[i-1]) - 1
            daily_returns.append(daily_return)
        
        if daily_returns:
            import statistics
            volatility = statistics.stdev(daily_returns) * (252 ** 0.5) * 100  # Annualized
            avg_return = statistics.mean(daily_returns) * 252 * 100  # Annualized
            sharpe = avg_return / volatility if volatility > 0 else 0
        else:
            volatility = 0
            sharpe = 0
        
        # Max Drawdown
        max_drawdown = 0
        peak = portfolio_values[0]
        drawdown_periods = []
        in_drawdown = False
        dd_start = None
        
        for i, val in enumerate(portfolio_values):
            if val > peak:
                peak = val
                if in_drawdown:
                    drawdown_periods.append({
                        "start": dd_start,
                        "end": dates[i-1] if i > 0 else dates[0],
                        "depth": round(max_drawdown, 2)
                    })
                    in_drawdown = False
            else:
                drawdown = ((peak - val) / peak) * 100
                if drawdown > 5 and not in_drawdown:  # Start tracking at 5%
                    in_drawdown = True
                    dd_start = dates[i]
                max_drawdown = max(max_drawdown, drawdown)
        
        # Rolling returns
        def get_rolling_return(days: int) -> float:
            if len(portfolio_values) < days:
                return 0
            period_return = (portfolio_values[-1] / portfolio_values[-min(days, len(portfolio_values))]) - 1
            return round(period_return * 100, 2)
        
        # Generate summary text
        performance = "outperformed" if total_return > benchmark_return else "underperformed"
        summary = f"Your index would have turned ₹{initial_investment:,.0f} into ₹{final_portfolio:,.0f}, " \
                  f"a {total_return:.1f}% return ({cagr:.1f}% CAGR). " \
                  f"This {performance} the benchmark by {abs(total_return - benchmark_return):.1f}%."
        
        return BacktestResult(
            total_return_pct=round(total_return, 2),
            cagr=round(cagr, 2),
            benchmark_return_pct=round(benchmark_return, 2),
            alpha=round(total_return - benchmark_return, 2),
            sharpe_ratio=round(sharpe, 2),
            max_drawdown=round(max_drawdown, 2),
            volatility=round(volatility, 2),
            chart_data=chart_data,
            rolling_1y=get_rolling_return(252),
            rolling_3y=get_rolling_return(756),
            rolling_5y=get_rolling_return(1260),
            drawdown_periods=drawdown_periods[:5],  # Top 5 drawdowns
            summary_text=summary,
            start_date=start_date,
            end_date=end_date,
            initial_investment=initial_investment,
            final_value=round(final_portfolio, 2)
        )
    
    def _empty_result(self, start: str, end: str, initial: float) -> BacktestResult:
        """Return empty result when data is unavailable."""
        return BacktestResult(
            total_return_pct=0,
            cagr=0,
            benchmark_return_pct=0,
            alpha=0,
            sharpe_ratio=0,
            max_drawdown=0,
            volatility=0,
            chart_data=[],
            rolling_1y=0,
            rolling_3y=0,
            rolling_5y=0,
            drawdown_periods=[],
            summary_text="Insufficient data for backtest",
            start_date=start,
            end_date=end,
            initial_investment=initial,
            final_value=initial
        )
    
    def to_json(self, result: BacktestResult) -> str:
        """Convert result to JSON for API response."""
        return json.dumps(asdict(result), indent=2)


# API Response Format for Frontend
def format_for_ui(result: BacktestResult) -> Dict:
    """Format backtest result for optimal UI/UX display."""
    return {
        # Hero section
        "hero": {
            "headline": f"₹{result.final_value:,.0f}",
            "subheadline": f"+{result.total_return_pct}% total return",
            "summary": result.summary_text
        },
        
        # Metric cards
        "metrics": [
            {"label": "Total Return", "value": f"{result.total_return_pct}%", "color": "green" if result.total_return_pct > 0 else "red"},
            {"label": "CAGR", "value": f"{result.cagr}%", "color": "green" if result.cagr > 0 else "red"},
            {"label": "Alpha", "value": f"{result.alpha}%", "color": "green" if result.alpha > 0 else "red"},
            {"label": "Sharpe Ratio", "value": f"{result.sharpe_ratio}", "color": "green" if result.sharpe_ratio > 1 else "yellow"},
            {"label": "Max Drawdown", "value": f"-{result.max_drawdown}%", "color": "red"},
            {"label": "Volatility", "value": f"{result.volatility}%", "color": "yellow"},
        ],
        
        # Main chart data (portfolio vs benchmark)
        "chart": {
            "type": "line",
            "data": result.chart_data,
            "series": [
                {"key": "portfolio", "name": "Your Index", "color": "#4ade80"},
                {"key": "benchmark", "name": "Benchmark", "color": "#94a3b8"}
            ]
        },
        
        # Rolling returns bar chart
        "rolling_returns": {
            "type": "bar",
            "data": [
                {"period": "1 Year", "return": result.rolling_1y},
                {"period": "3 Year", "return": result.rolling_3y},
                {"period": "5 Year", "return": result.rolling_5y}
            ]
        },
        
        # Drawdown visualization
        "drawdowns": result.drawdown_periods,
        
        # Period info
        "period": {
            "start": result.start_date,
            "end": result.end_date,
            "initial": result.initial_investment
        }
    }


if __name__ == "__main__":
    # Test backtest
    backtester = Backtester(market="us")
    
    # Sample index
    test_stocks = [
        {"symbol": "AAPL", "weight": 25},
        {"symbol": "MSFT", "weight": 25},
        {"symbol": "GOOGL", "weight": 25},
        {"symbol": "NVDA", "weight": 25}
    ]
    
    result = backtester.run_backtest(
        stocks=test_stocks,
        start_date="2020-01-01",
        end_date="2025-01-01",
        initial_investment=100000
    )
    
    print("\n" + "="*60)
    print("BACKTEST RESULTS")
    print("="*60)
    print(result.summary_text)
    print(f"\nTotal Return: {result.total_return_pct}%")
    print(f"CAGR: {result.cagr}%")
    print(f"Alpha: {result.alpha}%")
    print(f"Sharpe: {result.sharpe_ratio}")
    print(f"Max Drawdown: {result.max_drawdown}%")
    print(f"\nChart data points: {len(result.chart_data)}")
