#!/bin/bash
set -e

echo "🧹 Cleaning up previous attempts..."
# Stop service first
sudo systemctl stop inwezt || true

# Remove partial directories
rm -rf /home/ubuntu/inwezt_waitlist
mkdir -p /home/ubuntu/inwezt_waitlist

# Remove partial extracts in Home to avoid confusion
rm -rf /home/ubuntu/backend
rm -rf /home/ubuntu/inwezt_frontend
rm -rf /home/ubuntu/deployment

echo "📦 Extracting Source Package..."
# Install unzip just in case
sudo apt-get install -y unzip
# Unzip into target directory
unzip -o /home/ubuntu/inwezt_source_pkg.zip -d /home/ubuntu/inwezt_waitlist/

echo "📂 Configuring Environment..."
# Move .env from Home to Target if exists
if [ -f "/home/ubuntu/.env" ]; then
    echo "Found .env in Home, moving..."
    mv /home/ubuntu/.env /home/ubuntu/inwezt_waitlist/
else
    echo "Creating default .env..."
    # Fallback env if missing
    cat > /home/ubuntu/inwezt_waitlist/.env <<EOF
APP_NAME="Inwezt AI"
ENVIRONMENT="production"
DEBUG=False
DATABASE_URL="postgresql://inwezt_user:Waitlist2026!@localhost/inwezt"
LOG_LEVEL="INFO"
ALLOWED_ORIGINS=["https://analyez.com", "https://www.analyez.com", "http://localhost:3000"]
EOF
fi

echo "🚀 Building and Starting..."
cd /home/ubuntu/inwezt_waitlist
chmod +x deployment/setup_waitlist.sh

# Run setup (this handles npm install, build, etc.)
./deployment/setup_waitlist.sh analyez.com

echo "🔄 Service Check..."
sudo systemctl restart inwezt
sudo systemctl status inwezt --no-pager

echo "✅ Deployment Finalized!"
