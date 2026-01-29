"""
Inwezt - Database Module
PostgreSQL storage for comprehensive stock data (RAG foundation).
"""
import os
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.errors import UniqueViolation
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InweztDB")

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """Get a database connection."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not configured")
    return psycopg2.connect(DATABASE_URL)


def init_database():
    """Initialize all database tables."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Stock Master - Basic company info
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_master (
            symbol VARCHAR(20) PRIMARY KEY,
            name VARCHAR(200),
            sector VARCHAR(100),
            industry VARCHAR(100),
            market_cap_category VARCHAR(20),
            isin VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Daily Price History
    cur.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            trade_date DATE NOT NULL,
            open_price DECIMAL(12,2),
            high_price DECIMAL(12,2),
            low_price DECIMAL(12,2),
            close_price DECIMAL(12,2),
            volume BIGINT,
            delivery_pct DECIMAL(6,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, trade_date)
        )
    """)
    
    # Create index for faster lookups
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_history_symbol_date 
        ON price_history(symbol, trade_date DESC)
    """)
    
    # Quarterly Financials
    cur.execute("""
        CREATE TABLE IF NOT EXISTS financials (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            period_end DATE NOT NULL,
            period_type VARCHAR(10) DEFAULT 'Q',
            revenue BIGINT,
            net_profit BIGINT,
            eps DECIMAL(10,2),
            pe_ratio DECIMAL(10,2),
            pb_ratio DECIMAL(10,2),
            roe DECIMAL(10,2),
            net_margin DECIMAL(10,2),
            debt_equity DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, period_end, period_type)
        )
    """)
    
    # Stock Snapshots (daily metrics from IndianAPI)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_snapshots (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            snapshot_date DATE NOT NULL,
            price DECIMAL(12,2),
            change_pct DECIMAL(8,2),
            pe_ratio DECIMAL(10,2),
            sector_pe DECIMAL(10,2),
            market_cap DECIMAL(15,2),
            eps_ttm DECIMAL(10,2),
            high_52w DECIMAL(12,2),
            low_52w DECIMAL(12,2),
            beta DECIMAL(6,2),
            analyst_score DECIMAL(5,2),
            ytd_change DECIMAL(8,2),
            source VARCHAR(50) DEFAULT 'IndianAPI',
            raw_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, snapshot_date)
        )
    """)
    
    # News Articles
    cur.execute("""
        CREATE TABLE IF NOT EXISTS news_articles (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20),
            headline TEXT NOT NULL,
            summary TEXT,
            source VARCHAR(100),
            url TEXT,
            published_at TIMESTAMP,
            sentiment_score DECIMAL(4,2),
            embedding_id VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_symbol_date 
        ON news_articles(symbol, published_at DESC)
    """)
    
    # Query History (for learning patterns)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS query_history (
            id SERIAL PRIMARY KEY,
            query TEXT NOT NULL,
            symbols TEXT[],
            intent VARCHAR(50),
            response TEXT,
            processing_time_ms INTEGER,
            user_feedback VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Analyst Ratings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analyst_ratings (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            source VARCHAR(100),
            rating VARCHAR(30),
            target_price DECIMAL(12,2),
            analyst_name VARCHAR(100),
            firm VARCHAR(100),
            updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Corporate Filings (Earnings, Annual Reports)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS corporate_filings (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            title TEXT,
            doc_type VARCHAR(50),
            url TEXT,
            doc_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, url)
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_filings_symbol_date 
        ON corporate_filings(symbol, doc_date DESC)
    """)
    
    # Concalls (Earnings Call Transcripts from Trendlyne)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS concalls (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            quarter VARCHAR(10),
            fiscal_year VARCHAR(10),
            call_date DATE,
            title TEXT,
            transcript TEXT,
            key_highlights TEXT,
            management_guidance TEXT,
            url TEXT,
            source VARCHAR(50) DEFAULT 'Trendlyne',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            nuanced_summary TEXT,
            UNIQUE(symbol, quarter, fiscal_year)
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_concalls_symbol_date 
        ON concalls(symbol, call_date DESC)
    """)
    
    # Annual Reports (from Trendlyne or BSE/NSE)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS annual_reports (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20) NOT NULL,
            fiscal_year VARCHAR(10) NOT NULL,
            report_date DATE,
            title TEXT,
            summary TEXT,
            key_metrics JSONB,
            chairman_letter TEXT,
            url TEXT,
            source VARCHAR(50) DEFAULT 'Trendlyne',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            nuanced_summary TEXT,
            UNIQUE(symbol, fiscal_year)
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_annual_reports_symbol_year 
        ON annual_reports(symbol, fiscal_year DESC)
    """)

    # Knowledge Base (for Inwezt specific Q&A)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id SERIAL PRIMARY KEY,
            topic VARCHAR(100),
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            embedding_id VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Database tables initialized successfully")



def _sanitize_text(text: Optional[str]) -> Optional[str]:
    """Remove NUL characters from text to prevent PostgreSQL errors."""
    if isinstance(text, str):
        return text.replace('\x00', '')
    return text


def save_stock_snapshot(data: Dict[str, Any]) -> bool:
    """Save a stock snapshot from IndianAPI to database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO stock_snapshots 
            (symbol, snapshot_date, price, change_pct, pe_ratio, sector_pe, 
             market_cap, eps_ttm, high_52w, low_52w, beta, analyst_score, 
             ytd_change, book_value, dividend_per_share, revenue_per_share,
             revenue_growth, profit_growth, net_margin, roe, source, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, snapshot_date) DO UPDATE SET
                price = EXCLUDED.price,
                change_pct = EXCLUDED.change_pct,
                pe_ratio = EXCLUDED.pe_ratio,
                sector_pe = EXCLUDED.sector_pe,
                market_cap = EXCLUDED.market_cap,
                eps_ttm = EXCLUDED.eps_ttm,
                high_52w = EXCLUDED.high_52w,
                low_52w = EXCLUDED.low_52w,
                beta = EXCLUDED.beta,
                analyst_score = EXCLUDED.analyst_score,
                ytd_change = EXCLUDED.ytd_change,
                book_value = EXCLUDED.book_value,
                dividend_per_share = EXCLUDED.dividend_per_share,
                revenue_per_share = EXCLUDED.revenue_per_share,
                revenue_growth = EXCLUDED.revenue_growth,
                profit_growth = EXCLUDED.profit_growth,
                net_margin = EXCLUDED.net_margin,
                roe = EXCLUDED.roe,
                raw_data = EXCLUDED.raw_data
        """, (
            data.get("ticker"),
            date.today(),
            data.get("price"),
            data.get("change_pct"),
            data.get("pe_ratio"),
            data.get("sector_pe"),
            data.get("market_cap"),
            data.get("eps_ttm"),
            data.get("high_52w"),
            data.get("low_52w"),
            data.get("beta"),
            data.get("analyst_score"),
            data.get("ytd_change"),
            data.get("book_value"),
            data.get("dividend_per_share"),
            data.get("revenue_per_share"),
            data.get("revenue_growth"),
            data.get("profit_growth"),
            data.get("net_margin"),
            data.get("roe"),
            data.get("source", "IndianAPI"),
            psycopg2.extras.Json(data)
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to save snapshot: {e}")
        return False


def save_news_article(symbol: str, article: Dict[str, Any]) -> bool:
    """Save a news article to database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO news_articles 
            (symbol, headline, summary, source, url, published_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            symbol,
            _sanitize_text(article.get("headline")),
            _sanitize_text(article.get("summary")),
            "LiveMint",  # IndianAPI sources from LiveMint
            article.get("url"),
            article.get("date")
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to save news: {e}")
        return False


def save_corporate_filing(symbol: str, filing: Dict[str, Any]) -> bool:
    """Save a corporate filing to database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO corporate_filings 
            (symbol, title, doc_type, url, doc_date)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (symbol, url) DO NOTHING
        """, (
            symbol,
            _sanitize_text(filing.get("title")),
            filing.get("type"),
            filing.get("url"),
            filing.get("date")
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to save filing: {e}")
        return False


def save_query_history(query: str, symbols: List[str], intent: str, 
                       response: str, processing_time: int) -> bool:
    """Save query history for learning."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO query_history 
            (query, symbols, intent, response, processing_time_ms)
            VALUES (%s, %s, %s, %s, %s)
        """, (query, symbols, intent, response, processing_time))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to save query history: {e}")
        return False


def get_historical_snapshots(symbol: str, days: int = 30) -> List[Dict]:
    """Get historical snapshots for a symbol."""
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT * FROM stock_snapshots 
            WHERE symbol = %s 
            ORDER BY snapshot_date DESC 
            LIMIT %s
        """, (symbol, days))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]
        
    except Exception as e:
        logger.error(f"Failed to get snapshots: {e}")
        return []


def get_recent_news(symbol: str, limit: int = 10) -> List[Dict]:
    """Get recent news for a symbol."""
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT headline, summary, published_at, url 
            FROM news_articles 
            WHERE symbol = %s 
            ORDER BY published_at DESC 
            LIMIT %s
        """, (symbol, limit))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]
        
    except Exception as e:
        logger.error(f"Failed to get news: {e}")
        return []


def get_corporate_filings(symbol: str, limit: int = 5) -> List[Dict]:
    """Get recent corporate filings for a symbol."""
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT title, doc_type, url, doc_date 
            FROM corporate_filings 
            WHERE symbol = %s 
            ORDER BY doc_date DESC 
            LIMIT %s
        """, (symbol, limit))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        # Format dates
        results = []
        for row in rows:
            r = dict(row)
            if isinstance(r.get('doc_date'), (date, datetime)):
                r['doc_date'] = str(r['doc_date'])
            results.append(r)
            
        return results
        
    except Exception as e:
        logger.error(f"Failed to get filings: {e}")
        return []


def save_concall(symbol: str, concall: Dict[str, Any]) -> bool:
    """Save an earnings call transcript to database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO concalls (symbol, quarter, fiscal_year, call_date, title, transcript, 
             key_highlights, management_guidance, nuanced_summary, url, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, quarter, fiscal_year) DO UPDATE SET
                transcript = EXCLUDED.transcript,
                key_highlights = EXCLUDED.key_highlights,
                management_guidance = EXCLUDED.management_guidance,
                nuanced_summary = EXCLUDED.nuanced_summary,
                updated_at = CURRENT_TIMESTAMP
        """, (
            symbol,
            concall.get("quarter"),
            concall.get("fiscal_year"),
            concall.get("call_date"),
            _sanitize_text(concall.get("title")),
            _sanitize_text(concall.get("transcript")),
            _sanitize_text(concall.get("key_highlights")),
            _sanitize_text(concall.get("management_guidance")),
            _sanitize_text(concall.get("nuanced_summary")),
            concall.get("url"),
            concall.get("source", "Trendlyne")
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to save concall: {e}")
        return False


def concall_exists(symbol: str, quarter: str, fiscal_year: str) -> bool:
    """Check if a concall already exists in the database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM concalls WHERE symbol = %s AND quarter = %s AND fiscal_year = %s",
            (symbol, quarter, fiscal_year)
        )
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Error checking concall existence: {e}")
        return False


def concall_url_exists(url: str) -> bool:
    """Check if a concall URL already exists in the database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM concalls WHERE url = %s", (url,))
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Error checking concall URL existence: {e}")
        return False


def update_concall_metadata(url: str, quarter: str, fiscal_year: str) -> bool:
    """Update metadata for an existing concall if it is currently null."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Only update if currently null or 'None'
        cur.execute("""
            UPDATE concalls 
            SET quarter = %s, fiscal_year = %s 
            WHERE url = %s AND (fiscal_year IS NULL OR fiscal_year = 'None')
        """, (quarter, fiscal_year, url))
        
        updated = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        return updated
        return updated
    except UniqueViolation:
        logger.warning(f"Unique constraint violation updating metadata for {url}. Skipping.")
        conn.rollback() # Important to rollback the transaction
        cur.close()
        conn.close()
        return False
    except Exception as e:
        logger.error(f"Error updating concall metadata: {e}")
        conn.rollback()
        cur.close()
        conn.close()
        return False


def get_concalls(symbol: str, limit: int = 8) -> List[Dict]:
    """Get recent earnings call transcripts for a symbol."""
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT quarter, fiscal_year, call_date, title, transcript, 
                   key_highlights, management_guidance, nuanced_summary, url
            FROM concalls 
            WHERE symbol = %s 
            ORDER BY call_date DESC 
            LIMIT %s
        """, (symbol, limit))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        results = []
        for row in rows:
            r = dict(row)
            if isinstance(r.get('call_date'), (date, datetime)):
                r['call_date'] = str(r['call_date'])
            results.append(r)
            
        return results
        
    except Exception as e:
        logger.error(f"Failed to get concalls: {e}")
        return []


def save_annual_report(symbol: str, report: Dict[str, Any]) -> bool:
    """Save an annual report to database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO annual_reports (symbol, fiscal_year, report_date, title, summary, 
             key_metrics, chairman_letter, nuanced_summary, url, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, fiscal_year) DO UPDATE SET
                summary = EXCLUDED.summary,
                key_metrics = EXCLUDED.key_metrics,
                chairman_letter = EXCLUDED.chairman_letter,
                nuanced_summary = EXCLUDED.nuanced_summary
        """, (
            symbol,
            report.get("fiscal_year"),
            report.get("report_date"),
            _sanitize_text(report.get("title")),
            _sanitize_text(report.get("summary")),
            psycopg2.extras.Json(report.get("key_metrics", {})),
            _sanitize_text(report.get("chairman_letter")),
            _sanitize_text(report.get("nuanced_summary")),
            report.get("url"),
            report.get("source", "Trendlyne")
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to save annual report: {e}")
        return False


def annual_report_exists(symbol: str, fiscal_year: str) -> bool:
    """Check if an annual report already exists in the database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM annual_reports WHERE symbol = %s AND fiscal_year = %s",
            (symbol, fiscal_year)
        )
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Error checking annual report existence: {e}")
        return False


def annual_report_url_exists(url: str) -> bool:
    """Check if an annual report URL already exists in the database."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM annual_reports WHERE url = %s", (url,))
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Error checking annual report URL existence: {e}")
        return False


def get_annual_reports(symbol: str, limit: int = 3) -> List[Dict]:
    """Get recent annual reports for a symbol."""
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT fiscal_year, report_date, title, summary, 
                   key_metrics, chairman_letter, nuanced_summary, url
            FROM annual_reports 
            WHERE symbol = %s 
            ORDER BY fiscal_year DESC 
            LIMIT %s
        """, (symbol, limit))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        results = []
        for row in rows:
            r = dict(row)
            if isinstance(r.get('report_date'), (date, datetime)):
                r['report_date'] = str(r['report_date'])
            results.append(r)
            
        return results
        
    except Exception as e:
        logger.error(f"Failed to get annual reports: {e}")
        return []


def get_stock_coverage(symbol: str) -> Dict[str, int]:
    """
    Get coverage counts for a stock.
    Returns: {'annual_reports': int, 'concalls': int}
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM annual_reports WHERE symbol = %s", (symbol,))
        ar_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM concalls WHERE symbol = %s", (symbol,))
        concall_count = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        return {'annual_reports': ar_count, 'concalls': concall_count}
        
    except Exception as e:
        logger.error(f"Failed to get stock coverage: {e}")
        return {'annual_reports': 0, 'concalls': 0}


def save_knowledge(topic: str, question: str, answer: str) -> bool:
    """Save a knowledge base item."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO knowledge_base (topic, question, answer)
            VALUES (%s, %s, %s)
        """, (topic, question, answer))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to save knowledge: {e}")
        return False


def get_knowledge(query: str, limit: int = 3) -> List[Dict]:
    """
    Get relevant knowledge items. 
    (Currently simple search, can be upgraded to vector search later)
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Simple keyword search for now
        cur.execute("""
            SELECT topic, question, answer 
            FROM knowledge_base 
            WHERE question ILIKE %s OR answer ILIKE %s
            LIMIT %s
        """, (f'%{query}%', f'%{query}%', limit))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get knowledge: {e}")
        return []


def get_stock_history(symbol: str, years: int = 5) -> Dict[str, List]:
    """
    Get long-term historical data for a symbol.
    Returns dictionaries of list of prices and valuations.
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get historical prices
        cur.execute("""
            SELECT trade_date, price, dma_50, dma_200, volume 
            FROM historical_prices 
            WHERE symbol = %s AND trade_date >= (CURRENT_DATE - INTERVAL '%s years')
            ORDER BY trade_date ASC
        """, (symbol, years))
        price_rows = cur.fetchall()
        
        # Get historical valuations
        cur.execute("""
            SELECT trade_date, pe_ratio, eps 
            FROM historical_valuations 
            WHERE symbol = %s AND trade_date >= (CURRENT_DATE - INTERVAL '%s years')
            ORDER BY trade_date ASC
        """, (symbol, years))
        valuation_rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Format for context
        prices = []
        for row in price_rows:
            prices.append({
                "date": str(row['trade_date']),
                "price": float(row['price']) if row['price'] else None,
                "dma50": float(row['dma_50']) if row['dma_50'] else None,
                "dma200": float(row['dma_200']) if row['dma_200'] else None
            })
            
        valuations = []
        for row in valuation_rows:
            valuations.append({
                "date": str(row['trade_date']),
                "pe": float(row['pe_ratio']) if row['pe_ratio'] else None,
                "eps": float(row['eps']) if row['eps'] else None
            })
            
        return {
            "prices": prices,
            "valuations": valuations,
            "years_requested": years
        }
        
    except Exception as e:
        logger.error(f"Failed to get stock history: {e}")
        return {"prices": [], "valuations": []}


def get_stock_context_from_db(symbol: str) -> Dict[str, Any]:
    """Get comprehensive context for a stock from database."""
    context = {
        "symbol": symbol,
        "has_historical_data": False,
        "snapshots": [],
        "news": [],
        "trend": None
    }
    
    # Get recent snapshots
    snapshots = get_historical_snapshots(symbol, 7)
    if snapshots:
        context["has_historical_data"] = True
        context["snapshots"] = snapshots
        
        # Calculate short-term trend
        if len(snapshots) >= 2:
            latest = snapshots[0].get("price", 0)
            oldest = snapshots[-1].get("price", 0)
            if oldest and latest:
                trend_pct = ((latest - oldest) / oldest) * 100
                context["trend"] = {
                    "direction": "up" if trend_pct > 0 else "down",
                    "change_pct": round(trend_pct, 2),
                    "period_days": len(snapshots)
                }
    
    # Get long-term history (10 years for accurate CAGR)
    history = get_stock_history(symbol, years=10)
    if history["prices"]:
        context["history"] = history
        context["has_long_term_data"] = True
        
        # Add long-term trend with 10-year CAGR
        prices = history["prices"]
        if len(prices) > 1:
            start_price = prices[0]["price"]
            end_price = prices[-1]["price"]
            if start_price and end_price:
                # Calculate actual years between dates
                from datetime import datetime
                start_date = datetime.strptime(prices[0]["date"], "%Y-%m-%d")
                end_date = datetime.strptime(prices[-1]["date"], "%Y-%m-%d")
                years_diff = (end_date - start_date).days / 365.25
                
                lt_change = ((end_price - start_price) / start_price) * 100
                cagr_10yr = ((end_price / start_price) ** (1/years_diff) - 1) * 100 if years_diff > 0 else 0
                
                context["long_term_trend"] = {
                    "start_price": round(start_price, 2),
                    "start_date": prices[0]["date"],
                    "end_price": round(end_price, 2), 
                    "end_date": prices[-1]["date"],
                    "change_pct_total": round(lt_change, 2),
                    "years": round(years_diff, 1),
                    "cagr_10yr": round(cagr_10yr, 2)
                }
    
    # Get recent news
    context["news"] = get_recent_news(symbol, 5)
    
    return context



def get_historical_price_data(symbol: str, days: int = 365) -> List[Dict[str, Any]]:
    """
    Get historical price data for a specific number of days.
    Useful for analyzing trends, moving averages, and volume.
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT trade_date, price, dma_50, dma_200, volume, delivery_pct
            FROM historical_prices 
            WHERE symbol = %s AND trade_date >= (CURRENT_DATE - make_interval(days := %s))
            ORDER BY trade_date ASC
        """, (symbol, days))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convert dates to strings for JSON serialization
        results = []
        for row in rows:
            row_dict = dict(row)
            if isinstance(row_dict.get('trade_date'), (date, datetime)):
                row_dict['trade_date'] = str(row_dict['trade_date'])
            results.append(row_dict)
            
        return results
        
    except Exception as e:
        logger.error(f"Failed to get historical prices: {e}")
        return []


def get_historical_valuation_data(symbol: str, days: int = 365) -> List[Dict[str, Any]]:
    """
    Get historical valuation data (PE, EPS) for a specific number of days.
    Useful for analyzing valuation trends and earnings growth.
    """
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT trade_date, pe_ratio, eps, sector_pe
            FROM historical_valuations
            WHERE symbol = %s AND trade_date >= (CURRENT_DATE - make_interval(days := %s))
            ORDER BY trade_date ASC
        """, (symbol, days))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convert dates to strings for JSON serialization
        results = []
        for row in rows:
            row_dict = dict(row)
            if isinstance(row_dict.get('trade_date'), (date, datetime)):
                row_dict['trade_date'] = str(row_dict['trade_date'])
            results.append(row_dict)
            
        return results
        
    except Exception as e:
        logger.error(f"Failed to get historical valuations: {e}")
        return []


# Nifty 500 stocks for bulk ingestion
NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", 
    "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK",
    "BAJFINANCE", "ASIANPAINT", "MARUTI", "HCLTECH", "SUNPHARMA",
    "TITAN", "WIPRO", "ULTRACEMCO", "NTPC", "TECHM", "NESTLEIND",
    "POWERGRID", "TATASTEEL", "ONGC", "JSWSTEEL", "COALINDIA",
    "BAJAJFINSV", "GRASIM", "TATAMOTORS", "ADANIPORTS", "HINDALCO",
    "M&M", "DRREDDY", "BRITANNIA", "CIPLA", "BPCL", "DIVISLAB",
    "EICHERMOT", "APOLLOHOSP", "HDFCLIFE", "SBILIFE", "TATACONSUM",
    "HEROMOTOCO", "UPL", "INDUSINDBK", "BAJAJ-AUTO", "LTIM"
]


if __name__ == "__main__":
    print("Initializing database...")
    init_database()
    print("Database ready!")
    
    # Test connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM stock_snapshots")
    count = cur.fetchone()[0]
    print(f"Current snapshots in DB: {count}")
    cur.close()
    conn.close()
