#!/bin/bash
# =============================================================================
# ANALYEZ SCRAPER - Parallel Instance Launcher for EC2 c7i.large
# Optimized for overnight runs - 10 parallel instances
# =============================================================================

set -e

# Navigate to the project root
cd "$(dirname "$0")/../.."
PROJECT_ROOT=$(pwd)

echo "=================================================="
echo "ANALYEZ SCRAPER - EC2 Launcher"
echo "=================================================="
echo "Project root: $PROJECT_ROOT"
echo "Time: $(date)"
echo ""

# Configuration
NUM_INSTANCES=20  # Scaled up to 20 as requested

# Kill any existing scrapers
echo "[1/5] Stopping any existing scrapers..."
pkill -f "bulk_ingest.py" 2>/dev/null || true
sleep 2

# Clean up stale lock files
echo "[2/5] Cleaning up lock files..."
rm -f .scraper_*.lock

# Create logs directory
echo "[3/5] Creating logs directory..."
mkdir -p data_platform/scrapers/logs

# Clear old logs (optional - comment out to keep history)
# rm -f data_platform/scrapers/logs/instance_*.log

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "[ERROR] Virtual environment not found. Run setup_remote.sh first."
    exit 1
fi

# Fetch/Update stock list
echo "[3.5/5] Checking stock list..."
if [ ! -f "data_platform/scrapers/all_stocks.json" ]; then
    echo "  Fetching top 2000 stocks from Screener.in..."
    ./venv/bin/python3 data_platform/scrapers/fetch_screener_stocks.py --limit 2000
fi


# Check for arguments
CONCALLS_ONLY_FLAG=""
LIST_FILE_FLAG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --concalls-only)
            CONCALLS_ONLY_FLAG="--concalls-only"
            echo "  Mode: Concall-Only Focus (Skipping Annual Reports)"
            shift
            ;;
        --list-file)
            shift
            LIST_FILE_FLAG="--list-file $1"
            echo "  Custom List: $1"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Launch instances
echo "[4/5] Launching $NUM_INSTANCES parallel instances..."
echo ""

for i in $(seq 1 $NUM_INSTANCES); do
    nohup ./venv/bin/python3 data_platform/scrapers/bulk_ingest.py --instance $i --total $NUM_INSTANCES $CONCALLS_ONLY_FLAG $LIST_FILE_FLAG >> data_platform/scrapers/logs/instance_$i.log 2>&1 &
    PID=$!
    echo "  ✓ Instance $i started (PID: $PID)"
done

echo ""
echo "[5/5] All instances launched!"
echo ""
echo "=================================================="
echo "SCRAPER RUNNING - You can disconnect now"
echo "=================================================="
echo ""
echo "📊 MONITORING COMMANDS:"
echo ""
echo "  View all logs (live):"
echo "    tail -f data_platform/scrapers/logs/instance_*.log"
echo ""
echo "  View single instance:"
echo "    tail -f data_platform/scrapers/logs/instance_1.log"
echo ""
echo "  Check running processes:"
echo "    ps aux | grep bulk_ingest"
echo ""
echo "  Check coverage:"
echo "    python3 data_platform/scrapers/coverage_report.py"
echo ""
echo "  Stop all scrapers:"
echo "    pkill -f bulk_ingest.py"
echo ""
echo "=================================================="
echo "Estimated completion: ~4-6 hours for 500 stocks"
echo "=================================================="
