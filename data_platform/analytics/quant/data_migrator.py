from sqlalchemy import text
from db_utils import AWSResourceConnector
from models import StockPrice
from typing import List

class DataMigrator:
    def __init__(self):
        self.connector = AWSResourceConnector()
        self.engine = self.connector.get_rds_engine()
        self.ensure_table_exists()

    def ensure_table_exists(self):
        """
        Idempotent operation to create the table if it doesn't exist.
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS stock_prices (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(50) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            currency VARCHAR(10) DEFAULT 'INR',
            daily_change DECIMAL(10, 2),
            daily_change_percent DECIMAL(5, 2),
            volume BIGINT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text(create_table_sql))
                conn.commit()
            print("✅ IDEMPOTENCY CHECK: Table 'stock_prices' ensures to exist.")
        except Exception as e:
            print(f"❌ Failed to check/create table: {e}")

    def save_prices(self, prices: List[StockPrice]):
        """
        Saves a list of StockPrice objects to the database.
        Uses a transaction to ensure all-or-nothing (Atomicity).
        """
        if not prices:
            return

        insert_sql = text("""
            INSERT INTO stock_prices (symbol, price, currency, daily_change, daily_change_percent, fetched_at)
            VALUES (:symbol, :price, :currency, :daily_change, :daily_change_percent, :timestamp)
        """)

        try:
            with self.engine.begin() as conn: # .begin() starts a transaction automatically
                for p in prices:
                    conn.execute(insert_sql, {
                        "symbol": p.symbol,
                        "price": p.price,
                        "currency": p.currency,
                        "daily_change": p.daily_change,
                        "daily_change_percent": p.daily_change_percent,
                        "timestamp": p.timestamp
                    })
            print(f"✅ ATOMICITY SUCCESS: Successfully saved {len(prices)} records to DB.")
        except Exception as e:
            print(f"❌ Transaction Failed! Rolling back. No data was saved. Error: {e}")
