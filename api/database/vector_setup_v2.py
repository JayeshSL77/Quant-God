"""
Hybrid RAG Vector Database Setup v2 — AI Native Supreme Hedge Fund
Upgrades pgvector schema with BM25 keyword search, metadata columns, and HNSW indexes.
"""
import logging
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VectorSetupV2")

DATABASE_URL = os.getenv("DATABASE_URL")


def upgrade_schema():
    """Upgrade document_chunks for hybrid RAG: vector + BM25 + metadata."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not configured")
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=15)
    cur = conn.cursor()
    
    # Step 1: pgvector extension
    logger.info("1/7 — Ensuring pgvector extension...")
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.commit()
    logger.info("  ✅ pgvector ready")
    
    # Step 2: Add metadata columns
    logger.info("2/7 — Adding metadata columns...")
    metadata_cols = [
        ("doc_type", "VARCHAR(30)"),           # 'annual_report' or 'concall'
        ("context_prefix", "TEXT"),              # Anthropic-style contextual prefix
        ("page_start", "INTEGER"),              # Approximate page range
        ("page_end", "INTEGER"),
        ("search_vector", "tsvector"),          # BM25 keyword search
    ]
    for col_name, col_type in metadata_cols:
        try:
            cur.execute(f"""
                ALTER TABLE document_chunks 
                ADD COLUMN IF NOT EXISTS {col_name} {col_type}
            """)
            conn.commit()
            logger.info(f"  ✅ Added column: {col_name}")
        except Exception as e:
            logger.warning(f"  ⚠️ Column {col_name}: {e}")
            conn.rollback()
    
    # Step 3: Create GIN index for BM25 full-text search
    logger.info("3/7 — Creating GIN index for BM25 search...")
    try:
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_search_vector
            ON document_chunks USING gin(search_vector)
        """)
        conn.commit()
        logger.info("  ✅ GIN index created on search_vector")
    except Exception as e:
        logger.warning(f"  ⚠️ GIN index: {e}")
        conn.rollback()
    
    # Step 4: Create trigger to auto-populate tsvector on insert/update
    logger.info("4/7 — Creating tsvector trigger...")
    try:
        cur.execute("""
            CREATE OR REPLACE FUNCTION update_search_vector()
            RETURNS trigger AS $$
            BEGIN
                NEW.search_vector := 
                    setweight(to_tsvector('english', COALESCE(NEW.context_prefix, '')), 'A') ||
                    setweight(to_tsvector('english', COALESCE(NEW.chunk_text, '')), 'B');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        cur.execute("""
            DROP TRIGGER IF EXISTS trg_update_search_vector ON document_chunks;
            CREATE TRIGGER trg_update_search_vector
            BEFORE INSERT OR UPDATE OF chunk_text, context_prefix
            ON document_chunks
            FOR EACH ROW
            EXECUTE FUNCTION update_search_vector();
        """)
        conn.commit()
        logger.info("  ✅ tsvector trigger created")
    except Exception as e:
        logger.warning(f"  ⚠️ Trigger: {e}")
        conn.rollback()
    
    # Step 5: Metadata indexes for fast filtering
    logger.info("5/7 — Creating metadata indexes...")
    indexes = [
        ("idx_chunks_doc_type", "doc_type"),
        ("idx_chunks_fiscal_year", "fiscal_year"),
        ("idx_chunks_section_type", "section_type"),
        ("idx_chunks_symbol_year", "symbol, fiscal_year"),
        ("idx_chunks_symbol_section", "symbol, section_type"),
    ]
    for idx_name, idx_cols in indexes:
        try:
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS {idx_name}
                ON document_chunks({idx_cols})
            """)
            conn.commit()
            logger.info(f"  ✅ Index: {idx_name}")
        except Exception as e:
            logger.warning(f"  ⚠️ Index {idx_name}: {e}")
            conn.rollback()
    
    # Step 6: Ensure HNSW vector index exists
    logger.info("6/7 — Ensuring HNSW vector index...")
    try:
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 200)
        """)
        conn.commit()
        logger.info("  ✅ HNSW index ready (m=16, ef_construction=200)")
    except Exception as e:
        logger.warning(f"  ⚠️ HNSW index: {e}")
        conn.rollback()
    
    # Step 7: Backfill search_vector for existing chunks
    logger.info("7/7 — Backfilling tsvector for existing chunks...")
    try:
        cur.execute("""
            UPDATE document_chunks 
            SET search_vector = 
                setweight(to_tsvector('english', COALESCE(context_prefix, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(chunk_text, '')), 'B')
            WHERE search_vector IS NULL
        """)
        backfilled = cur.rowcount
        conn.commit()
        logger.info(f"  ✅ Backfilled {backfilled:,} rows")
    except Exception as e:
        logger.warning(f"  ⚠️ Backfill: {e}")
        conn.rollback()
    
    # Verify
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION:")
    
    cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    logger.info(f"  pgvector: {'✅' if cur.fetchone() else '❌'}")
    
    for col in ['search_vector', 'doc_type', 'context_prefix']:
        cur.execute(f"""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'document_chunks' AND column_name = '{col}'
        """)
        logger.info(f"  {col}: {'✅' if cur.fetchone() else '❌'}")
    
    cur.execute("SELECT COUNT(*) FROM document_chunks WHERE search_vector IS NOT NULL")
    sv_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM document_chunks")
    total = cur.fetchone()[0]
    logger.info(f"  search_vector populated: {sv_count:,}/{total:,}")
    
    logger.info("=" * 60)
    
    cur.close()
    conn.close()
    return True


if __name__ == "__main__":
    print("🚀 Upgrading to Hybrid RAG Schema v2...")
    print("   AI Native Supreme Hedge Fund — 11,000 Agent Swarm\n")
    success = upgrade_schema()
    if success:
        print("\n✅ Schema upgrade complete!")
        print("Next: Run hybrid_search.py to test")
    else:
        print("\n❌ Upgrade failed. Check logs.")
