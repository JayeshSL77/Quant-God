#!/bin/bash
set -e

echo "Fixing Inwezt Deployment..."

# 1. Install PostgreSQL
sudo apt-get install -y postgresql postgresql-contrib

# 2. Setup Database & User
sudo -u postgres psql -c "CREATE USER inwezt_user WITH PASSWORD 'Waitlist2026!';" || echo "User exists"
sudo -u postgres psql -c "CREATE DATABASE inwezt OWNER inwezt_user;" || echo "DB exists"
sudo -u postgres psql -c "ALTER USER inwezt_user CREATEDB;"

# 3. Create .env file
cat > .env <<EOF
APP_NAME="Inwezt AI"
ENVIRONMENT="production"
DEBUG=False
DATABASE_URL="postgresql://inwezt_user:Waitlist2026!@localhost/inwezt"
LOG_LEVEL="INFO"
ALLOWED_ORIGINS=["https://analyez.com", "https://www.analyez.com"]
EOF

# 4. Initialize Database Tables
source venv/bin/activate
python3 -c "from backend.database.database import init_database; init_database(); print('Tables Initialized')"

# 5. Restart Service
sudo systemctl restart inwezt
sudo systemctl status inwezt --no-pager

echo "Deployment Fixed! Backend should be running."
echo "REMINDER: Update DNS to this server IP!"
