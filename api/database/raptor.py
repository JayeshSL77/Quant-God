"""
RAPTOR — Recursive Abstractive Processing for Tree-Organized Retrieval
AI Native Supreme Hedge Fund — 11,000 Agent Swarm

RAPTOR creates multi-scale document representations:
- L0: Raw chunks (already exist in document_chunks)
- L1: Section-level summaries (~5-10 chunks each) 
- L2: Document-level summary (entire document)

This enables "zoom in/zoom out" retrieval:
- Specific question → hits L0 chunk directly
- Section question → hits L1 summary, then drills into L0 chunks
- Big picture question → hits L2 doc summary, then L1 sections

Uses GPT-4o-mini for cost-efficient summarization (~$0.02/doc).
"""

import os
import sys
import json
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from openai import OpenAI, AsyncOpenAI

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAPTOR")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")

_openai_client = None
_async_openai_client = None

def _get_openai():
    global _openai_client
    if _openai_client is None and OPENAI_API_KEY:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client

def _get_async_openai():
    global _async_openai_client
    if _async_openai_client is None and OPENAI_API_KEY:
        _async_openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _async_openai_client


@dataclass
class RaptorNode:
    """A node in the RAPTOR tree."""
    node_id: str
    level: int  # 0=chunk, 1=section summary, 2=doc summary
    title: str
    summary: str
    section_type: str
    chunk_ids: List[int] = field(default_factory=list)  # L0 chunk IDs covered
    children: List[str] = field(default_factory=list)  # child node IDs
    page_start: int = 0
    page_end: int = 0
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        d.pop('embedding', None)  # Don't include embedding in JSON
        return d


# ============================================================
# SUMMARIZATION PROMPTS
# ============================================================

L1_SYSTEM_PROMPT = """You are a financial analyst summarizing sections of Indian company documents.
Given multiple text chunks from the same section, create a concise summary that:
- Captures ALL key financial metrics, ratios, and figures
- Preserves specific numbers (₹ amounts, percentages, ratios)
- Notes management commentary, guidance, and forward-looking statements  
- Retains analyst names and key Q&A points (for concalls)
- Uses 150-300 words
- Writes in third person past tense
Do NOT add opinions or analysis — just faithful summarization."""

L2_SYSTEM_PROMPT = """You are a financial analyst creating an executive summary of an Indian company's document.
Given section-level summaries of the entire document, create a comprehensive executive overview that:
- Captures the company's overall financial health and performance
- Highlights key metrics: revenue, profit, margins, growth rates
- Notes strategic priorities, risks, and governance highlights
- Covers all major sections proportionally
- Uses 300-500 words
- Writes in third person past tense
Do NOT add opinions — just faithful high-level summarization."""


class RaptorBuilder:
    """
    Build RAPTOR trees from document chunks.
    
    Flow:
    1. Group chunks by section_type → create L1 summaries
    2. Combine L1 summaries → create L2 document summary
    3. Embed all summaries
    4. Store in raptor_summaries table
    """

    def __init__(self, batch_size: int = 10):
        self.client = _get_openai()
        self.batch_size = batch_size

    async def _summarize_async(self, text: str, system_prompt: str, 
                               doc_context: str = "") -> Optional[str]:
        """Generate summary asynchronously using GPT-4o-mini."""
        client = _get_async_openai()
        if not client:
            return None

        try:
            # Construct prompt
            user_msg = f"{doc_context}\n\nTEXT TO SUMMARIZE:\n{text[:25000]}"
            
            # Retry logic for rate limits
            for attempt in range(3):
                try:
                    response = await client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_msg}
                        ],
                        max_tokens=600,
                        temperature=0.3,
                    )
                    return response.choices[0].message.content.strip()
                except Exception as e:
                    if "429" in str(e) and attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise e
            return None

        except Exception as e:
            logger.warning(f"RAPTOR async summary failed: {e}")
            return None

    def _summarize(self, chunks_text: str, system_prompt: str, 
                   doc_context: str = "") -> Optional[str]:
        """Generate summary synchronously (fallback/L2)."""
        client = _get_openai()
        if not client:
            return None

        try:
            user_msg = doc_context + "\n\n" + chunks_text if doc_context else chunks_text
            user_msg = user_msg[:28000]

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=600,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"RAPTOR summarization failed: {e}")
            return None

    def build_for_document(self, source_table: str, source_id: int,
                           symbol: str, fiscal_year: str,
                           doc_type: str, conn) -> Dict:
        """
        Build RAPTOR tree for a single document.
        
        Args:
            source_table: 'annual_reports' or 'concalls'
            source_id: Document ID
            symbol: Stock symbol
            fiscal_year: FY year
            doc_type: 'annual_report' or 'concall'
            conn: Database connection
            
        Returns:
            Dict with tree structure and stats
        """
        from api.database.embeddings import get_embedding, get_embeddings_batch

        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch all L0 chunks for this document
        cur.execute("""
            SELECT chunk_index, chunk_text, section_type, page_start, page_end
            FROM document_chunks
            WHERE source_table = %s AND source_id = %s
            ORDER BY chunk_index
        """, (source_table, source_id))

        chunks = [dict(r) for r in cur.fetchall()]

        if not chunks:
            cur.close()
            return {'nodes': [], 'l1_count': 0, 'l2_count': 0}

        doc_context = f"Document: {symbol} {doc_type.replace('_', ' ').title()} FY{fiscal_year}"

        # ── LEVEL 1: Section summaries (PARALLEL ASYNC) ──
        # Group chunks by section_type
        section_groups = {}
        for chunk in chunks:
            st = chunk['section_type'] or 'unknown'
            if st not in section_groups:
                section_groups[st] = []
            section_groups[st].append(chunk)

        async def process_l1_nodes():
            tasks = []
            meta_list = []  # To keep track of which section corresponds to which task

            for section_type, section_chunks in section_groups.items():
                if len(section_chunks) < 2:
                    continue

                combined_text = "\n\n---\n\n".join([
                    f"[Chunk {c['chunk_index']}, pages {c['page_start']}-{c['page_end']}]\n{c['chunk_text'][:2000]}"
                    for c in section_chunks
                ])
                
                tasks.append(self._summarize_async(combined_text, L1_SYSTEM_PROMPT, doc_context))
                meta_list.append((section_type, section_chunks))
            
            if not tasks:
                return []
            
            results = await asyncio.gather(*tasks)
            nodes = []
            node_counter = 0
            
            for summary, (section_type, section_chunks) in zip(results, meta_list):
                if not summary:
                    continue
                    
                node_id = f"L1_{node_counter:04d}"
                node_counter += 1
                
                nodes.append(RaptorNode(
                    node_id=node_id,
                    level=1,
                    title=section_type.replace('_', ' ').title(),
                    summary=summary,
                    section_type=section_type,
                    chunk_ids=[c['chunk_index'] for c in section_chunks],
                    page_start=min(c['page_start'] for c in section_chunks),
                    page_end=max(c['page_end'] for c in section_chunks),
                ))
            return nodes

        # Run async L1 generation
        try:
            l1_nodes = asyncio.run(process_l1_nodes())
        except Exception as e:
            logger.error(f"Async L1 generation failed: {e}")
            l1_nodes = []

        # ── LEVEL 2: Document summary (SYNC) ──
        l2_node = None

        if l1_nodes:
            l1_combined = "\n\n---\n\n".join([
                f"[{n.title} | pages {n.page_start}-{n.page_end}]\n{n.summary}"
                for n in l1_nodes
            ])

            doc_summary = self._summarize(l1_combined, L2_SYSTEM_PROMPT, doc_context)
            if doc_summary:
                l2_node = RaptorNode(
                    node_id="L2_0000",
                    level=2,
                    title=f"{symbol} FY{fiscal_year} Executive Summary",
                    summary=doc_summary,
                    section_type="executive_summary",
                    chunk_ids=[c['chunk_index'] for c in chunks],
                    children=[n.node_id for n in l1_nodes],
                    page_start=min(c['page_start'] for c in chunks),
                    page_end=max(c['page_end'] for c in chunks),
                )

        # ── EMBED ALL RAPTOR SUMMARIES ──
        all_nodes = l1_nodes + ([l2_node] if l2_node else [])
        if all_nodes:
            texts_to_embed = [
                f"{doc_context}. {n.title}. {n.summary}" 
                for n in all_nodes
            ]
            embeddings = get_embeddings_batch(texts_to_embed, batch_size=self.batch_size)

            for node, emb in zip(all_nodes, embeddings):
                node.embedding = emb

        # ── STORE IN DB ──
        for node in all_nodes:
            if not node.embedding:
                continue
            try:
                cur.execute("""
                    INSERT INTO raptor_summaries
                    (source_table, source_id, symbol, fiscal_year, doc_type,
                     node_id, level, title, summary, section_type,
                     chunk_ids, children, page_start, page_end, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_table, source_id, node_id) DO UPDATE SET
                        summary = EXCLUDED.summary,
                        embedding = EXCLUDED.embedding,
                        chunk_ids = EXCLUDED.chunk_ids,
                        children = EXCLUDED.children
                """, (
                    source_table, source_id, symbol, fiscal_year, doc_type,
                    node.node_id, node.level, node.title, node.summary,
                    node.section_type,
                    json.dumps(node.chunk_ids),
                    json.dumps(node.children),
                    node.page_start, node.page_end,
                    node.embedding,
                ))
            except Exception as e:
                logger.error(f"Failed to store RAPTOR node {node.node_id}: {e}")
                conn.rollback()

        conn.commit()
        cur.close()

        stats = {
            'l1_count': len(l1_nodes),
            'l2_count': 1 if l2_node else 0,
            'total_nodes': len(all_nodes),
            'sections_summarized': len(l1_nodes),
        }

        logger.info(
            f"RAPTOR built for {symbol} FY{fiscal_year}: "
            f"{stats['l1_count']} L1 + {stats['l2_count']} L2 summaries"
        )

        return stats


def ensure_raptor_schema(conn):
    """Create raptor_summaries table if it doesn't exist."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS raptor_summaries (
            id SERIAL PRIMARY KEY,
            source_table VARCHAR(50) NOT NULL,
            source_id INTEGER NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            fiscal_year VARCHAR(20),
            doc_type VARCHAR(30),
            node_id VARCHAR(20) NOT NULL,
            level INTEGER NOT NULL,  -- 1=section, 2=document
            title VARCHAR(200),
            summary TEXT NOT NULL,
            section_type VARCHAR(50),
            chunk_ids JSONB,
            children JSONB,
            page_start INTEGER DEFAULT 0,
            page_end INTEGER DEFAULT 0,
            embedding vector(3072),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_table, source_id, node_id)
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_raptor_symbol 
        ON raptor_summaries(symbol);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_raptor_level 
        ON raptor_summaries(level);
    """)
    # Note: pgvector indexes (IVFFlat/HNSW) don't support >2000 dimensions.
    # RAPTOR table is small (~50K rows max) so sequential scan is fast enough.
    # For the main document_chunks table, we also use sequential scan on 3072d.

    conn.commit()
    cur.close()
    logger.info("✅ raptor_summaries table ready")


# ============================================================
# RAPTOR SEARCH (for hybrid_search.py integration)
# ============================================================

def raptor_search(query_embedding: List[float],
                  symbol: Optional[str] = None,
                  fiscal_year: Optional[str] = None,
                  doc_type: Optional[str] = None,
                  level: Optional[int] = None,
                  top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Search RAPTOR summaries by vector similarity.
    
    Args:
        query_embedding: Query vector (3072d)
        symbol: Filter by stock symbol
        fiscal_year: Filter by FY
        doc_type: Filter by document type
        level: Filter by RAPTOR level (1=section, 2=document)
        top_k: Number of results
    """
    conn = psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=15)
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
        if doc_type:
            conditions.append("doc_type = %s")
            params.append(doc_type)
        if level:
            conditions.append("level = %s")
            params.append(level)

        where = " AND ".join(conditions)
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

        cur.execute(f"""
            SELECT 
                id, source_table, source_id, symbol, fiscal_year,
                node_id, level, title, summary, section_type,
                chunk_ids, page_start, page_end,
                1 - (embedding <=> %s::vector) as score
            FROM raptor_summaries
            WHERE {where}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, [embedding_str] + params + [embedding_str, top_k])

        results = []
        for row in cur.fetchall():
            r = dict(row)
            r['search_method'] = 'raptor'
            r['raptor_level'] = r['level']
            # Map RAPTOR summary to chunk_text for compatibility with RRF
            r['chunk_text'] = r['summary']
            results.append(r)

        return results

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    """Test RAPTOR on a single document."""
    print("=" * 60)
    print("RAPTOR TEST — Recursive Abstractive Tree-Organized Retrieval")
    print("=" * 60)

    conn = psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=15)
    ensure_raptor_schema(conn)

    # Find a document that has chunks
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT source_table, source_id, symbol, fiscal_year
        FROM document_chunks
        GROUP BY source_table, source_id, symbol, fiscal_year
        ORDER BY count(*) DESC
        LIMIT 1
    """)
    doc = cur.fetchone()
    cur.close()

    if doc:
        print(f"\nBuilding RAPTOR tree for {doc['symbol']} FY{doc['fiscal_year']}...")
        builder = RaptorBuilder()
        stats = builder.build_for_document(
            doc['source_table'], doc['source_id'],
            doc['symbol'], doc['fiscal_year'],
            'annual_report', conn
        )
        print(f"Results: {stats}")
    else:
        print("No chunked documents found. Run the batch processor first.")

    conn.close()
