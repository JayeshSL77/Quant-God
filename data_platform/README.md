# Analyez Data Platform

The data engine powering Analyez, responsible for scraping, processing, and analyzing stock market data.

## Components

- **`scrapers/`**: Scripts to scrape Annual Reports, Concalls, and Stock Metadata (Screener.in, BSE/NSE).
- **`analytics/core/`**: Core analytics logic.
- **`analytics/quant/`**: Quantitative analysis models.

## Usage

Run scrapers from the root directory or `data_platform/scrapers/`:

```bash
# Example: Run bulk ingestion
python data_platform/scrapers/bulk_ingest.py
```
