from sqlalchemy import text
from db_utils import AWSResourceConnector
import pandas as pd

def view_data():
    connector = AWSResourceConnector()
    engine = connector.get_rds_engine()
    
    print("\n--- 📊 Current Data in 'stock_prices' Table ---")
    try:
        with engine.connect() as conn:
            # Using pandas for a nice table display
            df = pd.read_sql("SELECT * FROM stock_prices ORDER BY fetched_at DESC LIMIT 10", conn)
            
            if df.empty:
                print("No data found in the table.")
            else:
                print(df.to_string(index=False))
                
    except Exception as e:
        print(f"❌ Error fetching data: {e}")

if __name__ == "__main__":
    view_data()
