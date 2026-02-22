"""Backfill tsvector in tiny batches to avoid RDS OOM."""
import psycopg2
import os
import time
from dotenv import load_dotenv

load_dotenv(override=True)
DB = os.getenv("DATABASE_URL")

def backfill_batch(batch_size=500):
    """Process one batch, return count updated."""
    conn = psycopg2.connect(DB, sslmode='require', connect_timeout=15)
    cur = conn.cursor()
    try:
        cur.execute(f"""
            UPDATE document_chunks 
            SET search_vector = 
                setweight(to_tsvector('english', COALESCE(LEFT(context_prefix, 500), '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(LEFT(chunk_text, 4000), '')), 'B')
            WHERE id IN (
                SELECT id FROM document_chunks 
                WHERE search_vector IS NULL 
                LIMIT {batch_size}
            )
        """)
        updated = cur.rowcount
        conn.commit()
        return updated
    finally:
        cur.close()
        conn.close()

def check_status():
    conn = psycopg2.connect(DB, sslmode='require', connect_timeout=15)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM document_chunks WHERE search_vector IS NOT NULL")
    populated = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM document_chunks")
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    return populated, total

# Main
print("Backfilling tsvector (small batches)...")
populated, total = check_status()
print(f"  Starting: {populated:,}/{total:,} populated")

batch_num = 0
total_updated = 0
while True:
    try:
        updated = backfill_batch(500)
        total_updated += updated
        batch_num += 1
        if batch_num % 10 == 0:
            p, t = check_status()
            print(f"  Batch {batch_num}: total updated {total_updated:,} ({p:,}/{t:,})")
        if updated == 0:
            break
        time.sleep(0.5)  # Give RDS breathing room
    except Exception as e:
        print(f"  Error in batch {batch_num}: {e}")
        time.sleep(5)  # Wait and retry

populated, total = check_status()
print(f"\n✅ Done! {populated:,}/{total:,} chunks have tsvector")

# Check columns and indexes
conn = psycopg2.connect(DB, sslmode='require', connect_timeout=15)
cur = conn.cursor()
for col in ['search_vector', 'doc_type', 'context_prefix']:
    cur.execute(f"""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'document_chunks' AND column_name = '{col}'
    """)
    print(f"  {col}: {'✅' if cur.fetchone() else '❌'}")

cur.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'document_chunks' ORDER BY indexname")
print("\nIndexes:")
for r in cur.fetchall():
    print(f"  - {r[0]}")
cur.close()
conn.close()
