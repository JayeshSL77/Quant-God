#!/bin/bash
# =============================================================================
# INWEZT ONE-CLICK DEPLOYMENT
# Run this script to deploy everything to EC2 automatically.
# =============================================================================

EC2_IP="13.232.82.40"
KEY_FILE="scraper_key.pem"
PACKAGE="analyez_scraper_pkg.zip"

echo "🚀 Starting Deployment to $EC2_IP..."

# 0. Rebuild Package (to include latest .env)
echo "📦 Building deployment package..."
python3 create_ec2_package.py
if [ $? -ne 0 ]; then
    echo "❌ Failed to create package."
    exit 1
fi

# 1. Permission check
chmod 400 $KEY_FILE
echo "🔑 Key permissions fixed."

# 2. Upload Package (Chunked Mode for Bad Networks)
echo "📤 Uploading package in small chunks (Ultimate Connectivity Fix)..."

# Create a temporary directory for chunks
mkdir -p chunks
rm -f chunks/*

# Split file into 500KB chunks (small enough for any network)
if [ ! -f "$PACKAGE" ]; then
    echo "❌ Error: Package $PACKAGE not found!"
    exit 1
fi

split -b 500k "$PACKAGE" chunks/pkg_chunk_

if [ -z "$(ls -A chunks)" ]; then
    echo "❌ Error: Failed to split package. Directory empty."
    exit 1
fi

TOTAL_CHUNKS=$(ls chunks | wc -l)
CURRENT=0

echo "   Total chunks to upload: $TOTAL_CHUNKS"

for chunk in chunks/*; do
    ((CURRENT++))
    filename=$(basename "$chunk")
    echo -ne "   Uploading chunk $CURRENT/$TOTAL_CHUNKS ($filename)... \r"
    
    # Upload chunk - Retry loop
    MAX_RETRIES=3
    count=0
    success=0
    
    while [ $count -lt $MAX_RETRIES ]; do
        # Use base64 pipe for each chunk (safest method)
        cat "$chunk" | base64 | ssh -i $KEY_FILE -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$EC2_IP "cat > $filename.b64 && base64 -d $filename.b64 > $filename && rm $filename.b64"
        
        if [ $? -eq 0 ]; then
            success=1
            break
        fi
        ((count++))
        echo "   Retrying chunk $CURRENT..."
        sleep 2
    done
    
    if [ $success -eq 0 ]; then
        echo ""
        echo "❌ Failed to upload chunk $filename after $MAX_RETRIES attempts."
        exit 1
    fi
done

echo ""
echo "✅ All chunks uploaded."

# Reassemble on server
echo "📦 Reassembling file on server..."
ssh -i $KEY_FILE -o StrictHostKeyChecking=no ubuntu@$EC2_IP "cat pkg_chunk_* > $PACKAGE && rm pkg_chunk_*"

if [ $? -eq 0 ]; then
    echo "✅ Reassembly successful!"
else
    echo "❌ Reassembly failed."
    exit 1
fi
rm -rf chunks

# 3. Remote Setup & Launch
echo "🔧 Setting up remote environment..."
ssh -i $KEY_FILE -o StrictHostKeyChecking=no ubuntu@$EC2_IP 'bash -s' << 'ENDSSH'
    # Check if unzip is installed
    if ! command -v unzip &> /dev/null; then
        sudo apt update && sudo apt install -y unzip python3-pip python3-venv libpq-dev
    fi

    # Unzip
    unzip -o analyez_scraper_pkg.zip
    chmod +x setup_remote.sh data_platform/scrapers/run_parallel.sh

    # Run Setup
    ./setup_remote.sh

    # check if .env exists
    if [ -f ".env" ]; then
        echo "✅ .env file deployed successfully."
    else
        echo "⚠️  .env file MISSING!"
    fi

    # Start Scrapers
    echo "🚀 Launching Scrapers..."
    ./data_platform/scrapers/run_parallel.sh
ENDSSH

echo ""
echo "🎉 DEPLOYMENT COMPLETE!"
echo "You can check the logs with:"
echo "ssh -i $KEY_FILE ubuntu@$EC2_IP 'tail -f data_platform/scrapers/logs/instance_1.log'"
