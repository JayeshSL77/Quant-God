"""
BSE Corporate Filings — Database Schema Setup
AI Native Supreme Hedge Fund — 11,000 Agent Swarm

Creates 6 new tables for BSE filings data.
"""

import os
import logging
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BSEFilingsSchema")

DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")

TABLES = [
    # 1. Corporate Governance (quarterly CG reports)
    """
    CREATE TABLE IF NOT EXISTS corporate_governance (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        scrip_code VARCHAR(10),
        quarter VARCHAR(10),
        fiscal_year VARCHAR(10),
        report_date DATE,
        content TEXT,
        pdf_url TEXT,
        raw_json JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, quarter, fiscal_year)
    )
    """,

    # 2. Shareholding Pattern (quarterly)
    """
    CREATE TABLE IF NOT EXISTS shareholding_patterns (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        scrip_code VARCHAR(10),
        quarter VARCHAR(10),
        fiscal_year VARCHAR(10),
        promoter_holding NUMERIC,
        public_holding NUMERIC,
        institutional_holding NUMERIC,
        dii_holding NUMERIC,
        fii_holding NUMERIC,
        content TEXT,
        raw_json JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, quarter, fiscal_year)
    )
    """,

    # 3. Related Party Transactions
    """
    CREATE TABLE IF NOT EXISTS related_party_transactions (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        scrip_code VARCHAR(10),
        fiscal_year VARCHAR(10),
        half_year VARCHAR(10),
        report_date DATE,
        content TEXT,
        raw_json JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, fiscal_year, half_year)
    )
    """,

    # 4. Board & Shareholder Meetings
    """
    CREATE TABLE IF NOT EXISTS meetings (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        scrip_code VARCHAR(10),
        meeting_type VARCHAR(20),
        meeting_date DATE,
        purpose TEXT,
        agenda TEXT,
        content TEXT,
        raw_json JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, meeting_type, meeting_date)
    )
    """,

    # 5. Corporate Actions (dividends, splits, bonuses)
    """
    CREATE TABLE IF NOT EXISTS corporate_actions_bse (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        scrip_code VARCHAR(10),
        action_type VARCHAR(50),
        ex_date DATE,
        record_date DATE,
        bc_start_date DATE,
        bc_end_date DATE,
        details TEXT,
        raw_json JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, action_type, ex_date)
    )
    """,

    # 6. Deals & Disclosures (bulk/block deals + insider trading)
    """
    CREATE TABLE IF NOT EXISTS deals_and_disclosures (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        scrip_code VARCHAR(10),
        filing_type VARCHAR(30),
        trade_date DATE,
        client_name VARCHAR(500),
        buy_sell VARCHAR(10),
        quantity BIGINT,
        price NUMERIC,
        content TEXT,
        raw_json JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # 7. Scrip code mapping (symbol → BSE scrip code)
    """
    CREATE TABLE IF NOT EXISTS bse_scrip_codes (
        symbol VARCHAR(20) PRIMARY KEY,
        scrip_code VARCHAR(10) NOT NULL,
        company_name VARCHAR(300),
        isin VARCHAR(20),
        group_name VARCHAR(10),
        face_value NUMERIC,
        industry VARCHAR(200),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # 8. Integrated Filings (governance + finance)
    """
    CREATE TABLE IF NOT EXISTS integrated_filings (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        scrip_code VARCHAR(10),
        filing_type VARCHAR(50),
        quarter VARCHAR(10),
        fiscal_year VARCHAR(10),
        filing_date DATE,
        content TEXT,
        raw_json JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, filing_type, quarter, fiscal_year)
    )
    """,

    # 9. Corp Announcements (general — LODR, board outcomes, etc.)
    """
    CREATE TABLE IF NOT EXISTS corp_announcements (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL,
        scrip_code VARCHAR(10),
        announcement_type VARCHAR(100),
        announcement_date DATE,
        subject TEXT,
        content TEXT,
        pdf_url TEXT,
        raw_json JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cg_symbol ON corporate_governance(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_cg_fiscal ON corporate_governance(fiscal_year)",
    "CREATE INDEX IF NOT EXISTS idx_shp_symbol ON shareholding_patterns(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_shp_fiscal ON shareholding_patterns(fiscal_year)",
    "CREATE INDEX IF NOT EXISTS idx_rpt_symbol ON related_party_transactions(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_meetings_symbol ON meetings(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_meetings_type ON meetings(meeting_type)",
    "CREATE INDEX IF NOT EXISTS idx_ca_symbol ON corporate_actions_bse(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_ca_type ON corporate_actions_bse(action_type)",
    "CREATE INDEX IF NOT EXISTS idx_deals_symbol ON deals_and_disclosures(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_deals_type ON deals_and_disclosures(filing_type)",
    "CREATE INDEX IF NOT EXISTS idx_deals_date ON deals_and_disclosures(trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_scrip_code ON bse_scrip_codes(scrip_code)",
    "CREATE INDEX IF NOT EXISTS idx_intfil_symbol ON integrated_filings(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_ann_symbol ON corp_announcements(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_ann_date ON corp_announcements(announcement_date)",
    "CREATE INDEX IF NOT EXISTS idx_ann_type ON corp_announcements(announcement_type)",
]


def create_schema():
    """Create all BSE filing tables and indexes."""
    logger.info("Creating BSE filings schema...")
    conn = psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=15)
    cur = conn.cursor()

    for i, ddl in enumerate(TABLES, 1):
        try:
            cur.execute(ddl)
            table_name = ddl.split("CREATE TABLE IF NOT EXISTS ")[1].split(" (")[0].strip()
            logger.info(f"  ✅ {i}/{len(TABLES)} Table: {table_name}")
        except Exception as e:
            logger.error(f"  ❌ Table {i}: {e}")
    conn.commit()

    for idx_sql in INDEXES:
        try:
            cur.execute(idx_sql)
            idx_name = idx_sql.split("INDEX IF NOT EXISTS ")[1].split(" ON")[0]
            logger.info(f"  ✅ Index: {idx_name}")
        except Exception as e:
            logger.error(f"  ❌ Index: {e}")
    conn.commit()

    cur.close()
    conn.close()
    logger.info("✅ BSE filings schema created successfully!")


if __name__ == "__main__":
    create_schema()
