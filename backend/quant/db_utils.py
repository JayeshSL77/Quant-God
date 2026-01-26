import os
import boto3
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from botocore.exceptions import ClientError

# Load environment variables from .env file
load_dotenv()

class AWSResourceConnector:
    def __init__(self):
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')

    def get_rds_engine(self):
        """
        Creates a SQLAlchemy engine for RDS (Postgres/MySQL)
        Relies on DATABASE_URL in .env
        """
        db_url = os.getenv('DATABASE_URL')
        db_password = os.getenv('DB_PASSWORD')

        if not db_url:
            raise ValueError("DATABASE_URL not found in environment variables")
        
        # If DB_PASSWORD is provided separately, inject it safely (handles special chars)
        if db_password:
            from urllib.parse import quote_plus
            import re
            # Regex to find the password part: :password@
            # We look for the part between the first : (port usually, or user separator) and @
            # detailed regex: :([^:@]+)@
            # simpler approach: replace the password in the string if we know the placeholder or just reconstruct it
            # But since we don't know the exact string 'password' the user put in there, we can't simple replace.
            # robust way: Reconstruct URL if components available, or trust user to putting a placeholder.
            
            # Let's try replacing the password segment strictly.
            # Assuming standard format: protocol://user:PASSWORD@host...
            # We will use string manipulation to be safer than regex if possible, or regex.
            match = re.search(r":([^:@]+)@", db_url)
            if match:
                current_password_in_url = match.group(1)
                # We won't blindly replace any string that matches the password, just the one in the URL structure
                # Actually, simpler: Use SQLAlchemy URL object? No, keep it simple.
                encoded_pwd = quote_plus(db_password)
                db_url = db_url.replace(f":{current_password_in_url}@", f":{encoded_pwd}@")

        # Force SSL mode if not present (fixes "no pg_hba.conf entry ... no encryption" error)
        if "sslmode" not in db_url:
            separator = "&" if "?" in db_url else "?"
            db_url += f"{separator}sslmode=require"
        
        try:
            engine = create_engine(db_url)
            # Test connection
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                print("✅ Successfully connected to RDS!")
            return engine
        except Exception as e:
            print(f"❌ Failed to connect to RDS: {e}")
            return None

    def get_dynamodb_resource(self):
        """
        Returns a helper for DynamoDB using Boto3
        """
        try:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.aws_region
            )
            dynamodb = session.resource('dynamodb')
            print("✅ Successfully initialized DynamoDB resource!")
            return dynamodb
        except Exception as e:
            print(f"❌ Failed to initialize DynamoDB: {e}")
            return None

    def get_s3_client(self):
        """
        Returns a helper for S3 using Boto3
        """
        try:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.aws_region
            )
            s3 = session.client('s3')
            print("✅ Successfully initialized S3 client!")
            return s3
        except Exception as e:
            print(f"❌ Failed to initialize S3: {e}")
            return None

if __name__ == "__main__":
    # Example Usage
    connector = AWSResourceConnector()
    
    print("--- Testing RDS Connection ---")
    # Uncomment to test if you have DATABASE_URL set
    connector.get_rds_engine()
    
    print("\n--- Testing DynamoDB Connection ---")
    connector.get_dynamodb_resource()
