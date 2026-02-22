"""
Hybrid RAG Search Engine — AI Native Supreme Hedge Fund
7-Layer Architecture: HyDE + PageIndex + Vector + BM25 + RRF + Reranker + Metadata

Designed for 11,000-agent swarm with sub-second financial document retrieval.
- HyDE: Hypothetical document generation for semantic bridge
- PageIndex: Structure-aware, reasoning-based retrieval
- Vector + BM25: Dense + sparse hybrid search
"""

import os
import json
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HybridRAG")

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Lazy-loaded clients
_reranker = None
_reranker_load_attempted = False
_openai_client = None


def _get_db_connection():
    """Get database connection with SSL."""
    url = DATABASE_URL
    return psycopg2.connect(url, sslmode='require', connect_timeout=15)


def _get_openai_client():
    """Lazy-load OpenAI client for HyDE."""
    global _openai_client
    if _openai_client is None and OPENAI_API_KEY:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


# ============================================================
# LAYER -1: HyDE (Hypothetical Document Embeddings)
# ============================================================

HYDE_SYSTEM_PROMPT = """You are a financial document expert specializing in Indian capital markets.
Given a search query, generate a realistic passage that would appear in an Indian company's
annual report, earnings call transcript, or BSE filing that directly answers the query.

Rules:
- Write 150-250 words as if excerpted from an actual financial document
- Use specific Indian financial terminology (Rs/₹, crores, lakhs, SEBI, Ind AS, etc.)
- Include realistic but hypothetical numbers, ratios, and metrics
- Match the tone of the likely source (formal for annual reports, conversational for concalls)
- Do NOT add disclaimers or meta-commentary — just the passage itself"""


def hyde_generate(query: str, doc_type: Optional[str] = None) -> Optional[str]:
    """
    Generate a hypothetical document passage that would answer the query.
    Uses GPT-4o-mini for speed and cost efficiency (~$0.001/query).
    
    This is the core of HyDE — by embedding a hypothetical *answer* instead of
    the *question*, we bridge the vocabulary gap between how analysts ask
    questions and how companies write documents.
    """
    client = _get_openai_client()
    if not client:
        return None
    
    try:
        # Customize prompt based on expected document type
        user_prompt = f"Search query: {query}"
        if doc_type == 'annual_report':
            user_prompt += "\n\nGenerate a passage from an annual report."
        elif doc_type == 'concall':
            user_prompt += "\n\nGenerate a passage from an earnings call transcript, including speaker attribution."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": HYDE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=400,
            temperature=0.7,
        )
        
        passage = response.choices[0].message.content.strip()
        logger.debug(f"HyDE generated {len(passage)} char passage for: {query[:60]}")
        return passage
        
    except Exception as e:
        logger.warning(f"HyDE generation failed: {e}")
        return None


def hyde_search(query: str,
                symbol: Optional[str] = None,
                fiscal_year: Optional[str] = None,
                section_type: Optional[str] = None,
                doc_type: Optional[str] = None,
                top_k: int = 20) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    HyDE search — generates a hypothetical document passage, embeds it,
    and uses that embedding for vector search.
    
    Returns (results, hyde_passage) tuple.
    The hyde_passage is returned for transparency/debugging.
    """
    from api.database.embeddings import get_embedding
    
    # Step 1: Generate hypothetical passage
    hyde_passage = hyde_generate(query, doc_type=doc_type)
    if not hyde_passage:
        return [], None
    
    # Step 2: Embed the hypothetical passage (NOT the query)
    hyde_embedding = get_embedding(hyde_passage)
    if not hyde_embedding:
        return [], hyde_passage
    
    # Step 3: Use the hypothetical embedding for vector search
    results = vector_search(
        query_embedding=hyde_embedding,
        symbol=symbol,
        fiscal_year=fiscal_year,
        section_type=section_type,
        doc_type=doc_type,
        top_k=top_k
    )
    
    # Tag results with HyDE metadata
    for r in results:
        r['search_method'] = 'hyde'
    
    return results, hyde_passage


# ============================================================
# LAYER 0: PageIndex Tree Search (Structure-Aware Retrieval)
# ============================================================

def pageindex_search(query: str,
                     symbol: Optional[str] = None,
                     fiscal_year: Optional[str] = None,
                     section_type: Optional[str] = None,
                     doc_type: Optional[str] = None,
                     top_k: int = 20) -> List[Dict[str, Any]]:
    """
    PageIndex tree search — retrieves chunks by navigating the hierarchical
    document structure (like an intelligent TOC).

    How it works:
    1. Finds relevant PageIndex trees for the query filters
    2. Searches tree node summaries for keyword matches
    3. Returns chunk_ids from matching nodes, preserving page-level precision

    This is the "reasoning path" — excels at structural queries like:
    - "What did the chairman say about growth?"
    - "Find the balance sheet for FY2024"
    - "Show me the Q&A about debt reduction"
    """
    conn = _get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        conditions = []
        params = []

        if symbol:
            conditions.append("pit.symbol = %s")
            params.append(symbol)
        if fiscal_year:
            conditions.append("pit.fiscal_year = %s")
            params.append(fiscal_year)
        if doc_type:
            conditions.append("pit.doc_type = %s")
            params.append(doc_type)

        where = " AND ".join(conditions) if conditions else "1=1"

        # Fetch relevant trees
        cur.execute(f"""
            SELECT pit.source_table, pit.source_id, pit.symbol, pit.fiscal_year,
                   pit.doc_type, pit.tree_json
            FROM page_index_trees pit
            WHERE {where}
            ORDER BY pit.created_at DESC
            LIMIT 50
        """, params)

        trees = cur.fetchall()

        if not trees:
            return []

        # Extract query keywords for tree node matching
        query_lower = query.lower()
        query_words = set(query_lower.split())
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for',
                      'of', 'with', 'and', 'or', 'not', 'what', 'how', 'show', 'find', 'me', 'from'}
        query_keywords = query_words - stop_words

        # Search through tree nodes
        matching_chunk_ids = []

        for tree_row in trees:
            tree = tree_row['tree_json'] if isinstance(tree_row['tree_json'], dict) else json.loads(tree_row['tree_json'])
            source_table = tree_row['source_table']
            source_id = tree_row['source_id']

            nodes = tree.get('nodes', [])
            for node in nodes:
                score = _score_tree_node(node, query_keywords, query_lower, section_type)
                if score > 0:
                    for chunk_id in node.get('chunk_ids', []):
                        matching_chunk_ids.append({
                            'source_table': source_table,
                            'source_id': source_id,
                            'chunk_index': chunk_id,
                            'tree_score': score,
                            'tree_node_title': node.get('title', ''),
                            'tree_pages': f"{node.get('start_page', '?')}-{node.get('end_page', '?')}",
                        })

                # Also search children
                for child in node.get('children', []):
                    child_score = _score_tree_node(child, query_keywords, query_lower, section_type)
                    if child_score > 0:
                        for chunk_id in child.get('chunk_ids', []):
                            matching_chunk_ids.append({
                                'source_table': source_table,
                                'source_id': source_id,
                                'chunk_index': chunk_id,
                                'tree_score': child_score,
                                'tree_node_title': child.get('title', ''),
                                'tree_pages': f"{child.get('start_page', '?')}-{child.get('end_page', '?')}",
                            })

        if not matching_chunk_ids:
            return []

        # Sort by tree score and deduplicate
        matching_chunk_ids.sort(key=lambda x: x['tree_score'], reverse=True)

        # Fetch the actual chunks
        results = []
        seen = set()
        for match in matching_chunk_ids[:top_k * 2]:
            key = (match['source_table'], match['source_id'], match['chunk_index'])
            if key in seen:
                continue
            seen.add(key)

            cur.execute("""
                SELECT id, source_table, source_id, symbol, fiscal_year,
                       quarter, chunk_index, section_type, doc_type,
                       LEFT(chunk_text, 1500) as chunk_text,
                       context_prefix, page_start, page_end
                FROM document_chunks
                WHERE source_table = %s AND source_id = %s AND chunk_index = %s
            """, (match['source_table'], match['source_id'], match['chunk_index']))

            row = cur.fetchone()
            if row:
                result = dict(row)
                result['score'] = match['tree_score']
                result['search_method'] = 'pageindex'
                result['tree_node'] = match['tree_node_title']
                result['tree_pages'] = match['tree_pages']
                results.append(result)

            if len(results) >= top_k:
                break

        return results

    finally:
        cur.close()
        conn.close()


def _score_tree_node(node: Dict, query_keywords: set, query_lower: str,
                     section_filter: Optional[str] = None) -> float:
    """Score a PageIndex tree node against query keywords."""
    score = 0.0

    title = (node.get('title', '') or '').lower()
    summary = (node.get('summary', '') or '').lower()
    node_section = node.get('section_type', '')

    # Section type filter match (strongest signal)
    if section_filter and node_section == section_filter:
        score += 3.0

    # Keyword matches in title (strong signal)
    for kw in query_keywords:
        if kw in title:
            score += 2.0
        if kw in summary:
            score += 0.5

    # Section type relevance (medium signal)
    if node_section:
        section_words = set(node_section.replace('_', ' ').split())
        overlap = query_keywords & section_words
        score += len(overlap) * 1.0

    return score


# ============================================================
# LAYER 1: Vector Search (Semantic Similarity)
# ============================================================

def vector_search(query_embedding: List[float],
                  symbol: Optional[str] = None,
                  fiscal_year: Optional[str] = None,
                  section_type: Optional[str] = None,
                  doc_type: Optional[str] = None,
                  top_k: int = 20) -> List[Dict[str, Any]]:
    """
    Dense vector search using pgvector cosine distance.
    Returns chunks ranked by semantic similarity.
    """
    conn = _get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        conditions = ["embedding IS NOT NULL"]
        params = []
        
        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol)
        if fiscal_year:
            conditions.append("fiscal_year = %s")
            params.append(fiscal_year)
        if section_type:
            conditions.append("section_type = %s")
            params.append(section_type)
        if doc_type:
            conditions.append("doc_type = %s")
            params.append(doc_type)
        
        where = " AND ".join(conditions)
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        cur.execute(f"""
            SELECT 
                id, source_table, source_id, symbol, fiscal_year,
                quarter, chunk_index, section_type, doc_type,
                LEFT(chunk_text, 1500) as chunk_text,
                context_prefix,
                1 - (embedding <=> %s::vector) as score
            FROM document_chunks
            WHERE {where}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, [embedding_str] + params + [embedding_str, top_k])
        
        results = [dict(r) for r in cur.fetchall()]
        for r in results:
            r['search_method'] = 'vector'
        return results
        
    finally:
        cur.close()
        conn.close()


# ============================================================
# LAYER 2: BM25 Keyword Search (Exact Term Matching)
# ============================================================

def bm25_search(query: str,
                symbol: Optional[str] = None,
                fiscal_year: Optional[str] = None,
                section_type: Optional[str] = None,
                doc_type: Optional[str] = None,
                top_k: int = 20) -> List[Dict[str, Any]]:
    """
    BM25 keyword search using PostgreSQL's tsvector/tsquery.
    Excels at exact term matching (company names, financial ratios, years).
    """
    conn = _get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        conditions = ["search_vector IS NOT NULL"]
        params = []
        
        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol)
        if fiscal_year:
            conditions.append("fiscal_year = %s")
            params.append(fiscal_year)
        if section_type:
            conditions.append("section_type = %s")
            params.append(section_type)
        if doc_type:
            conditions.append("doc_type = %s")
            params.append(doc_type)
        
        where = " AND ".join(conditions)
        
        # Use plainto_tsquery for natural language, websearch_tsquery for advanced
        cur.execute(f"""
            SELECT 
                id, source_table, source_id, symbol, fiscal_year,
                quarter, chunk_index, section_type, doc_type,
                LEFT(chunk_text, 1500) as chunk_text,
                context_prefix,
                ts_rank_cd(search_vector, query, 32) as score
            FROM document_chunks,
                 plainto_tsquery('english', %s) query
            WHERE {where}
              AND search_vector @@ query
            ORDER BY ts_rank_cd(search_vector, query, 32) DESC
            LIMIT %s
        """, [query] + params + [top_k])
        
        results = [dict(r) for r in cur.fetchall()]
        for r in results:
            r['search_method'] = 'bm25'
        return results
        
    finally:
        cur.close()
        conn.close()


# ============================================================
# LAYER 3: Reciprocal Rank Fusion (RRF)
# ============================================================

def reciprocal_rank_fusion(result_lists: List[List[Dict]], 
                            k: int = 60,
                            weights: Optional[List[float]] = None) -> List[Dict]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion.
    
    RRF formula: score(d) = Σ (w_i / (k + rank_i(d)))
    
    This is the standard fusion method used in production hybrid search systems.
    k=60 is the standard constant (from the original RRF paper).
    """
    if weights is None:
        weights = [1.0] * len(result_lists)
    
    # Normalize weights
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]
    
    # Score each document
    doc_scores = defaultdict(lambda: {
        'rrf_score': 0.0,
        'sources': [],
        'data': None
    })
    
    for list_idx, results in enumerate(result_lists):
        for rank, doc in enumerate(results):
            doc_id = doc['id']
            rrf_contribution = weights[list_idx] / (k + rank + 1)
            doc_scores[doc_id]['rrf_score'] += rrf_contribution
            doc_scores[doc_id]['sources'].append(doc.get('search_method', f'list_{list_idx}'))
            if doc_scores[doc_id]['data'] is None:
                doc_scores[doc_id]['data'] = doc
    
    # Sort by RRF score
    ranked = sorted(doc_scores.items(), key=lambda x: x[1]['rrf_score'], reverse=True)
    
    results = []
    for doc_id, info in ranked:
        doc = info['data'].copy()
        doc['rrf_score'] = info['rrf_score']
        doc['original_score'] = doc.pop('score', 0)
        doc['search_methods'] = list(set(info['sources']))
        results.append(doc)
    
    return results


# ============================================================
# LAYER 4: Cross-Encoder Reranking
# ============================================================

def _load_reranker():
    """Lazy-load BGE-Reranker-v2 (free, self-hosted via sentence-transformers)."""
    global _reranker, _reranker_load_attempted
    
    if _reranker_load_attempted:
        return _reranker
    
    _reranker_load_attempted = True
    
    try:
        from sentence_transformers import CrossEncoder
        logger.info("Loading BGE-Reranker-v2-m3 (first load may take 30s)...")
        _reranker = CrossEncoder('BAAI/bge-reranker-v2-m3', max_length=512)
        logger.info("✅ Reranker loaded successfully")
    except ImportError:
        logger.warning("⚠️ sentence-transformers not installed. Reranking disabled.")
        logger.warning("   Install: pip install sentence-transformers")
    except Exception as e:
        logger.warning(f"⚠️ Reranker load failed: {e}")
    
    return _reranker


def rerank(query: str, 
           documents: List[Dict], 
           top_k: int = 10) -> List[Dict]:
    """
    Rerank documents using a cross-encoder model.
    Falls back to original ranking if reranker is unavailable.
    """
    if not documents:
        return documents
    
    reranker = _load_reranker()
    
    if reranker is None:
        # No reranker available — return top-k by existing score
        return documents[:top_k]
    
    try:
        # Prepare query-document pairs
        pairs = []
        for doc in documents:
            text = doc.get('chunk_text', '')[:512]  # CrossEncoder max length
            pairs.append([query, text])
        
        # Score all pairs
        scores = reranker.predict(pairs)
        
        # Attach scores and sort
        for i, doc in enumerate(documents):
            doc['rerank_score'] = float(scores[i])
        
        documents.sort(key=lambda x: x['rerank_score'], reverse=True)
        return documents[:top_k]
        
    except Exception as e:
        logger.warning(f"Reranking failed: {e}")
        return documents[:top_k]


# ============================================================
# LAYER 5: Main Hybrid Search API
# ============================================================

def hybrid_search(query: str,
                  symbol: Optional[str] = None,
                  fiscal_year: Optional[str] = None,
                  section_type: Optional[str] = None,
                  doc_type: Optional[str] = None,
                  top_k: int = 10,
                  use_reranker: bool = True,
                  use_hyde: bool = True,
                  use_raptor: bool = True,
                  vector_weight: float = 0.30,
                  bm25_weight: float = 0.20,
                  hyde_weight: float = 0.25,
                  pageindex_weight: float = 0.10,
                  raptor_weight: float = 0.15) -> List[Dict[str, Any]]:
    """
    8-Layer Hybrid Search for the AI Native Supreme Hedge Fund.
    
    Pipeline:
        -1. HyDE: Generate hypothetical document, embed it, vector search
        0.  RAPTOR: Multi-scale search across L1/L2 summaries  
        1.  PageIndex tree search (structure-aware, reasoning-based)
        2.  Metadata pre-filtering (symbol, year, section)
        3.  Parallel: Vector search + BM25 search
        4.  Reciprocal Rank Fusion (merge up to 5 result sets)
        5.  Cross-encoder reranking (optional)
        6.  Return top-k results
    
    Args:
        query: Natural language search query
        symbol: Filter by stock symbol (e.g., 'DLF')
        fiscal_year: Filter by fiscal year (e.g., '2025')
        section_type: Filter by section ('mda', 'corporate_governance', etc.)
        doc_type: Filter by doc type ('annual_report', 'concall')
        top_k: Number of results
        use_reranker: Whether to apply cross-encoder reranking
        use_hyde: Whether to use HyDE (hypothetical document embeddings)
        use_raptor: Whether to search RAPTOR multi-scale summaries
        vector_weight: Weight for vector search in RRF (default 0.30)
        bm25_weight: Weight for BM25 in RRF (default 0.20)
        hyde_weight: Weight for HyDE in RRF (default 0.25)
        pageindex_weight: Weight for PageIndex in RRF (default 0.10)
        raptor_weight: Weight for RAPTOR in RRF (default 0.15)
    
    Returns:
        List of ranked document chunks with scores and metadata
    """
    from api.database.embeddings import get_embedding
    
    start = time.time()
    hyde_passage = None
    
    # Generate query embedding
    query_embedding = get_embedding(query)
    if not query_embedding:
        logger.error("Failed to generate query embedding")
        return []
    
    embed_time = time.time() - start
    
    # LAYER -1: HyDE (hypothetical document embeddings)
    retrieve_start = time.time()
    hyde_results = []
    
    if use_hyde:
        hyde_results, hyde_passage = hyde_search(
            query, symbol=symbol, fiscal_year=fiscal_year,
            section_type=section_type, doc_type=doc_type,
            top_k=top_k * 3
        )
    
    hyde_time = time.time() - retrieve_start
    
    # LAYER 0: RAPTOR multi-scale search (L1 section + L2 document summaries)
    raptor_results = []
    if use_raptor:
        try:
            from api.database.raptor import raptor_search as _raptor_search
            raptor_results = _raptor_search(
                query_embedding=query_embedding,
                symbol=symbol,
                fiscal_year=fiscal_year,
                doc_type=doc_type,
                top_k=top_k * 2
            )
        except Exception as e:
            logger.debug(f"RAPTOR search skipped: {e}")
    
    # LAYER 1: PageIndex tree search (structure-aware)
    filter_kwargs = {
        'symbol': symbol,
        'fiscal_year': fiscal_year,
        'section_type': section_type,
        'doc_type': doc_type,
        'top_k': top_k * 3,  # Over-fetch for fusion
    }
    
    pageindex_results = pageindex_search(query, **filter_kwargs)
    
    # LAYER 2+3: Parallel retrieval (vector + BM25)
    vec_results = vector_search(query_embedding, **filter_kwargs)
    bm25_results = bm25_search(query, **filter_kwargs)
    
    retrieve_time = time.time() - retrieve_start
    
    # LAYER 4: Reciprocal Rank Fusion (up to 5-way)
    result_lists = [vec_results, bm25_results]
    weights = [vector_weight, bm25_weight]
    
    if hyde_results:
        result_lists.append(hyde_results)
        weights.append(hyde_weight)
    
    if pageindex_results:
        result_lists.append(pageindex_results)
        weights.append(pageindex_weight)
    
    if raptor_results:
        result_lists.append(raptor_results)
        weights.append(raptor_weight)
    
    fused = reciprocal_rank_fusion(result_lists, weights=weights)
    
    # LAYER 5: Cross-encoder reranking
    if use_reranker and len(fused) > top_k:
        rerank_start = time.time()
        final_results = rerank(query, fused, top_k=top_k)
        rerank_time = time.time() - rerank_start
    else:
        final_results = fused[:top_k]
        rerank_time = 0
    
    # Attach metadata for transparency
    if hyde_passage:
        for r in final_results:
            r['hyde_passage'] = hyde_passage[:200]
    
    total_time = time.time() - start
    
    # Log performance
    logger.info(
        f"Hybrid search: {len(final_results)} results in {total_time:.2f}s "
        f"(embed: {embed_time:.2f}s, hyde: {hyde_time:.2f}s, "
        f"retrieve: {retrieve_time:.2f}s, rerank: {rerank_time:.2f}s) | "
        f"hyde: {len(hyde_results)}, raptor: {len(raptor_results)}, "
        f"pageindex: {len(pageindex_results)}, vec: {len(vec_results)}, "
        f"bm25: {len(bm25_results)}, fused: {len(fused)}"
    )
    
    return final_results


def get_context_for_agent(query: str,
                          symbol: str,
                          top_k: int = 5,
                          fiscal_year: Optional[str] = None) -> str:
    """
    Build RAG context string for agent swarm consumption.
    Each agent in the 11,000-agent swarm can call this for document retrieval.
    
    Returns formatted context ready for LLM prompt injection.
    """
    results = hybrid_search(
        query=query,
        symbol=symbol,
        fiscal_year=fiscal_year,
        top_k=top_k,
        use_reranker=True
    )
    
    if not results:
        return f"No relevant documents found for {symbol}."
    
    context_parts = [f"📚 RAG CONTEXT FOR {symbol} ({len(results)} sources):\n"]
    
    for i, chunk in enumerate(results, 1):
        source = "Annual Report" if chunk.get('source_table') == 'annual_reports' else "Earnings Call"
        year = chunk.get('fiscal_year', '?')
        section = chunk.get('section_type', 'general')
        methods = ', '.join(chunk.get('search_methods', ['unknown']))
        
        # Show which retrieval methods found this chunk
        score_info = f"RRF: {chunk.get('rrf_score', 0):.4f}"
        if 'rerank_score' in chunk:
            score_info += f" | Rerank: {chunk['rerank_score']:.3f}"
        
        context_parts.append(
            f"\n{'─' * 60}\n"
            f"📄 Source {i}: {source} FY{year} | Section: {section}\n"
            f"   Found via: [{methods}] | {score_info}\n"
            f"{'─' * 60}"
        )
        context_parts.append(chunk.get('chunk_text', '')[:1500])
    
    return "\n".join(context_parts)


def search_across_market(query: str,
                         top_k: int = 10,
                         min_score: float = 0.3) -> List[Dict]:
    """
    Thematic search across ALL stocks — for custom index generation.
    
    Example: "companies investing in AI infrastructure" → finds relevant stocks
    """
    results = hybrid_search(
        query=query,
        top_k=top_k * 5,
        use_reranker=False  # Skip reranker for speed on market-wide search
    )
    
    # Group by symbol, keep best match per stock
    symbol_map = {}
    for r in results:
        sym = r['symbol']
        if sym not in symbol_map or r.get('rrf_score', 0) > symbol_map[sym].get('rrf_score', 0):
            symbol_map[sym] = r
    
    # Sort by score and return top-k symbols
    ranked = sorted(symbol_map.values(), key=lambda x: x.get('rrf_score', 0), reverse=True)
    return ranked[:top_k]


# ============================================================
# CLI Testing
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🔍 HYBRID RAG SEARCH ENGINE — TEST SUITE")
    print("   AI Native Supreme Hedge Fund | 11,000 Agent Swarm")
    print("=" * 60)
    
    # Test 1: Single stock search  
    print("\n📊 Test 1: DLF governance search (hybrid)")
    results = hybrid_search(
        query="corporate governance board composition independent directors",
        symbol="DLF",
        top_k=3,
        use_reranker=False  # Skip reranker for speed in test
    )
    if results:
        for r in results:
            print(f"  [{', '.join(r.get('search_methods', []))}] "
                  f"FY{r.get('fiscal_year', '?')} | {r.get('section_type', '?')} | "
                  f"RRF: {r.get('rrf_score', 0):.4f}")
    else:
        print("  No results — stock may not be embedded yet")
    
    # Test 2: BM25 exact term search
    print("\n📊 Test 2: BM25 keyword search (debt-to-equity)")
    bm25_results = bm25_search(
        query="debt equity ratio leverage",
        top_k=5
    )
    if bm25_results:
        for r in bm25_results:
            print(f"  {r['symbol']} FY{r.get('fiscal_year', '?')} | "
                  f"Section: {r.get('section_type', '?')} | Score: {r['score']:.4f}")
    else:
        print("  No BM25 results — search_vector may not be populated yet")
    
    # Test 3: Market-wide thematic search
    print("\n📊 Test 3: Market-wide search (AI investments)")
    market_results = search_across_market(
        query="artificial intelligence machine learning investments",
        top_k=5
    )
    if market_results:
        for r in market_results:
            print(f"  {r['symbol']} | RRF: {r.get('rrf_score', 0):.4f}")
    else:
        print("  No results — embeddings may need to be generated")
    
    # Test 4: Agent context generation
    print("\n📊 Test 4: Agent context generation")
    context = get_context_for_agent(
        query="revenue growth profitability margins",
        symbol="DALBHARAT",
        top_k=2
    )
    print(f"  Context length: {len(context)} chars")
    print(f"  Preview: {context[:200]}...")
    
    print("\n" + "=" * 60)
    print("✅ Test suite complete")
