"""
Index Builder API
Builds custom stock indices based on user queries (Generated Assets).
Combines semantic search + quantitative filters + AI ranking.
"""

import os
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional, Any, Tuple
from openai import OpenAI
from dotenv import load_dotenv
from dataclasses import dataclass, asdict

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IndexBuilder")

# Database URLs
INDIA_DB = os.getenv("DATABASE_URL", 
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")
US_DB = os.getenv("US_DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/usmarkets")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


@dataclass
class IndexStock:
    """A stock included in a generated index."""
    symbol: str
    company_name: str
    relevance_score: float  # 0-100
    weight: float  # portfolio weight
    market: str  # 'india' or 'us'
    justification: str
    metrics: Dict[str, Any]


@dataclass 
class GeneratedIndex:
    """A complete generated index/asset."""
    name: str
    description: str
    query: str
    stocks: List[IndexStock]
    total_stocks: int
    average_score: float
    created_at: str


class IndexBuilder:
    """
    Builds custom indices from natural language queries.
    
    Examples:
    - "AI-focused companies with positive cash flow"
    - "High ROIC companies with low debt"
    - "EV exposure with revenue growth > 20%"
    """
    
    QUERY_PARSER_PROMPT = """Parse this investment query into structured filters.
Return JSON with:
- themes: list of themes to search for (ai, cloud, ev, renewable, healthcare, etc.)
- quantitative_filters: dict of metric conditions (e.g., {"profit_margin": ">10", "debt_to_equity": "<1"})
- market: "india", "us", or "both"
- min_companies: ideal number of companies (default 10)

Query: {query}

JSON only:"""

    RANKING_PROMPT = """You are ranking stocks for an investment index.
Given this query: "{query}"

And these candidate stocks with their relevance data:
{candidates}

Rank them 0-100 based on how well they match the query intent.
Consider both thematic relevance and financial strength.

Return JSON array with: [{{"symbol": "X", "score": 85, "justification": "brief reason"}}]
Top 15 only:"""

    def __init__(self, market: str = "india"):
        self.market = market
        self.db_url = INDIA_DB if market == "india" else US_DB
        self.conn = psycopg2.connect(self.db_url)
        self.client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    
    def parse_query(self, query: str) -> Dict[str, Any]:
        """Parse natural language query into structured filters."""
        if not self.client:
            return {"themes": [], "quantitative_filters": {}, "market": self.market}
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Parse investment queries into structured filters. JSON only."},
                    {"role": "user", "content": self.QUERY_PARSER_PROMPT.format(query=query)}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"Query parse error: {e}")
            return {"themes": [], "quantitative_filters": {}, "market": self.market}
    
    def semantic_search(self, query: str, limit: int = 50) -> List[Dict]:
        """Find relevant document chunks using vector similarity."""
        if not self.client:
            return []
        
        # Get query embedding
        try:
            response = self.client.embeddings.create(
                input=query,
                model="text-embedding-3-small"
            )
            query_embedding = response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return []
        
        # Vector search
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT DISTINCT ON (symbol) 
                symbol, 
                fiscal_year,
                chunk_text,
                1 - (embedding <=> %s::vector) as similarity
            FROM document_chunks
            WHERE embedding IS NOT NULL
            ORDER BY symbol, embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, query_embedding, limit))
        
        results = [dict(row) for row in cur.fetchall()]
        cur.close()
        
        return results
    
    def get_company_metrics(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch metrics for companies (from fundamentals table or extracted)."""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        
        # For India, use annual_reports table
        if self.market == "india":
            table = "annual_reports"
            cur.execute(f"""
                SELECT DISTINCT ON (symbol) symbol, fiscal_year, nuanced_summary
                FROM {table}
                WHERE symbol = ANY(%s)
                ORDER BY symbol, fiscal_year DESC
            """, (symbols,))
        else:
            # For US, use company_fundamentals if available
            cur.execute("""
                SELECT DISTINCT ON (symbol) symbol, fiscal_year, 
                       revenue, net_income, operating_cash_flow, eps,
                       roic, roe, profit_margin, debt_to_equity
                FROM company_fundamentals
                WHERE symbol = ANY(%s)
                ORDER BY symbol, fiscal_year DESC
            """, (symbols,))
        
        metrics = {}
        for row in cur.fetchall():
            metrics[row['symbol']] = dict(row)
        
        cur.close()
        return metrics
    
    def rank_candidates(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """Use AI to rank candidates based on query relevance."""
        if not self.client or not candidates:
            return candidates
        
        # Prepare candidate summary
        candidate_text = "\n".join([
            f"- {c['symbol']}: similarity={c.get('similarity', 0):.2f}, excerpt={c.get('chunk_text', '')[:200]}..."
            for c in candidates[:20]  # Limit for token efficiency
        ])
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Rank stocks for investment indices. JSON array only."},
                    {"role": "user", "content": self.RANKING_PROMPT.format(
                        query=query, candidates=candidate_text
                    )}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            
            rankings = json.loads(content)
            
            # Merge rankings with candidates
            ranking_map = {r['symbol']: r for r in rankings}
            for c in candidates:
                if c['symbol'] in ranking_map:
                    c['relevance_score'] = ranking_map[c['symbol']]['score']
                    c['justification'] = ranking_map[c['symbol']].get('justification', '')
            
            return sorted(candidates, key=lambda x: x.get('relevance_score', 0), reverse=True)
            
        except Exception as e:
            logger.error(f"Ranking error: {e}")
            return candidates
    
    def build_index(self, query: str, max_stocks: int = 15) -> GeneratedIndex:
        """Build a complete index from a natural language query."""
        logger.info(f"Building index for: {query}")
        
        # 1. Parse query
        parsed = self.parse_query(query)
        logger.info(f"Parsed: {parsed}")
        
        # 2. Semantic search
        candidates = self.semantic_search(query, limit=50)
        logger.info(f"Found {len(candidates)} candidates via semantic search")
        
        # 3. Rank candidates
        ranked = self.rank_candidates(query, candidates)
        
        # 4. Get top stocks
        top_stocks = ranked[:max_stocks]
        symbols = [s['symbol'] for s in top_stocks]
        
        # 5. Get metrics
        metrics = self.get_company_metrics(symbols)
        
        # 6. Build index stocks
        index_stocks = []
        for i, stock in enumerate(top_stocks):
            weight = round(100 / max_stocks, 2)  # Equal weight
            index_stocks.append(IndexStock(
                symbol=stock['symbol'],
                company_name=stock.get('company_name', stock['symbol']),
                relevance_score=stock.get('relevance_score', stock.get('similarity', 0) * 100),
                weight=weight,
                market=self.market,
                justification=stock.get('justification', 'Matched query theme'),
                metrics=metrics.get(stock['symbol'], {})
            ))
        
        # 7. Create index
        avg_score = sum(s.relevance_score for s in index_stocks) / len(index_stocks) if index_stocks else 0
        
        from datetime import datetime
        return GeneratedIndex(
            name=f"Custom Index: {query[:50]}",
            description=f"AI-generated index based on: {query}",
            query=query,
            stocks=index_stocks,
            total_stocks=len(index_stocks),
            average_score=round(avg_score, 1),
            created_at=datetime.now().isoformat()
        )
    
    def to_json(self, index: GeneratedIndex) -> str:
        """Convert index to JSON for API response."""
        data = {
            "name": index.name,
            "description": index.description,
            "query": index.query,
            "total_stocks": index.total_stocks,
            "average_score": index.average_score,
            "created_at": index.created_at,
            "stocks": [asdict(s) for s in index.stocks]
        }
        return json.dumps(data, indent=2)


if __name__ == "__main__":
    # Test with India market
    builder = IndexBuilder(market="india")
    
    query = "AI and technology focused companies with strong cash flows"
    print(f"Query: {query}\n")
    
    index = builder.build_index(query)
    print(builder.to_json(index))
