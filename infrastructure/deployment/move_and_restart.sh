#!/bin/bash
set -e

echo "📦 Organizing Files into inwezt_waitlist..."

# 1. Create Directory
mkdir -p /home/ubuntu/inwezt_waitlist

# 2. Check if files are unzipped in Home
if [ -d "/home/ubuntu/backend" ]; then
    echo "Found extracted files in Home. Moving..."
    mv /home/ubuntu/backend /home/ubuntu/inwezt_waitlist/
    mv /home/ubuntu/inwezt_frontend /home/ubuntu/inwezt_waitlist/
    mv /home/ubuntu/run.py /home/ubuntu/inwezt_waitlist/
    mv /home/ubuntu/requirements.txt /home/ubuntu/inwezt_waitlist/
    mv /home/ubuntu/deployment /home/ubuntu/inwezt_waitlist/ || true
    mv /home/ubuntu/.env /home/ubuntu/inwezt_waitlist/ || true
    mv /home/ubuntu/venv /home/ubuntu/inwezt_waitlist/ || true
    mv /home/ubuntu/scrapers /home/ubuntu/inwezt_waitlist/ || true
    echo "Files moved."
else
    echo "Files not found in Home. Maybe zip wasn't extracted?"
    if [ -f "/home/ubuntu/inwezt_source_pkg.zip" ]; then
        echo "Found zip. Extracting..."
        mv /home/ubuntu/inwezt_source_pkg.zip /home/ubuntu/inwezt_waitlist/
        cd /home/ubuntu/inwezt_waitlist
        sudo apt-get install -y unzip
        unzip -o inwezt_source_pkg.zip
        # Re-run setup to build frontend/venv if needed
        # Assuming venv moves failed if not extracted
    fi
fi

# 3. Fix Permissions
sudo chown -R ubuntu:ubuntu /home/ubuntu/inwezt_waitlist

# 4. Restart Service
echo "🔄 Restarting Service..."
sudo systemctl restart inwezt
sleep 2
sudo systemctl status inwezt --no-pager

echo "✅ App should be running now!"
