"""
Database Migration: Add missing IndianAPI fields to stock_snapshots

This migration adds fundamental fields that IndianAPI provides but weren't in the original schema:
- book_value
- dividend_per_share  
- revenue_growth
- profit_growth
- net_margin
- roe (Return on Equity)
"""

import os
import logging
from dotenv import load_dotenv
import psycopg2

load_dotenv(override=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DBMigration")

DATABASE_URL = os.getenv("DATABASE_URL")


def migrate():
    """Add missing columns to stock_snapshots table."""
    if not DATABASE_URL:
        logger.error("DATABASE_URL not configured")
        return False
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Check if columns already exist
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='stock_snapshots' AND column_name='book_value'
        """)
        
        if cur.fetchone():
            logger.info("Migration already applied, skipping")
            cur.close()
            conn.close()
            return True
        
        logger.info("Adding missing columns to stock_snapshots...")
        
        # Add all missing columns
        cur.execute("""
            ALTER TABLE stock_snapshots
            ADD COLUMN IF NOT EXISTS book_value DECIMAL(10,2),
            ADD COLUMN IF NOT EXISTS dividend_per_share DECIMAL(8,2),
            ADD COLUMN IF NOT EXISTS revenue_growth DECIMAL(8,2),
            ADD COLUMN IF NOT EXISTS profit_growth DECIMAL(8,2),
            ADD COLUMN IF NOT EXISTS net_margin DECIMAL(8,2),
            ADD COLUMN IF NOT EXISTS roe DECIMAL(8,2),
            ADD COLUMN IF NOT EXISTS revenue_per_share DECIMAL(10,2)
        """)
        
        conn.commit()
        logger.info("✓ Migration completed successfully")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = migrate()
    exit(0 if success else 1)
