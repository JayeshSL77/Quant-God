#!/bin/bash
set -e

echo "🔄 Upgrading Node.js to v22 (Vite requires 20+)..."
# Using NodeSource for latest Node.js
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
echo "✅ Node version: $(node -v)"

echo "🎨 Updating Branding in .env..."
# Go to backend root where .env lives
cd /home/ubuntu/inwezt_waitlist
if grep -q "APP_NAME" .env; then
    sed -i 's/APP_NAME=.*/APP_NAME="Analyez"/' .env
else
    echo 'APP_NAME="Analyez"' >> .env
fi

echo "🚀 Deploying Patch files..."
unzip -o ~/patch.zip -d /home/ubuntu/inwezt_waitlist/

echo "🏗️  Rebuilding Frontend (Vite)..."
cd /home/ubuntu/inwezt_waitlist/inwezt_frontend

# Install dependencies if missing (or rebuild for new Node version)
npm install
npm rebuild esbuild

# Build
npx vite build

echo "🔄 Restarting Service..."
sudo systemctl restart inwezt
sudo systemctl status inwezt --no-pager
echo "✅ Deployment Patch Complete!"
