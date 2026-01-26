
from typing import Dict, Any, List
from .base import BaseAgent
from backend.database.database import get_corporate_filings, get_concalls, get_annual_reports
from .summarizer import summarize_document

class FilingsAgent(BaseAgent):
    """
    Agent responsible for retrieving and analyzing Corporate Filings (RAG).
    Also fetches quarterly financial results from yfinance.
    """
    
    def __init__(self):
        super().__init__(name="FilingsAgent")
        
    def _get_quarterly_financials(self, symbol: str) -> Dict[str, Any]:
        """Fetch quarterly financial data from yfinance."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(f"{symbol}.NS")
            inc = ticker.quarterly_income_stmt
            
            if inc is None or inc.empty:
                return {}
            
            results = []
            for col in inc.columns[:4]:  # Last 4 quarters
                quarter_data = {
                    "quarter_end": col.strftime("%Y-%m-%d"),
                    "revenue_cr": None,
                    "net_profit_cr": None,
                    "ebitda_cr": None
                }
                
                if 'Total Revenue' in inc.index:
                    val = inc.loc['Total Revenue', col]
                    if val and not (isinstance(val, float) and val != val):  # Check for NaN
                        quarter_data["revenue_cr"] = round(float(val) / 1e7, 2)  # Convert to Crores
                        
                if 'Net Income' in inc.index:
                    val = inc.loc['Net Income', col]
                    if val and not (isinstance(val, float) and val != val):
                        quarter_data["net_profit_cr"] = round(float(val) / 1e7, 2)
                        
                if 'EBITDA' in inc.index:
                    val = inc.loc['EBITDA', col]
                    if val and not (isinstance(val, float) and val != val):
                        quarter_data["ebitda_cr"] = round(float(val) / 1e7, 2)
                
                results.append(quarter_data)
            
            return {"quarterly_results": results}
            
        except Exception as e:
            self._log_activity(f"Failed to fetch quarterly financials: {e}")
            return {}
        
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieves recent filings, concalls, and annual reports.
        Applies nuanced summarization to deep documents for V3.
        """
        symbol = context.get("formatted_tickers", [])[0] if context.get("formatted_tickers") else None
        
        if not symbol:
            return {
                "response": "I couldn't identify a stock symbol to search filings for.",
                "data": {},
                "source": "FilingsAgent"
            }
            
        self._log_activity(f"V3: Retrieving deep context for {symbol}")
        
        # 1. Fetch Basic Filings
        filings = get_corporate_filings(symbol, limit=5)
        
        # 2. Fetch Concalls & Summarize
        concalls = get_concalls(symbol, limit=1)
        concall_data = []
        for call in concalls:
            transcript = call.get("transcript", "")
            if len(transcript) > 500:
                self._log_activity(f"Summarizing concall for {symbol} ({call.get('fiscal_year')} {call.get('quarter')})")
                summary = summarize_document(transcript, doc_type="Concall")
                call["nuanced_summary"] = summary
            concall_data.append(call)
            
        # 3. Fetch Annual Reports & Summarize
        reports = get_annual_reports(symbol, limit=1)
        report_data = []
        for report in reports:
            # Check for chairman letter or summary
            deep_content = report.get("chairman_letter") or report.get("summary") or ""
            if len(deep_content) > 500:
                self._log_activity(f"Summarizing annual report for {symbol} ({report.get('fiscal_year')})")
                summary = summarize_document(deep_content, doc_type="Annual Report")
                report["nuanced_summary"] = summary
            report_data.append(report)

        # 4. Check for quarterly results focus
        query_lower = query.lower()
        is_results_query = any(term in query_lower for term in 
            ['result', 'quarterly', 'profit', 'revenue', 'earnings', 'financial', 'guidance', 'margin'])
        
        data = {
            "filings": filings if filings else [],
            "concalls": concall_data,
            "annual_reports": report_data
        }
        
        # 5. Fetch Actual Financial Numbers if requested
        if is_results_query:
            financials = self._get_quarterly_financials(symbol)
            if financials:
                data.update(financials)
                self._log_activity(f"Fetched quarterly financials for {symbol}")
        
        has_deep_data = bool(concall_data or report_data)
        
        return {
            "has_data": bool(filings or has_deep_data),
            "data": data,
            "source": "FilingsAgent (V3)",
            "relevance_score": 0.95 if is_results_query else 0.7
        }
