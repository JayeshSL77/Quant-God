#!/usr/bin/env python3
"""
Coverage Report - Shows scraping progress for all stocks
Run: python3 backend/scrapers/coverage_report.py
"""
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")


def get_coverage_stats():
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in environment")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return

    print("\n" + "=" * 80)
    print(f"INWEZT SCRAPER - Coverage Report")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Get total counts
    cur.execute("SELECT COUNT(DISTINCT symbol) as count FROM annual_reports")
    ar_symbols = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM annual_reports")
    total_ars = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(DISTINCT symbol) as count FROM concalls")
    concall_symbols = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM concalls")
    total_concalls = cur.fetchone()['count']
    
    print(f"\n📊 SUMMARY")
    print(f"   Stocks with Annual Reports: {ar_symbols}")
    print(f"   Total Annual Reports: {total_ars}")
    print(f"   Stocks with Concalls: {concall_symbols}")
    print(f"   Total Concalls: {total_concalls}")
    print()

    # Get per-stock coverage with year ranges
    cur.execute("""
        SELECT 
            symbol, 
            COUNT(*) as ar_count, 
            MIN(fiscal_year) as min_year,
            MAX(fiscal_year) as max_year
        FROM annual_reports
        WHERE fiscal_year ~ '^[0-9]+$'
        GROUP BY symbol
        ORDER BY ar_count DESC, symbol
    """)
    ar_stats = {row['symbol']: row for row in cur.fetchall()}

    cur.execute("""
        SELECT 
            symbol, 
            COUNT(*) as concall_count, 
            MIN(fiscal_year) as min_year,
            MAX(fiscal_year) as max_year
        FROM concalls
        WHERE fiscal_year ~ '^[0-9]+$'
        GROUP BY symbol
        ORDER BY concall_count DESC, symbol
    """)
    concall_stats = {row['symbol']: row for row in cur.fetchall()}

    # Combine stats
    symbols = sorted(set(list(ar_stats.keys()) + list(concall_stats.keys())))
    
    print(f"Total Stocks Scanned: {len(symbols)}")
    print()
    print(f"{'Symbol':<15} | {'AR Count':<10} | {'AR Years':<22} | {'Concall Count':<15} | {'Concall Years':<22}")
    print("-" * 95)
    
    for symbol in symbols:
        ar = ar_stats.get(symbol, {'ar_count': 0, 'min_year': '-', 'max_year': '-'})
        concall = concall_stats.get(symbol, {'concall_count': 0, 'min_year': '-', 'max_year': '-'})
        
        ar_years = f"{ar['min_year']} - {ar['max_year']}" if ar['ar_count'] > 0 else "-"
        concall_years = f"{concall['min_year']} - {concall['max_year']}" if concall['concall_count'] > 0 else "-"
        
        print(f"{symbol:<15} | {ar['ar_count']:<10} | {ar_years:<22} | {concall['concall_count']:<15} | {concall_years:<22}")

    # Show stocks needing attention (low coverage)
    print("\n" + "=" * 80)
    print("⚠️  STOCKS NEEDING ATTENTION (Less than 3 Annual Reports)")
    print("=" * 80)
    
    low_coverage = [s for s in symbols if ar_stats.get(s, {}).get('ar_count', 0) < 3]
    if low_coverage:
        for symbol in low_coverage[:20]:  # Show first 20
            ar = ar_stats.get(symbol, {'ar_count': 0})
            concall = concall_stats.get(symbol, {'concall_count': 0})
            print(f"   {symbol}: {ar['ar_count']} ARs, {concall['concall_count']} Concalls")
        if len(low_coverage) > 20:
            print(f"   ... and {len(low_coverage) - 20} more")
    else:
        print("   ✅ All stocks have 3+ Annual Reports!")

    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    get_coverage_stats()
