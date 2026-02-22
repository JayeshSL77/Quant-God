#!/bin/bash
set -e

echo "🚀 Building and Deploying Analyez Waitlist..."

export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH

# Variables
PROJECT_DIR="/Users/brainx/Desktop/Create/Analyez "
FRONTEND_DIR="$PROJECT_DIR/web"
BACKEND_DIR="$PROJECT_DIR/api"
PEM_FILE="$PROJECT_DIR/scraper_key.pem"
EC2_HOST="13.232.82.40"
REMOTE_APP_DIR="/home/ubuntu/analyez_waitlist"

# 1. Build Frontend
echo "🏗️  Building React Frontend..."
cd "$FRONTEND_DIR"
npm install
npm run build

# 2. Copy Frontend to Backend Static
echo "✅ Frontend built directly to api/static (via vite.config.ts)"

# 3. Create deployment package
echo "📦 Creating deployment package..."
cd "$PROJECT_DIR"
rm -f waitlist_deploy.zip
zip -r waitlist_deploy.zip \
    api \
    requirements.txt \
    .env \
    -x "api/venv/*" \
    -x "api/__pycache__/*" \
    -x "**/.DS_Store"

# 4. Upload to EC2
echo "☁️  Uploading to EC2..."
scp -i "$PEM_FILE" -o StrictHostKeyChecking=no waitlist_deploy.zip ubuntu@$EC2_HOST:~/

# 5. Deploy on EC2
echo "🚀 Deploying on EC2..."
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no ubuntu@$EC2_HOST << 'ENDSSH'
cd ~
echo "📦 Extracting package..."
unzip -o waitlist_deploy.zip -d analyez_waitlist_new/

echo "🔄 Stopping service..."
sudo systemctl stop analyez

echo "🔄 Backing up and swapping..."
rm -rf analyez_waitlist_backup
mv analyez_waitlist analyez_waitlist_backup 2>/dev/null || true
mv analyez_waitlist_new analyez_waitlist

echo "🔧 Setting up venv..."
cd analyez_waitlist
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt --quiet

# Copy .env from backup
cp ~/analyez_waitlist_backup/.env ./ 2>/dev/null || echo "No .env to copy"


# Create/Update Systemd Service
echo "⚙️ Creating Systemd service for Analyez..."
sudo tee /etc/systemd/system/analyez.service <<EOF
[Unit]
Description=Analyez Waitlist App
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/analyez_waitlist
Environment="PATH=/home/ubuntu/analyez_waitlist/venv/bin"
EnvironmentFile=/home/ubuntu/analyez_waitlist/.env
ExecStart=/home/ubuntu/analyez_waitlist/venv/bin/uvicorn api.endpoints.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Remove old service if exists
if [ -f "/etc/systemd/system/inwezt.service" ]; then
    echo "Removed old inwezt service"
    sudo systemctl stop inwezt 2>/dev/null || true
    sudo systemctl disable inwezt 2>/dev/null || true
    sudo rm /etc/systemd/system/inwezt.service
fi

sudo systemctl daemon-reload
sudo systemctl enable analyez
echo "🚀 Starting service..."
sudo systemctl restart analyez

sleep 3
sudo systemctl status analyez --no-pager | head -10

echo ""
echo "✅ Deployment complete!"
ENDSSH

echo ""
echo "✅ Waitlist deployed successfully!"
echo "🌐 Access: https://analyez.com/waitlist/india"
echo "📧 Emails will be stored in RDS PostgreSQL"
echo "🔢 Position numbering starts from 77"
