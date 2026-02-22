#!/bin/bash
# =============================================================================
# Inwezt Scraper - Remote Setup Script for EC2
# Run this after unzipping the package on EC2
# =============================================================================

set -e

echo "=================================================="
echo "ANALYEZ SCRAPER - EC2 Setup"
echo "=================================================="

# Check if running as expected
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: Run this script from the project root directory"
    exit 1
fi

# 1. Install system dependencies
echo "[1/5] Installing system packages..."
sudo apt update
sudo apt install -y python3-pip python3-venv libpq-dev

# 2. Create virtual environment
echo "[2/5] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 3. Install Python dependencies
echo "[3/5] Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Create necessary directories
echo "[4/5] Creating directories..."
# 4. Create necessary directories
echo "[4/5] Creating directories..."
mkdir -p data_platform/scrapers/logs
mkdir -p data

# ... (Previous lines preserved implicitly if I use chunks, but replace content must replace existing block)

# I will target lines 36 only for mkdir
mkdir -p data_platform/scrapers/logs
mkdir -p data

# 5. Check for .env file
echo "[5/5] Checking configuration..."
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  .env file not found!"
    echo "   Copy .env.example to .env and configure:"
    echo ""
    echo "   cp .env.example .env"
    echo "   nano .env"
    echo ""
    echo "   Required variables:"
    echo "   - DATABASE_URL=postgresql://user:pass@host:5432/dbname"
    echo ""
else
    echo "✅ .env file found"
fi

echo ""
echo "=================================================="
echo "✅ SETUP COMPLETE"
echo "=================================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Configure environment (if not done):"
echo "   cp .env.example .env && nano .env"
echo ""
echo "2. Start the scrapers:"
echo "   ./data_platform/scrapers/run_parallel.sh"
echo ""
echo "3. Monitor progress:"
echo "   tail -f data_platform/scrapers/logs/instance_*.log"
echo ""
echo "=================================================="
