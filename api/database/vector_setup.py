"""
Vector Database Setup for Inwezt RAG System
Installs pgvector and creates necessary tables/indexes for semantic search.
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VectorSetup")

DATABASE_URL = os.getenv("DATABASE_URL")


def setup_pgvector():
    """Install pgvector extension and create vector infrastructure."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not configured")
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Step 1: Install pgvector extension
    logger.info("Installing pgvector extension...")
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        logger.info("✅ pgvector extension installed successfully")
    except Exception as e:
        logger.error(f"❌ Failed to install pgvector: {e}")
        logger.info("Note: You may need rds_superuser role on AWS RDS")
        conn.rollback()
        return False
    
    # Step 2: Add embedding columns to existing tables
    logger.info("Adding embedding columns to annual_reports...")
    try:
        cur.execute("""
            ALTER TABLE annual_reports 
            ADD COLUMN IF NOT EXISTS embedding vector(768)
        """)
        conn.commit()
        logger.info("✅ Added embedding column to annual_reports")
    except Exception as e:
        logger.warning(f"Could not add column to annual_reports: {e}")
        conn.rollback()
    
    logger.info("Adding embedding columns to concalls...")
    try:
        cur.execute("""
            ALTER TABLE concalls 
            ADD COLUMN IF NOT EXISTS embedding vector(768)
        """)
        conn.commit()
        logger.info("✅ Added embedding column to concalls")
    except Exception as e:
        logger.warning(f"Could not add column to concalls: {e}")
        conn.rollback()
    
    # Step 3: Create document chunks table for large documents
    logger.info("Creating document_chunks table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id SERIAL PRIMARY KEY,
            source_table VARCHAR(50) NOT NULL,
            source_id INTEGER NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            fiscal_year VARCHAR(10),
            quarter VARCHAR(10),
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            section_type VARCHAR(50),
            embedding vector(1536),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_table, source_id, chunk_index)
        )
    """)
    conn.commit()
    logger.info("✅ Created document_chunks table")
    
    # Step 4: Create vector indexes (IVFFlat for approximate nearest neighbor)
    logger.info("Creating vector indexes...")
    
    # Need at least some data before creating IVFFlat index
    # For now, create a basic index that works with any amount of data
    try:
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
            ON document_chunks 
            USING hnsw (embedding vector_cosine_ops)
        """)
        conn.commit()
        logger.info("✅ Created HNSW index on document_chunks")
    except Exception as e:
        logger.warning(f"Could not create HNSW index (may need data first): {e}")
        conn.rollback()
    
    # Step 5: Create supporting indexes
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_symbol 
        ON document_chunks(symbol)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_source 
        ON document_chunks(source_table, source_id)
    """)
    conn.commit()
    logger.info("✅ Created supporting indexes")
    
    # Verify setup
    cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    has_vector = cur.fetchone() is not None
    
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'document_chunks' AND column_name = 'embedding'
    """)
    has_embedding_col = cur.fetchone() is not None
    
    cur.close()
    conn.close()
    
    logger.info("=" * 50)
    logger.info("SETUP VERIFICATION:")
    logger.info(f"  pgvector installed: {has_vector}")
    logger.info(f"  document_chunks.embedding exists: {has_embedding_col}")
    logger.info("=" * 50)
    
    return has_vector and has_embedding_col


if __name__ == "__main__":
    print("🚀 Setting up Vector Database Infrastructure...")
    success = setup_pgvector()
    if success:
        print("\n✅ Vector setup completed successfully!")
        print("Next step: Run chunking and embedding pipeline")
    else:
        print("\n❌ Setup failed. Check logs above.")
