429#!/bin/bash

# Swim OCR App Deployment Script
# This script sets up the application on the server

set -e

APP_DIR="/opt/swim-ocr"
SERVICE_NAME="swim-ocr"
NGINX_SITE="swim-ocr"

echo "🏊 Deploying Swim OCR App..."

# Create app directory if it doesn't exist
sudo mkdir -p $APP_DIR
sudo chown -R $USER:$USER $APP_DIR

# Copy application files
echo "📁 Copying application files..."
cp -r app/ $APP_DIR/
cp -r static/ $APP_DIR/
cp requirements.txt $APP_DIR/

# Create Python virtual environment
echo "🐍 Setting up Python virtual environment..."
cd $APP_DIR
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null <<EOF
[Unit]
Description=Swim OCR API
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/.venv/bin"
ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create Nginx configuration
echo "🌐 Setting up Nginx configuration..."
sudo tee /etc/nginx/sites-available/$NGINX_SITE.conf > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    # UI route
    location /swim/ {
        alias $APP_DIR/static/;
        try_files \$uri \$uri/ /index.html;
        index index.html;
    }

    # API routes
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 20M;
    }

    # Health check
    location /healthz {
        proxy_pass http://127.0.0.1:8000/healthz;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable Nginx site
echo "🔗 Enabling Nginx site..."
sudo ln -sf /etc/nginx/sites-available/$NGINX_SITE.conf /etc/nginx/sites-enabled/
sudo nginx -t

# Reload systemd and start services
echo "🚀 Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME
sudo systemctl reload nginx

# Check service status
echo "✅ Checking service status..."
sudo systemctl status $SERVICE_NAME --no-pager -l

echo "🎉 Deployment complete!"
echo "📱 Access your app at: http://$(curl -s ifconfig.me)/swim/"
echo "🔍 Health check: http://$(curl -s ifconfig.me)/healthz"