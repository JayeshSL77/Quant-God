#!/bin/bash
# Run 20 parallel scraper instances - Maximum performance mode

cd /Users/brainx/Desktop/Create/inwezt_app

# Kill any existing scrapers
pkill -f "bulk_ingest.py" 2>/dev/null
sleep 2
rm -f .scraper_*.lock

# Create logs directory
mkdir -p backend/scrapers/logs

echo "🚀 Starting 20 parallel scraper instances - MAXIMUM PERFORMANCE MODE"
echo "Each instance will process ~18 stocks"
echo ""

# Launch 20 instances
for i in {1..20}; do
    nohup python3 backend/scrapers/bulk_ingest.py --instance $i --total 20 > backend/scrapers/logs/instance_$i.log 2>&1 &
    echo "Instance $i started (PID: $!)"
done

echo ""
echo "✅ All 20 instances started!"
echo ""
echo "📊 Monitor with:"
echo "  tail -f backend/scrapers/logs/instance_*.log"
echo ""
echo "📈 Check coverage:"
echo "  python3 backend/scrapers/coverage_report.py"
echo ""
echo "⏱️  Estimated completion: ~2 hours (by 4 AM)"
