
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
        In comparison_mode, uses lighter processing for speed.
        """
        symbol = context.get("formatted_tickers", [])[0] if context.get("formatted_tickers") else None
        comparison_mode = context.get("comparison_mode", False)
        
        if not symbol:
            return {
                "response": "I couldn't identify a stock symbol to search filings for.",
                "data": {},
                "source": "FilingsAgent"
            }
            
        self._log_activity(f"V3: Retrieving deep context for {symbol}" + (" (comparison mode)" if comparison_mode else ""))
        
        # 1. Fetch Basic Filings
        filings = get_corporate_filings(symbol, limit=3 if comparison_mode else 5)
        
        # 2. Fetch Concalls & Summarize
        # In comparison mode: only 2 recent concalls, skip LLM summarization for uncached
        concall_limit = 2 if comparison_mode else 8
        concalls = get_concalls(symbol, limit=concall_limit)
        concall_data = []
        from backend.database.database import save_concall 

        for call in concalls:
            existing_summary = call.get("nuanced_summary")
            if existing_summary and len(existing_summary) > 200:
                self._log_activity(f"Using cached concall summary for {symbol}")
            elif not comparison_mode:
                # Only do LLM summarization in full mode, not comparison mode
                transcript = call.get("transcript", "")
                if len(transcript) > 500:
                    summary = summarize_document(transcript, doc_type="Concall")
                    call["nuanced_summary"] = summary
                    save_concall(symbol, call)
            concall_data.append(call)
            
        # 3. Fetch Annual Reports & Summarize
        # In comparison mode: only 2 recent reports, skip LLM summarization for uncached
        report_limit = 2 if comparison_mode else 7
        reports = get_annual_reports(symbol, limit=report_limit)
        report_data = []
        annual_results = []
        from backend.database.database import save_annual_report 

        for report in reports:
            # Extract numerical data for charting
            metrics = report.get("key_metrics", {})
            if metrics:
                annual_results.append({
                    "fiscal_year": report.get("fiscal_year"),
                    "revenue_cr": metrics.get("Revenue", metrics.get("Total Revenue", metrics.get("revenue", 0))),
                    "net_profit_cr": metrics.get("Net Profit", metrics.get("PAT", metrics.get("net_profit", 0))),
                    "ebitda_cr": metrics.get("EBITDA", metrics.get("ebitda", 0))
                })

            existing_summary = report.get("nuanced_summary")
            if existing_summary and len(existing_summary) > 200:
                self._log_activity(f"Using cached annual report summary for {symbol}")
            elif not comparison_mode:
                # Only do LLM summarization in full mode, not comparison mode
                deep_content = report.get("chairman_letter") or report.get("summary") or ""
                if len(deep_content) > 500:
                    summary = summarize_document(deep_content, doc_type="Annual Report")
                    report["nuanced_summary"] = summary
                    save_annual_report(symbol, report)
            report_data.append(report)

        # 4. Check for quarterly results focus
        query_lower = query.lower()
        is_results_query = any(term in query_lower for term in 
            ['result', 'quarterly', 'profit', 'revenue', 'earnings', 'financial', 'guidance', 'margin', 'trend'])
        
        data = {
            "filings": filings if filings else [],
            "concalls": concall_data,
            "annual_reports": report_data,
            "annual_results": sorted(annual_results, key=lambda x: str(x.get("fiscal_year", "")))
        }
        
        # 5. Fetch Actual Financial Numbers (LAST 8 QUARTERS)
        if is_results_query:
            financials = self._get_quarterly_financials(symbol)
            if financials:
                # yfinance usually gives 4, but let's try to pass whatever we get 
                data.update(financials)
                self._log_activity(f"Fetched quarterly financials for {symbol}")
        
        return {
            "has_data": bool(filings or concall_data or report_data),
            "data": data,
            "source": "FilingsAgent (V3)",
            "relevance_score": 0.95 if is_results_query else 0.7
        }

