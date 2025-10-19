#!/bin/bash

# Huawei Swim OCR App - Setup Script
# One-time setup for system dependencies and virtual environment

set -e  # Exit on any error

echo "🏊 Setting up Huawei Swim OCR App..."

# Check if we're in the right directory
if [ ! -f "requirements.txt" ] || [ ! -f "app/main.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    echo "   Expected files: requirements.txt, app/main.py"
    exit 1
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
echo "   This may require sudo password for system packages"

# Check if running on Ubuntu/Debian
if command -v apt >/dev/null 2>&1; then
    echo "   Installing Tesseract OCR and Python development tools..."
    sudo apt update
    sudo apt install -y tesseract-ocr libtesseract-dev python3-venv
    echo "✅ System dependencies installed"
else
    echo "⚠️  Warning: Not running on Ubuntu/Debian"
    echo "   Please install Tesseract OCR manually for your system"
fi

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
if [ -d ".venv" ]; then
    echo "   Virtual environment already exists, removing old one..."
    rm -rf .venv
fi

python3 -m venv .venv --copies
echo "✅ Virtual environment created"

# Activate and install Python dependencies
echo "📋 Installing Python dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Python dependencies installed"

# Test the setup
echo "🧪 Testing setup..."
if python -c "import app.main; print('✅ App imports successfully')" 2>/dev/null; then
    echo "✅ Application setup complete!"
else
    echo "❌ Error: Application import failed"
    exit 1
fi

if python -c "import cv2, pytesseract, fastapi; print('✅ All dependencies available')" 2>/dev/null; then
    echo "✅ All dependencies working"
else
    echo "❌ Error: Some dependencies not working"
    exit 1
fi

echo ""
echo "🎉 Setup complete! You can now run the application with:"
echo "   ./run.sh"
echo ""
echo "Or manually with:"
echo "   source .venv/bin/activate"
echo "   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
echo ""
