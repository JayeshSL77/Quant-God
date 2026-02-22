"""
Risk Metrics Calculator
Calculates risk metrics optimized for UI/UX display.
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json
import statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RiskMetrics")


@dataclass
class RiskMetrics:
    """Complete risk metrics for an index."""
    # Core metrics
    sharpe_ratio: float
    sortino_ratio: float
    beta: float
    alpha_annual: float
    
    # Volatility metrics
    volatility_annual: float
    volatility_monthly: float
    downside_deviation: float
    
    # Drawdown metrics
    max_drawdown: float
    avg_drawdown: float
    drawdown_duration_days: int
    
    # VaR and tail risk
    var_95: float  # 95% Value at Risk (daily)
    var_99: float  # 99% Value at Risk (daily)
    cvar_95: float  # Conditional VaR (Expected Shortfall)
    
    # Correlation data
    correlation_with_benchmark: float
    
    # Risk rating (for UI)
    risk_score: int  # 1-10
    risk_label: str  # Low, Medium, High, Very High


class RiskCalculator:
    """
    Calculates comprehensive risk metrics.
    Outputs optimized for frontend visualization.
    """
    
    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate  # Annual risk-free rate
    
    def calculate(self, daily_returns: List[float], benchmark_returns: List[float]) -> RiskMetrics:
        """
        Calculate all risk metrics from daily returns.
        
        Args:
            daily_returns: List of daily portfolio returns (as decimals, e.g., 0.01 = 1%)
            benchmark_returns: List of daily benchmark returns
        """
        if len(daily_returns) < 30:
            return self._default_metrics()
        
        # Basic stats
        avg_return = statistics.mean(daily_returns)
        std_dev = statistics.stdev(daily_returns)
        
        # Annualized metrics
        annual_return = avg_return * 252
        volatility_annual = std_dev * (252 ** 0.5)
        volatility_monthly = std_dev * (21 ** 0.5)
        
        # Sharpe Ratio
        excess_return = annual_return - self.risk_free_rate
        sharpe = excess_return / volatility_annual if volatility_annual > 0 else 0
        
        # Downside deviation (Sortino)
        negative_returns = [r for r in daily_returns if r < 0]
        if negative_returns:
            downside_dev = statistics.stdev(negative_returns) * (252 ** 0.5)
            sortino = excess_return / downside_dev if downside_dev > 0 else 0
        else:
            downside_dev = 0
            sortino = sharpe * 1.5  # Estimate if no negative days
        
        # Beta and Alpha
        if len(benchmark_returns) >= len(daily_returns):
            benchmark_returns = benchmark_returns[:len(daily_returns)]
        
        if len(benchmark_returns) >= 30:
            # Covariance and variance
            cov = self._covariance(daily_returns, benchmark_returns)
            var_benchmark = statistics.variance(benchmark_returns)
            beta = cov / var_benchmark if var_benchmark > 0 else 1.0
            
            # Alpha (annualized)
            benchmark_annual_return = statistics.mean(benchmark_returns) * 252
            alpha = annual_return - (self.risk_free_rate + beta * (benchmark_annual_return - self.risk_free_rate))
            
            # Correlation
            correlation = self._correlation(daily_returns, benchmark_returns)
        else:
            beta = 1.0
            alpha = 0
            correlation = 0.8
        
        # Drawdowns
        max_dd, avg_dd, dd_duration = self._calculate_drawdowns(daily_returns)
        
        # VaR (Value at Risk)
        sorted_returns = sorted(daily_returns)
        var_95 = abs(sorted_returns[int(len(sorted_returns) * 0.05)]) * 100
        var_99 = abs(sorted_returns[int(len(sorted_returns) * 0.01)]) * 100
        
        # CVaR (Expected Shortfall) - average of worst 5%
        worst_5pct = sorted_returns[:int(len(sorted_returns) * 0.05)]
        cvar_95 = abs(statistics.mean(worst_5pct)) * 100 if worst_5pct else var_95
        
        # Risk score (1-10)
        risk_score = self._calculate_risk_score(volatility_annual, max_dd, beta, var_95)
        risk_label = self._risk_label(risk_score)
        
        return RiskMetrics(
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            beta=round(beta, 2),
            alpha_annual=round(alpha * 100, 2),  # As percentage
            volatility_annual=round(volatility_annual * 100, 2),
            volatility_monthly=round(volatility_monthly * 100, 2),
            downside_deviation=round(downside_dev * 100, 2),
            max_drawdown=round(max_dd, 2),
            avg_drawdown=round(avg_dd, 2),
            drawdown_duration_days=dd_duration,
            var_95=round(var_95, 2),
            var_99=round(var_99, 2),
            cvar_95=round(cvar_95, 2),
            correlation_with_benchmark=round(correlation, 2),
            risk_score=risk_score,
            risk_label=risk_label
        )
    
    def _covariance(self, x: List[float], y: List[float]) -> float:
        """Calculate covariance."""
        n = min(len(x), len(y))
        if n < 2:
            return 0
        mean_x = statistics.mean(x[:n])
        mean_y = statistics.mean(y[:n])
        return sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / (n - 1)
    
    def _correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation."""
        n = min(len(x), len(y))
        if n < 2:
            return 0
        cov = self._covariance(x[:n], y[:n])
        std_x = statistics.stdev(x[:n])
        std_y = statistics.stdev(y[:n])
        if std_x == 0 or std_y == 0:
            return 0
        return cov / (std_x * std_y)
    
    def _calculate_drawdowns(self, returns: List[float]) -> tuple:
        """Calculate drawdown metrics."""
        cumulative = 1.0
        peak = 1.0
        max_drawdown = 0
        drawdowns = []
        current_dd_days = 0
        max_dd_duration = 0
        
        for r in returns:
            cumulative *= (1 + r)
            if cumulative > peak:
                peak = cumulative
                if current_dd_days > 0:
                    max_dd_duration = max(max_dd_duration, current_dd_days)
                    current_dd_days = 0
            else:
                dd = (peak - cumulative) / peak
                max_drawdown = max(max_drawdown, dd)
                current_dd_days += 1
                if dd > 0.01:  # Track drawdowns > 1%
                    drawdowns.append(dd)
        
        avg_drawdown = statistics.mean(drawdowns) if drawdowns else 0
        
        return max_drawdown * 100, avg_drawdown * 100, max_dd_duration
    
    def _calculate_risk_score(self, vol: float, max_dd: float, beta: float, var: float) -> int:
        """Calculate risk score from 1-10."""
        # Weight different factors
        vol_score = min(vol * 100 / 5, 10)  # 50% vol = 10
        dd_score = min(max_dd / 10, 10)  # 100% dd = 10
        beta_score = min(beta * 5, 10)  # beta 2 = 10
        var_score = min(var / 0.5, 10)  # 5% daily VaR = 10
        
        # Weighted average
        score = (vol_score * 0.3 + dd_score * 0.3 + beta_score * 0.2 + var_score * 0.2)
        return max(1, min(10, int(round(score))))
    
    def _risk_label(self, score: int) -> str:
        """Convert score to label."""
        if score <= 3:
            return "Low Risk"
        if score <= 5:
            return "Moderate"
        if score <= 7:
            return "High Risk"
        return "Very High Risk"
    
    def _default_metrics(self) -> RiskMetrics:
        """Return default metrics when data is insufficient."""
        return RiskMetrics(
            sharpe_ratio=0, sortino_ratio=0, beta=1.0, alpha_annual=0,
            volatility_annual=0, volatility_monthly=0, downside_deviation=0,
            max_drawdown=0, avg_drawdown=0, drawdown_duration_days=0,
            var_95=0, var_99=0, cvar_95=0, correlation_with_benchmark=0,
            risk_score=5, risk_label="Unknown"
        )


def format_risk_for_ui(metrics: RiskMetrics) -> Dict:
    """Format risk metrics for optimal UI display."""
    return {
        # Risk gauge (main visualization)
        "gauge": {
            "score": metrics.risk_score,
            "label": metrics.risk_label,
            "color": _score_color(metrics.risk_score)
        },
        
        # Primary metrics (cards)
        "primary_metrics": [
            {
                "label": "Sharpe Ratio",
                "value": metrics.sharpe_ratio,
                "description": "Risk-adjusted return",
                "status": "good" if metrics.sharpe_ratio > 1 else "warning" if metrics.sharpe_ratio > 0.5 else "bad"
            },
            {
                "label": "Beta",
                "value": metrics.beta,
                "description": "Market sensitivity",
                "status": "good" if 0.8 <= metrics.beta <= 1.2 else "warning"
            },
            {
                "label": "Max Drawdown",
                "value": f"-{metrics.max_drawdown}%",
                "description": "Worst decline",
                "status": "good" if metrics.max_drawdown < 20 else "warning" if metrics.max_drawdown < 40 else "bad"
            },
            {
                "label": "Volatility",
                "value": f"{metrics.volatility_annual}%",
                "description": "Annual price swings",
                "status": "good" if metrics.volatility_annual < 20 else "warning" if metrics.volatility_annual < 35 else "bad"
            }
        ],
        
        # Detailed metrics (expandable)
        "detailed_metrics": {
            "Return Metrics": [
                {"label": "Alpha", "value": f"{metrics.alpha_annual}%"},
                {"label": "Sortino Ratio", "value": metrics.sortino_ratio},
            ],
            "Volatility": [
                {"label": "Annual", "value": f"{metrics.volatility_annual}%"},
                {"label": "Monthly", "value": f"{metrics.volatility_monthly}%"},
                {"label": "Downside", "value": f"{metrics.downside_deviation}%"},
            ],
            "Tail Risk": [
                {"label": "VaR 95%", "value": f"{metrics.var_95}%"},
                {"label": "VaR 99%", "value": f"{metrics.var_99}%"},
                {"label": "CVaR 95%", "value": f"{metrics.cvar_95}%"},
            ],
            "Drawdowns": [
                {"label": "Max", "value": f"-{metrics.max_drawdown}%"},
                {"label": "Average", "value": f"-{metrics.avg_drawdown}%"},
                {"label": "Longest", "value": f"{metrics.drawdown_duration_days} days"},
            ]
        },
        
        # Benchmark comparison
        "vs_benchmark": {
            "correlation": metrics.correlation_with_benchmark,
            "beta": metrics.beta
        }
    }


def _score_color(score: int) -> str:
    """Get color for risk score."""
    if score <= 3:
        return "#22c55e"  # Green
    if score <= 5:
        return "#eab308"  # Yellow
    if score <= 7:
        return "#f97316"  # Orange
    return "#ef4444"  # Red


if __name__ == "__main__":
    # Test with sample data
    import random
    random.seed(42)
    
    # Generate sample returns
    daily_returns = [random.gauss(0.0005, 0.015) for _ in range(500)]
    benchmark_returns = [random.gauss(0.0004, 0.012) for _ in range(500)]
    
    calculator = RiskCalculator()
    metrics = calculator.calculate(daily_returns, benchmark_returns)
    
    print("\n" + "="*50)
    print("RISK METRICS")
    print("="*50)
    print(f"Risk Score: {metrics.risk_score}/10 ({metrics.risk_label})")
    print(f"Sharpe: {metrics.sharpe_ratio}")
    print(f"Sortino: {metrics.sortino_ratio}")
    print(f"Beta: {metrics.beta}")
    print(f"Alpha: {metrics.alpha_annual}%")
    print(f"Volatility: {metrics.volatility_annual}%")
    print(f"Max Drawdown: {metrics.max_drawdown}%")
    print(f"VaR 95%: {metrics.var_95}%")
