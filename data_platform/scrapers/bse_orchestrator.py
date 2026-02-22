"""
BSE Filings Orchestrator
AI Native Supreme Hedge Fund — 11,000 Agent Swarm

Orchestrates BSE scraping across all 1,000 stocks with:
- Parallel instance support (same pattern as existing run_parallel.sh)
- Resume from where it left off
- Per-stock progress tracking
- DB insertion for all filing types
"""

import os
import sys
import json
import time
import logging
import argparse
import psycopg2
import psycopg2.extras
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BSEOrchestrator")

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bse_scraper import BSEScraper
from scrip_code_mapper import ScripCodeMapper

DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")


class BSEFilingsOrchestrator:
    """Orchestrates BSE filing scraping for all stocks."""

    def __init__(self, instance_id: int = 0, total_instances: int = 1):
        self.instance_id = instance_id
        self.total_instances = total_instances
        self.scraper = BSEScraper(rate_limit_delay=2.0)
        self.mapper = ScripCodeMapper()
        self.stats = {
            "stocks_processed": 0,
            "stocks_skipped": 0,
            "stocks_failed": 0,
            "total_filings_saved": 0,
            "start_time": time.time(),
        }

    def _get_connection(self):
        """Get a fresh DB connection."""
        return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=15)

    def _get_my_stocks(self) -> List[str]:
        """Get this instance's slice of stocks."""
        stocks_file = os.path.join(os.path.dirname(__file__), "bse_target_stocks.json")
        with open(stocks_file) as f:
            all_stocks = json.load(f)

        # Divide stocks across instances
        my_stocks = [s for i, s in enumerate(all_stocks) if i % self.total_instances == self.instance_id]
        logger.info(f"Instance {self.instance_id}: {len(my_stocks)}/{len(all_stocks)} stocks assigned")
        return my_stocks

    def _is_stock_scraped(self, symbol: str) -> bool:
        """Check if a stock already has BSE filings in the database."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            # Check if we have at least one filing type for this stock
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM corporate_governance WHERE symbol = %s) +
                    (SELECT COUNT(*) FROM shareholding_patterns WHERE symbol = %s) +
                    (SELECT COUNT(*) FROM corporate_actions_bse WHERE symbol = %s) +
                    (SELECT COUNT(*) FROM meetings WHERE symbol = %s)
            """, (symbol, symbol, symbol, symbol))
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            return count > 5  # Skip if we already have decent coverage
        except Exception:
            return False

    def _save_corporate_governance(self, conn, symbol: str, scrip_code: str, data: List[Dict]):
        """Save corporate governance records."""
        if not data:
            return 0
        cur = conn.cursor()
        saved = 0
        for item in data:
            try:
                cur.execute("""
                    INSERT INTO corporate_governance (symbol, scrip_code, quarter, fiscal_year, report_date, content, pdf_url, raw_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, quarter, fiscal_year) DO UPDATE SET
                        content = COALESCE(EXCLUDED.content, corporate_governance.content),
                        pdf_url = COALESCE(EXCLUDED.pdf_url, corporate_governance.pdf_url),
                        raw_json = EXCLUDED.raw_json
                """, (
                    symbol, scrip_code,
                    item.get("quarter"), item.get("fiscal_year"),
                    self.scraper._parse_date(str(item.get("report_date", ""))),
                    item.get("content"), item.get("pdf_url"),
                    json.dumps(item.get("raw_json", {}), default=str),
                ))
                saved += 1
            except Exception as e:
                logger.debug(f"CG save error: {e}")
        conn.commit()
        return saved

    def _save_shareholding_pattern(self, conn, symbol: str, scrip_code: str, data: List[Dict]):
        """Save shareholding pattern records."""
        if not data:
            return 0
        cur = conn.cursor()
        saved = 0
        for item in data:
            try:
                cur.execute("""
                    INSERT INTO shareholding_patterns
                        (symbol, scrip_code, quarter, fiscal_year, promoter_holding, public_holding,
                         institutional_holding, dii_holding, fii_holding, content, raw_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, quarter, fiscal_year) DO UPDATE SET
                        promoter_holding = EXCLUDED.promoter_holding,
                        public_holding = EXCLUDED.public_holding,
                        institutional_holding = EXCLUDED.institutional_holding,
                        dii_holding = EXCLUDED.dii_holding,
                        fii_holding = EXCLUDED.fii_holding,
                        content = EXCLUDED.content,
                        raw_json = EXCLUDED.raw_json
                """, (
                    symbol, scrip_code,
                    item.get("quarter"), item.get("fiscal_year"),
                    item.get("promoter_holding"), item.get("public_holding"),
                    item.get("institutional_holding"), item.get("dii_holding"),
                    item.get("fii_holding"),
                    item.get("content"),
                    json.dumps(item.get("raw_json", {}), default=str),
                ))
                saved += 1
            except Exception as e:
                logger.debug(f"SHP save error: {e}")
        conn.commit()
        return saved

    def _save_related_party(self, conn, symbol: str, scrip_code: str, data: List[Dict]):
        """Save related party transaction records."""
        if not data:
            return 0
        cur = conn.cursor()
        saved = 0
        for item in data:
            try:
                cur.execute("""
                    INSERT INTO related_party_transactions
                        (symbol, scrip_code, fiscal_year, half_year, report_date, content, raw_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, fiscal_year, half_year) DO UPDATE SET
                        content = COALESCE(EXCLUDED.content, related_party_transactions.content),
                        raw_json = EXCLUDED.raw_json
                """, (
                    symbol, scrip_code,
                    item.get("fiscal_year"), item.get("half_year"),
                    self.scraper._parse_date(str(item.get("report_date", ""))),
                    item.get("content"),
                    json.dumps(item.get("raw_json", {}), default=str),
                ))
                saved += 1
            except Exception as e:
                logger.debug(f"RPT save error: {e}")
        conn.commit()
        return saved

    def _save_meetings(self, conn, symbol: str, scrip_code: str, data: List[Dict]):
        """Save meeting records (board + shareholder)."""
        if not data:
            return 0
        cur = conn.cursor()
        saved = 0
        for item in data:
            try:
                meeting_date = self.scraper._parse_date(str(item.get("meeting_date", "")))
                if not meeting_date:
                    continue
                cur.execute("""
                    INSERT INTO meetings
                        (symbol, scrip_code, meeting_type, meeting_date, purpose, agenda, content, raw_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, meeting_type, meeting_date) DO UPDATE SET
                        purpose = COALESCE(EXCLUDED.purpose, meetings.purpose),
                        agenda = COALESCE(EXCLUDED.agenda, meetings.agenda),
                        content = COALESCE(EXCLUDED.content, meetings.content),
                        raw_json = EXCLUDED.raw_json
                """, (
                    symbol, scrip_code,
                    item.get("meeting_type"), meeting_date,
                    item.get("purpose"), item.get("agenda"),
                    item.get("content"),
                    json.dumps(item.get("raw_json", {}), default=str),
                ))
                saved += 1
            except Exception as e:
                logger.debug(f"Meeting save error: {e}")
        conn.commit()
        return saved

    def _save_corporate_actions(self, conn, symbol: str, scrip_code: str, data: List[Dict]):
        """Save corporate action records."""
        if not data:
            return 0
        cur = conn.cursor()
        saved = 0
        for item in data:
            try:
                ex_date = self.scraper._parse_date(str(item.get("ex_date", "")))
                if not ex_date:
                    continue
                cur.execute("""
                    INSERT INTO corporate_actions_bse
                        (symbol, scrip_code, action_type, ex_date, record_date,
                         bc_start_date, bc_end_date, details, raw_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, action_type, ex_date) DO UPDATE SET
                        details = COALESCE(EXCLUDED.details, corporate_actions_bse.details),
                        raw_json = EXCLUDED.raw_json
                """, (
                    symbol, scrip_code,
                    item.get("action_type"), ex_date,
                    self.scraper._parse_date(str(item.get("record_date", ""))),
                    self.scraper._parse_date(str(item.get("bc_start_date", ""))),
                    self.scraper._parse_date(str(item.get("bc_end_date", ""))),
                    item.get("details"),
                    json.dumps(item.get("raw_json", {}), default=str),
                ))
                saved += 1
            except Exception as e:
                logger.debug(f"Corp action save error: {e}")
        conn.commit()
        return saved

    def _save_deals_and_disclosures(self, conn, symbol: str, scrip_code: str, data: List[Dict]):
        """Save bulk/block deals and insider trading disclosures."""
        if not data:
            return 0
        cur = conn.cursor()
        saved = 0
        for item in data:
            try:
                cur.execute("SAVEPOINT deal_sp")
                cur.execute("""
                    INSERT INTO deals_and_disclosures
                        (symbol, scrip_code, filing_type, trade_date, client_name,
                         buy_sell, quantity, price, content, raw_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    symbol, scrip_code,
                    item.get("filing_type"),
                    self.scraper._parse_date(str(item.get("trade_date", ""))),
                    str(item.get("client_name", ""))[:1000],
                    str(item.get("buy_sell", ""))[:10],
                    item.get("quantity"),
                    item.get("price"),
                    item.get("content"),
                    json.dumps(item.get("raw_json", {}), default=str),
                ))
                cur.execute("RELEASE SAVEPOINT deal_sp")
                saved += 1
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT deal_sp")
                logger.warning(f"Deal save error: {e}")
        conn.commit()
        return saved

    def _save_integrated_filings(self, conn, symbol: str, scrip_code: str, data: List[Dict]):
        """Save integrated filings."""
        if not data:
            return 0
        cur = conn.cursor()
        saved = 0
        for item in data:
            try:
                cur.execute("""
                    INSERT INTO integrated_filings
                        (symbol, scrip_code, filing_type, quarter, fiscal_year, filing_date, content, raw_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, filing_type, quarter, fiscal_year) DO UPDATE SET
                        content = COALESCE(EXCLUDED.content, integrated_filings.content),
                        raw_json = EXCLUDED.raw_json
                """, (
                    symbol, scrip_code,
                    item.get("filing_type"), item.get("quarter"), item.get("fiscal_year"),
                    self.scraper._parse_date(str(item.get("filing_date", ""))),
                    item.get("content"),
                    json.dumps(item.get("raw_json", {}), default=str),
                ))
                saved += 1
            except Exception as e:
                logger.debug(f"Integrated filing save error: {e}")
        conn.commit()
        return saved

    def _save_announcements(self, conn, symbol: str, scrip_code: str, data: List[Dict]):
        """Save corporate announcements."""
        if not data:
            return 0
        cur = conn.cursor()
        saved = 0
        for item in data:
            try:
                cur.execute("""
                    INSERT INTO corp_announcements
                        (symbol, scrip_code, announcement_type, announcement_date,
                         subject, content, pdf_url, raw_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    symbol, scrip_code,
                    item.get("announcement_type"),
                    self.scraper._parse_date(str(item.get("announcement_date", ""))),
                    item.get("subject"),
                    item.get("content"),
                    item.get("pdf_url"),
                    json.dumps(item.get("raw_json", {}), default=str),
                ))
                saved += 1
            except Exception as e:
                logger.debug(f"Announcement save error: {e}")
        conn.commit()
        return saved

    def _save_investor_complaints(self, conn, symbol: str, scrip_code: str, data: List[Dict]):
        """Save investor complaints."""
        if not data:
            return 0
        cur = conn.cursor()
        saved = 0
        for item in data:
            try:
                cur.execute("""
                    INSERT INTO investor_complaints
                        (symbol, scrip_code, quarter, fiscal_year, content, raw_json)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, quarter, fiscal_year) DO UPDATE SET
                        content = COALESCE(EXCLUDED.content, investor_complaints.content),
                        raw_json = EXCLUDED.raw_json
                """, (
                    symbol, scrip_code,
                    item.get("quarter"), item.get("fiscal_year"),
                    item.get("content"),
                    json.dumps(item.get("raw_json", {}), default=str),
                ))
                saved += 1
            except Exception as e:
                logger.debug(f"Investor complaint save error: {e}")
        conn.commit()
        return saved

    def process_stock(self, symbol: str) -> Dict:
        """Process all BSE filings for a single stock."""
        # Skip if already scraped
        if self._is_stock_scraped(symbol):
            logger.info(f"[{symbol}] Already scraped — skipping")
            self.stats["stocks_skipped"] += 1
            return {"status": "skipped"}

        # Resolve scrip code
        scrip_code = self.mapper.get_code(symbol)
        if not scrip_code:
            logger.warning(f"[{symbol}] No BSE scrip code found — skipping")
            self.stats["stocks_failed"] += 1
            return {"status": "no_scrip_code"}

        logger.info(f"[{symbol}] Scrip {scrip_code} — Fetching all filings...")

        try:
            # Fetch all filings
            filings = self.scraper.fetch_all_filings(scrip_code)

            # Save to DB
            conn = self._get_connection()
            total_saved = 0

            total_saved += self._save_corporate_governance(conn, symbol, scrip_code, filings["corporate_governance"])
            total_saved += self._save_shareholding_pattern(conn, symbol, scrip_code, filings["shareholding_pattern"])
            total_saved += self._save_related_party(conn, symbol, scrip_code, filings["related_party_transactions"])
            total_saved += self._save_meetings(conn, symbol, scrip_code,
                                               filings["board_meetings"] + filings["shareholder_meetings"])
            total_saved += self._save_corporate_actions(conn, symbol, scrip_code, filings["corporate_actions"])
            total_saved += self._save_deals_and_disclosures(conn, symbol, scrip_code,
                                                           filings["bulk_block_deals"] + filings["sdd_pit"])
            total_saved += self._save_integrated_filings(conn, symbol, scrip_code, filings["integrated_filing"])
            total_saved += self._save_announcements(conn, symbol, scrip_code, filings["corp_announcements"])

            # Save investor complaints to dedicated table
            total_saved += self._save_investor_complaints(conn, symbol, scrip_code,
                                                         filings.get("investor_complaints", []))

            conn.close()

            self.stats["stocks_processed"] += 1
            self.stats["total_filings_saved"] += total_saved

            # Per-filing summary
            summary = {k: len(v) for k, v in filings.items()}
            logger.info(f"[{symbol}] ✅ Saved {total_saved} filings — {summary}")

            return {"status": "success", "saved": total_saved, "summary": summary}

        except Exception as e:
            logger.error(f"[{symbol}] ❌ Failed: {e}")
            self.stats["stocks_failed"] += 1
            return {"status": "error", "error": str(e)}

    def run(self, test_mode: bool = False, test_symbols: List[str] = None):
        """Run the orchestrator for all assigned stocks."""
        if test_symbols:
            stocks = test_symbols
        else:
            stocks = self._get_my_stocks()

        if test_mode:
            stocks = stocks[:3]
            logger.info("🧪 TEST MODE — 3 stocks only")

        total = len(stocks)
        logger.info(f"🚀 BSE Filings Scraper — Instance {self.instance_id}")
        logger.info(f"   Processing {total} stocks...")
        logger.info("=" * 60)

        for i, symbol in enumerate(stocks):
            try:
                result = self.process_stock(symbol)
                elapsed = time.time() - self.stats["start_time"]
                rate = (i + 1) / (elapsed / 60) if elapsed > 0 else 0

                if (i + 1) % 10 == 0:
                    logger.info(
                        f"📊 Progress: {i+1}/{total} | "
                        f"✅ {self.stats['stocks_processed']} | "
                        f"⏭ {self.stats['stocks_skipped']} | "
                        f"❌ {self.stats['stocks_failed']} | "
                        f"📄 {self.stats['total_filings_saved']} filings | "
                        f"⏱ {rate:.1f} stocks/min"
                    )
            except KeyboardInterrupt:
                logger.info("⛔ Interrupted by user")
                break
            except Exception as e:
                logger.error(f"[{symbol}] Unexpected error: {e}")
                continue

        # Final summary
        elapsed = time.time() - self.stats["start_time"]
        logger.info("=" * 60)
        logger.info(f"🏁 COMPLETE — Instance {self.instance_id}")
        logger.info(f"   Processed: {self.stats['stocks_processed']}")
        logger.info(f"   Skipped: {self.stats['stocks_skipped']}")
        logger.info(f"   Failed: {self.stats['stocks_failed']}")
        logger.info(f"   Total filings saved: {self.stats['total_filings_saved']}")
        logger.info(f"   Time: {elapsed/60:.1f} minutes")
        logger.info(f"   Scraper stats: {self.scraper.stats}")


def main():
    parser = argparse.ArgumentParser(description="BSE Filings Orchestrator")
    parser.add_argument("--instance", type=int, default=0, help="Instance ID (0-indexed)")
    parser.add_argument("--total", type=int, default=1, help="Total instances")
    parser.add_argument("--test", action="store_true", help="Test with 3 stocks")
    parser.add_argument("--symbol", type=str, help="Process single symbol")
    args = parser.parse_args()

    orchestrator = BSEFilingsOrchestrator(
        instance_id=args.instance,
        total_instances=args.total
    )

    if args.symbol:
        orchestrator.run(test_symbols=[args.symbol])
    else:
        orchestrator.run(test_mode=args.test)


if __name__ == "__main__":
    main()
