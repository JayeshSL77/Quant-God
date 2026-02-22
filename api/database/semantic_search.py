"""
Inwezt Semantic Search Module — Hybrid RAG v2
Powers the RAG system with 5-layer Hybrid Search:
  Vector + BM25 + RRF + Reranking + Metadata Filtering

AI Native Supreme Hedge Fund — 11,000 Agent Swarm
"""

import os
import logging
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from .embeddings import get_embedding

# Hybrid engine (new)
try:
    from .hybrid_search import hybrid_search as _hybrid_search
    from .hybrid_search import get_context_for_agent, search_across_market as _market_search
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SemanticSearch")

DATABASE_URL = os.getenv("DATABASE_URL")


def semantic_search(query: str, 
                    symbol: Optional[str] = None,
                    source_type: Optional[str] = None,  # 'annual_reports' or 'concalls'
                    fiscal_year: Optional[str] = None,
                    top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Search for relevant document chunks.
    Routes to Hybrid RAG (vector + BM25 + RRF + reranking) when available,
    falls back to vector-only search.
    """
    # Route through hybrid engine if available
    if HYBRID_AVAILABLE:
        logger.info("Using Hybrid RAG engine (vector + BM25 + RRF)")
        doc_type = None
        if source_type == 'annual_reports':
            doc_type = 'annual_report'
        elif source_type == 'concalls':
            doc_type = 'concall'
        return _hybrid_search(
            query=query,
            symbol=symbol,
            fiscal_year=fiscal_year,
            doc_type=doc_type,
            top_k=top_k,
            use_reranker=True
        )
    
    # Fallback: original vector-only search
    logger.info("Hybrid RAG not available, using vector-only search")
    query_embedding = get_embedding(query)
    if not query_embedding:
        logger.error("Failed to generate query embedding")
        return []
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Build dynamic WHERE clause
        conditions = ["embedding IS NOT NULL"]
        params = []
        
        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol)
        
        if source_type:
            conditions.append("source_table = %s")
            params.append(source_type)
        
        if fiscal_year:
            conditions.append("fiscal_year = %s")
            params.append(fiscal_year)
        
        where_clause = " AND ".join(conditions)
        
        # Vector similarity search using pgvector
        # Using <=> operator for cosine distance (smaller = more similar)
        query_sql = f"""
            SELECT 
                id,
                source_table,
                source_id,
                symbol,
                fiscal_year,
                quarter,
                chunk_index,
                section_type,
                LEFT(chunk_text, 1000) as chunk_preview,
                1 - (embedding <=> %s::vector) as similarity
            FROM document_chunks
            WHERE {where_clause}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        
        # Convert embedding to PostgreSQL array format
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        cur.execute(query_sql, [embedding_str] + params + [embedding_str, top_k])
        results = cur.fetchall()
        
        return [dict(r) for r in results]
        
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_context_for_query(query: str, 
                          symbol: str,
                          top_k: int = 5,
                          fiscal_year: Optional[str] = None) -> str:
    """
    Build a context string from relevant document chunks for RAG.
    Routes to Hybrid RAG agent context builder when available.
    """
    # Route to hybrid engine if available
    if HYBRID_AVAILABLE:
        return get_context_for_agent(query, symbol, top_k=top_k, fiscal_year=fiscal_year)
    
    results = semantic_search(query, symbol=symbol, top_k=top_k)
    
    if not results:
        return ""
    
    context_parts = [f"📚 RELEVANT CONTEXT FOR {symbol}:\n"]
    
    for i, chunk in enumerate(results, 1):
        source = "Annual Report" if chunk['source_table'] == 'annual_reports' else "Earnings Call"
        period = chunk.get('quarter', '') + ' ' if chunk.get('quarter') else ''
        period += f"FY{chunk.get('fiscal_year', 'N/A')}"
        
        similarity_pct = chunk['similarity'] * 100
        
        context_parts.append(f"\n--- Source {i}: {source} ({period}) | Relevance: {similarity_pct:.0f}% ---")
        context_parts.append(chunk['chunk_preview'])
    
    return "\n".join(context_parts)


def search_across_market(query: str,
                         top_k: int = 10,
                         min_similarity: float = 0.5) -> List[Dict[str, Any]]:
    """
    Search across ALL stocks to find companies matching a thematic query.
    Routes to hybrid engine market-wide search when available.
    
    Args:
        query: Thematic search query
        top_k: Number of results per stock
        min_similarity: Minimum similarity threshold
        
    Returns:
        List of matching chunks grouped by symbol
    """
    # Route to hybrid engine if available
    if HYBRID_AVAILABLE:
        return _market_search(query, top_k=top_k, min_score=min_similarity)
    
    query_embedding = get_embedding(query)
    if not query_embedding:
        return []
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        # Find top chunks across entire corpus, then aggregate by symbol
        cur.execute("""
            WITH ranked_chunks AS (
                SELECT 
                    symbol,
                    source_table,
                    fiscal_year,
                    quarter,
                    section_type,
                    LEFT(chunk_text, 500) as chunk_preview,
                    1 - (embedding <=> %s::vector) as similarity,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY embedding <=> %s::vector) as rn
                FROM document_chunks
                WHERE embedding IS NOT NULL
            )
            SELECT *
            FROM ranked_chunks
            WHERE similarity >= %s AND rn <= 3
            ORDER BY similarity DESC
            LIMIT %s
        """, (embedding_str, embedding_str, min_similarity, top_k * 3))
        
        results = cur.fetchall()
        
        # Group by symbol
        symbol_map = {}
        for r in results:
            sym = r['symbol']
            if sym not in symbol_map:
                symbol_map[sym] = {
                    'symbol': sym,
                    'max_similarity': r['similarity'],
                    'matches': []
                }
            symbol_map[sym]['matches'].append(dict(r))
        
        # Sort by max similarity and return
        return sorted(symbol_map.values(), key=lambda x: x['max_similarity'], reverse=True)
        
    except Exception as e:
        logger.error(f"Market-wide search failed: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_document_summary(symbol: str, 
                         fiscal_year: str,
                         source_type: str = 'annual_reports') -> Optional[str]:
    """
    Get the AI-generated nuanced summary for a specific document.
    
    Args:
        symbol: Stock symbol
        fiscal_year: Fiscal year
        source_type: 'annual_reports' or 'concalls'
        
    Returns:
        The nuanced_summary if available
    """
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        table = 'annual_reports' if source_type == 'annual_reports' else 'concalls'
        cur.execute(f"""
            SELECT nuanced_summary 
            FROM {table}
            WHERE symbol = %s AND fiscal_year = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (symbol, fiscal_year))
        
        result = cur.fetchone()
        return result['nuanced_summary'] if result else None
        
    except Exception as e:
        logger.error(f"Failed to get summary: {e}")
        return None
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    # Test semantic search
    print("Testing semantic search...")
    
    results = semantic_search(
        query="revenue growth and profitability",
        symbol="RELIANCE",
        top_k=3
    )
    
    if results:
        print(f"\nFound {len(results)} results:")
        for r in results:
            print(f"  - {r['source_table']} FY{r['fiscal_year']}: {r['similarity']:.2%} similarity")
            print(f"    Section: {r['section_type']}")
            print(f"    Preview: {r['chunk_preview'][:100]}...")
    else:
        print("No results found. Make sure embeddings have been generated.")
    
    # Test market-wide search
    print("\n" + "="*50)
    print("Testing market-wide thematic search...")
    
    market_results = search_across_market(
        query="artificial intelligence investments",
        top_k=5
    )
    
    if market_results:
        print(f"\nFound {len(market_results)} companies mentioning AI:")
        for r in market_results:
            print(f"  {r['symbol']}: {r['max_similarity']:.2%} relevance")
    else:
        print("No market-wide results. Run embeddings first.")
