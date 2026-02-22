#!/bin/bash
set -e

echo "🚀 Packaging Inwezt Waitlist App..."

# 1. Cleaning
echo "🧹 Cleaning previous builds..."
rm -rf inwezt_backend_pkg.zip
rm -rf backend/static/*

# 2. Build Frontend
echo "🏗️  Building React Frontend..."
cd inwezt_frontend
npm install
npm run build
cd ..

# 3. Move Frontend to Backend Static
echo "📂 Moving Frontend build to Backend..."
# Ensure backend static dir exists
mkdir -p backend/static
# Copy 'dist' contents to 'static'
cp -r inwezt_frontend/dist/* backend/static/

# 4. Create Deployment Zip
echo "📦 Zipping application..."
zip -r inwezt_waitlist_pkg.zip \
    backend \
    run.py \
    requirements.txt \
    .env.example

echo "✅ Package created: inwezt_waitlist_pkg.zip"
echo "Ready to upload to EC2!"
