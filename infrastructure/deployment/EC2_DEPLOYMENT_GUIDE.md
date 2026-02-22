# EC2 Deployment Guide - Inwezt Scrapers (c7i.large)

## Quick Start for Overnight Run

### 1. Upload Package to EC2

```bash
# From your local machine
scp -i scraper_key.pem inwezt_scraper_pkg.zip ubuntu@<EC2-IP>:~/
```

### 2. SSH and Setup

```bash
# Connect to EC2
ssh -i scraper_key.pem ubuntu@<EC2-IP>

# Setup (first time only)
sudo apt update && sudo apt install -y unzip python3-pip python3-venv
unzip inwezt_scraper_pkg.zip
cd inwezt_scraper_pkg
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add your DATABASE_URL and API keys
```

### 3. Start Scrapers

```bash
# Start 10 parallel instances
chmod +x backend/scrapers/run_parallel.sh
./backend/scrapers/run_parallel.sh
```

### 4. Disconnect and Sleep 😴

The scrapers run in background via `nohup`. Safe to disconnect.

---

## EC2 Instance Configuration

| Setting | Value |
|---------|-------|
| Instance Type | c7i.large (2 vCPU, 4GB RAM) |
| OS | Ubuntu 22.04 LTS |
| Storage | 30GB gp3 |
| Security Group | SSH (22) from your IP |

## Monitoring Commands

```bash
# View all logs (live)
tail -f backend/scrapers/logs/instance_*.log

# Check specific instance
tail -f backend/scrapers/logs/instance_1.log

# Check running processes
ps aux | grep bulk_ingest

# Check database coverage
python3 backend/scrapers/coverage_report.py

# Stop all scrapers
pkill -f bulk_ingest.py
```

## Performance Estimates

| Metric | Value |
|--------|-------|
| Parallel Instances | 10 |
| Stocks per Instance | ~20 |
| ARs per Stock | ~6-10 |
| Concalls per Stock | ~15-25 |
| Est. Time per Stock | 2-5 min |
| **Total Est. Time** | **4-6 hours** |

## Troubleshooting

### Scrapers Stopped Unexpectedly
```bash
# Check logs for errors
grep -i "error\|failed" backend/scrapers/logs/instance_*.log

# Restart scrapers
./backend/scrapers/run_parallel.sh
```

### Database Connection Issues
```bash
# Test connection
python3 -c "from backend.database.database import get_connection; get_connection(); print('OK')"
```

### Rate Limiting
If you see many 429 errors, reduce instances:
```bash
# Edit run_parallel.sh
NUM_INSTANCES=5  # Reduce from 10
```

## Environment Variables (.env)

```
DATABASE_URL=postgresql://user:pass@host:5432/dbname
RAPIDAPI_KEY=your-key  # Optional for IndianAPI
```

## What Gets Scraped

| Document Type | Source | Year Range | Storage |
|--------------|--------|------------|---------|
| Annual Reports | Screener.in | 2015-2026 | Full PDF text in `summary` field |
| Concalls (Transcript) | Screener.in | 2015-2026 | Full transcript in `transcript` field |
| Concalls (AI Summary) | Screener.in | Fallback | Combined in `transcript` field |
| Concalls (PPT) | Screener.in | Fallback | Combined in `transcript` field |

## Skip Logic (Avoiding Duplicates)

The scraper checks before downloading:
1. `annual_report_exists(symbol, fiscal_year)` - By symbol + year
2. `annual_report_url_exists(url)` - By URL (double-check)
3. `concall_exists(symbol, quarter, fiscal_year)` - By symbol + quarter + year
4. `concall_url_exists(url)` - By URL (double-check)

This ensures no duplicate downloads even if you restart the scrapers.
