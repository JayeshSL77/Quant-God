"""
Phase 1 RAG Batch Processor - Optimized for Rich Context
Processes documents one-by-one to avoid memory issues.
Extracts structured financial metrics for Generated Assets feature.
"""

import os
import sys
import time
import argparse
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

load_dotenv(override=True)

from api.database.chunking import SmartChunker
from api.database.embeddings import get_embedding

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'phase1_batch_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger("Phase1Batch")

DATABASE_URL = os.getenv("DATABASE_URL", 
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")


class OptimizedBatchProcessor:
    """
    Optimized batch processor that:
    1. Fetches documents one-by-one (memory efficient)
    2. Creates rich context chunks
    3. Extracts structured metrics (for Generated Assets)
    """
    
    def __init__(self, rate_limit: int = 500):
        self.conn = psycopg2.connect(DATABASE_URL)
        self.chunker = SmartChunker()
        self.rate_limit = rate_limit  # embeddings per minute
        self.last_call_time = 0
        
        # Stats
        self.stats = {
            "documents_processed": 0,
            "chunks_created": 0,
            "embeddings_generated": 0,
            "errors": 0,
            "start_time": time.time()
        }
    
    def _rate_limit(self):
        """Rate limit API calls."""
        min_interval = 60.0 / self.rate_limit
        elapsed = time.time() - self.last_call_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_call_time = time.time()
    
    def get_document_ids(self, source_table: str, limit: Optional[int] = None) -> List[int]:
        """Get IDs of documents needing processing (NOT full content)."""
        cur = self.conn.cursor()
        
        text_col = 'summary' if source_table == 'annual_reports' else 'transcript'
        
        query = f"""
            SELECT ar.id 
            FROM {source_table} ar
            WHERE {text_col} IS NOT NULL 
              AND LENGTH({text_col}) > 500
              AND ar.id NOT IN (
                  SELECT DISTINCT source_id 
                  FROM document_chunks 
                  WHERE source_table = '{source_table}'
              )
            ORDER BY ar.id DESC
        """
        if limit:
            query += f" LIMIT {limit}"
        
        cur.execute(query)
        ids = [row[0] for row in cur.fetchall()]
        cur.close()
        return ids
    
    def fetch_document(self, source_table: str, doc_id: int) -> Optional[Dict]:
        """Fetch a single document by ID."""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        
        if source_table == 'annual_reports':
            query = """
                SELECT id, symbol, fiscal_year, summary as content, 
                       LENGTH(summary) as content_length
                FROM annual_reports WHERE id = %s
            """
        else:
            query = """
                SELECT id, symbol, fiscal_year, quarter, transcript as content,
                       LENGTH(transcript) as content_length
                FROM concalls WHERE id = %s
            """
        
        cur.execute(query, (doc_id,))
        doc = cur.fetchone()
        cur.close()
        return dict(doc) if doc else None
    
    def process_document(self, doc: Dict, source_table: str) -> int:
        """Process a single document: chunk, embed, store."""
        chunks_created = 0
        
        content = doc.get('content', '')
        if not content or len(content) < 500:
            return 0
        
        # Create rich context prefix for each chunk
        context_prefix = f"Company: {doc['symbol']} | FY: {doc.get('fiscal_year', 'N/A')}"
        if source_table == 'concalls':
            context_prefix += f" | Quarter: {doc.get('quarter', 'N/A')}"
        
        # Chunk the document
        chunks = self.chunker.chunk_document(content)
        
        cur = self.conn.cursor()
        
        for chunk in chunks:
            try:
                # Add context prefix to chunk for richer embeddings
                enriched_text = f"{context_prefix}\n\n{chunk.chunk_text}"
                
                # Rate limit and generate embedding
                self._rate_limit()
                embedding = get_embedding(enriched_text[:8000])
                
                if not embedding:
                    logger.warning(f"No embedding for {doc['symbol']} chunk {chunk.chunk_index}")
                    continue
                
                # Store chunk with embedding
                cur.execute("""
                    INSERT INTO document_chunks 
                    (source_table, source_id, symbol, fiscal_year, quarter, 
                     chunk_index, chunk_text, section_type, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_table, source_id, chunk_index) 
                    DO UPDATE SET embedding = EXCLUDED.embedding,
                                  chunk_text = EXCLUDED.chunk_text
                """, (
                    source_table,
                    doc['id'],
                    doc['symbol'],
                    doc.get('fiscal_year'),
                    doc.get('quarter'),
                    chunk.chunk_index,
                    enriched_text,  # Store enriched text
                    chunk.section_type,
                    embedding
                ))
                
                chunks_created += 1
                self.stats["embeddings_generated"] += 1
                
            except Exception as e:
                logger.error(f"Error processing chunk {chunk.chunk_index}: {e}")
                self.stats["errors"] += 1
                continue
        
        self.conn.commit()
        cur.close()
        
        self.stats["chunks_created"] += chunks_created
        return chunks_created
    
    def run_pipeline(self, source_table: str, limit: Optional[int] = None):
        """Run the pipeline for a source table."""
        logger.info(f"Fetching document IDs from {source_table}...")
        doc_ids = self.get_document_ids(source_table, limit)
        total = len(doc_ids)
        logger.info(f"Found {total} documents to process")
        
        for i, doc_id in enumerate(doc_ids):
            try:
                # Fetch document
                doc = self.fetch_document(source_table, doc_id)
                if not doc:
                    continue
                
                # Process
                chunks = self.process_document(doc, source_table)
                self.stats["documents_processed"] += 1
                
                # Log progress every 10 documents
                if (i + 1) % 10 == 0:
                    elapsed = time.time() - self.stats["start_time"]
                    rate = self.stats["embeddings_generated"] / elapsed * 60
                    logger.info(
                        f"[{i+1}/{total}] {doc['symbol']} FY{doc.get('fiscal_year')} - "
                        f"{chunks} chunks | Total: {self.stats['chunks_created']} | "
                        f"Rate: {rate:.1f} emb/min"
                    )
                
            except Exception as e:
                logger.error(f"Error processing doc {doc_id}: {e}")
                self.stats["errors"] += 1
                continue
    
    def run(self, mode: str = 'all', limit: Optional[int] = None):
        """Main entry point."""
        logger.info("="*60)
        logger.info("PHASE 1 BATCH PROCESSOR - OPTIMIZED")
        logger.info(f"Mode: {mode} | Limit: {limit or 'Unlimited'}")
        logger.info("="*60)
        
        # Ensure table exists
        cur = self.conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        self.conn.commit()
        cur.close()
        logger.info("✅ pgvector ready")
        
        if mode in ['all', 'embeddings', 'test']:
            # Process Annual Reports first (highest value)
            logger.info("\n📊 PROCESSING ANNUAL REPORTS")
            self.run_pipeline('annual_reports', limit)
            
            # Then Concalls
            logger.info("\n📞 PROCESSING CONCALLS")
            self.run_pipeline('concalls', limit)
        
        # Final stats
        elapsed = time.time() - self.stats["start_time"]
        logger.info("\n" + "="*60)
        logger.info("BATCH PROCESSING COMPLETE")
        logger.info(f"Documents: {self.stats['documents_processed']}")
        logger.info(f"Chunks: {self.stats['chunks_created']}")
        logger.info(f"Embeddings: {self.stats['embeddings_generated']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Time: {elapsed/60:.1f} minutes")
        logger.info(f"Rate: {self.stats['embeddings_generated']/elapsed*60:.1f} emb/min")
        logger.info("="*60)


def main():
    parser = argparse.ArgumentParser(description='Phase 1 RAG Batch Processor')
    parser.add_argument('--mode', choices=['all', 'embeddings', 'test'], default='all')
    parser.add_argument('--limit', type=int, help='Limit documents to process')
    args = parser.parse_args()
    
    if args.mode == 'test':
        args.limit = 3
        logger.info("🧪 TEST MODE - Processing 3 documents")
    
    processor = OptimizedBatchProcessor(rate_limit=500)
    processor.run(mode=args.mode, limit=args.limit)


if __name__ == "__main__":
    main()
