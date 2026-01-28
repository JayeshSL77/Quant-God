# Backend: Inwezt Ingestion Engine

The core data ingestion and processing engine for the Inwezt Copilot. This backend handles web scraping, PDF analysis, and financial data extraction for companies in the Nifty 500.

## Architecture

- **Scrapers**: Modular scrapers for BSE, Screener.io, and other financial portals.
- **Orchestrator**: Manages the ingestion lifecycle, retry logic, and concurrency.
- **Database Layer**: Handlers for storing extracted text and structured financial metrics.
- **Agents**: AI-driven analysis of scrapped data.

## Project Structure

```text
backend/
├── scrapers/          # Source code for data collection
│   ├── logs/          # Consolidated scraping execution logs
│   ├── base.py        # Base scraper class
│   ├── engine.py      # Core processing logic
│   └── orchestrator.py # Ingestion flow management
├── database/          # DB connection and migration scripts
├── agents/            # AI analysis modules
├── utils/             # Common helper functions
└── backend_thesis.md  # Detailed technical architectural overview
```

## Getting Started

1. **Set up Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Ingestion**:
   ```bash
   python scrapers/bulk_ingest.py
   ```

## Log Management

Execution logs are stored in `scrapers/logs/`. Each run generates a timestamped or thematic log file for tracking progress across the Nifty 500.

## Production Notes

- Ensure the database connection string is set via environment variables.
- The scrapers are designed to handle network timeouts and rate-limiting gracefully.
