
import os
import sys
import uvicorn
from dotenv import load_dotenv

# Ensure the current directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def main():
    """
    Main entry point for the Inwezt AI Backend.
    """
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    workers = int(os.getenv("WEB_CONCURRENCY", "1")) if not debug else 1
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    print(f"🚀 Starting Inwezt AI Backend on port {port} (Workers: {workers}, Debug: {debug})...")
    
    # Run Uvicorn
    # "backend.api.main:app" refers to the FastAPI instance in backend/api/main.py
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=debug,
        workers=workers,
        log_level=log_level,
        access_log=True
    )

if __name__ == "__main__":
    main()
