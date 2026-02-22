#!/bin/bash

# EC2 Setup Script for Inwezt Waitlist (Ubuntu 22.04)
# Usage: ./setup_waitlist.sh <DOMAIN_NAME>
# Example: ./setup_waitlist.sh analyez.com

DOMAIN=${1:-analyez.com}

echo "🚀 Setting up Inwezt Waitlist for $DOMAIN..."

# 1. System Updates & Dependencies
echo "📦 Installing system dependencies..."
# Add Node.js repository for latest version
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y python3-pip python3-venv nginx certbot python3-certbot-nginx nodejs

# 2. Build Frontend (Server-Side)
echo "🏗️  Building Frontend on Server..."
cd inwezt_frontend
# Fix for potential memory issues on small instances
export NODE_OPTIONS="--max-old-space-size=2048"
npm install
npm run build
cd ..

# Move build to backend
echo "📂 Moving Frontend build..."
mkdir -p backend/static
cp -r inwezt_frontend/dist/* backend/static/

# 3. Python Environment
echo "🐍 Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn uvicorn

# 4. Systemd Service (Keep app running)
echo "⚙️ Creating Systemd service..."
sudo tee /etc/systemd/system/inwezt.service <<EOF
[Unit]
Description=Inwezt Waitlist App
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/inwezt_waitlist
Environment="PATH=/home/ubuntu/inwezt_waitlist/venv/bin"
EnvironmentFile=/home/ubuntu/inwezt_waitlist/.env
ExecStart=/home/ubuntu/inwezt_waitlist/venv/bin/uvicorn run:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable inwezt
sudo systemctl start inwezt
sudo systemctl restart inwezt

# 5. Nginx Configuration (Reverse Proxy)
echo "🌐 Configuring Nginx..."
sudo tee /etc/nginx/sites-available/$DOMAIN <<EOF
server {
    server_name $DOMAIN www.$DOMAIN;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# 5. SSL Certificate (HTTPS)
echo "🔒 Obtaining SSL Certificate (Let's Encrypt)..."
echo "You may need to enter your email for renewal notices."
sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN || echo "⚠️ Certbot failed (DNS might not be propagated yet). Run 'sudo certbot --nginx' later."

echo "✅ Setup Complete! Your app should be live at https://$DOMAIN"
