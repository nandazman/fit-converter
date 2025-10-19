#!/bin/bash

# Huawei Swim OCR App - Run Script
# This script sets up and runs the application with virtual environment

set -e  # Exit on any error

# Help function
show_help() {
    echo "🏊 Huawei Swim OCR App - Run Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  --no-check     Skip dependency and port checks"
    echo "  --force        Force reinstall dependencies"
    echo ""
    echo "This script will:"
    echo "  1. Create/activate virtual environment"
    echo "  2. Install dependencies if needed"
    echo "  3. Check system requirements"
    echo "  4. Start the FastAPI server"
    echo ""
    echo "Web UI: http://localhost:8000/static/index.html"
    echo "API Docs: http://localhost:8000/docs"
}

# Parse command line arguments
NO_CHECK=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --no-check)
            NO_CHECK=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "🏊 Starting Huawei Swim OCR App..."

# Check if we're in the right directory
if [ ! -f "requirements.txt" ] || [ ! -f "app/main.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    echo "   Expected files: requirements.txt, app/main.py"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv --copies
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Check if dependencies are installed
if [ "$NO_CHECK" = false ]; then
    echo "📋 Checking dependencies..."
    if [ "$FORCE" = true ] || ! python -c "import fastapi, uvicorn, cv2, pytesseract" 2>/dev/null; then
        echo "📦 Installing dependencies..."
        pip install --upgrade pip
        if [ "$FORCE" = true ]; then
            pip install -r requirements.txt --force-reinstall
        else
            pip install -r requirements.txt
        fi
        echo "✅ Dependencies installed"
    else
        echo "✅ Dependencies already installed"
    fi
else
    echo "⏭️  Skipping dependency check (--no-check flag)"
fi

# Test imports with better error handling
if [ "$NO_CHECK" = false ]; then
    echo "🧪 Testing application imports..."
    if python -c "from app.main import app; print('✅ App imports successfully')" 2>/dev/null; then
        echo "✅ Application ready"
    else
        echo "❌ Error: Application import failed"
        echo "   Trying to install missing dependencies..."
        pip install -r requirements.txt --force-reinstall
        if python -c "from app.main import app; print('✅ App imports successfully after reinstall')" 2>/dev/null; then
            echo "✅ Application ready after reinstall"
        else
            echo "❌ Error: Application still fails to import"
            echo "   Please check the error messages above"
            exit 1
        fi
    fi
else
    echo "⏭️  Skipping import test (--no-check flag)"
fi

# Check if Tesseract is available
if [ "$NO_CHECK" = false ]; then
    echo "🔍 Checking Tesseract OCR..."
    if command -v tesseract >/dev/null 2>&1; then
        echo "✅ Tesseract OCR is available"
        tesseract --version | head -1
    else
        echo "⚠️  Warning: Tesseract OCR not found. Install with:"
        echo "   sudo apt install tesseract-ocr libtesseract-dev"
        echo "   The app will still work but OCR features may not function properly."
    fi
else
    echo "⏭️  Skipping Tesseract check (--no-check flag)"
fi

# Check if port 8000 is available
if [ "$NO_CHECK" = false ]; then
    echo "🔍 Checking if port 8000 is available..."
    if command -v lsof >/dev/null 2>&1; then
        if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo "⚠️  Warning: Port 8000 is already in use"
            echo "   Please stop the existing service or use a different port"
            echo "   You can kill the process with: pkill -f 'python app/main.py'"
            exit 1
        else
            echo "✅ Port 8000 is available"
        fi
    else
        echo "⚠️  Warning: Cannot check port availability (lsof not available)"
        echo "   If the server fails to start, port 8000 might be in use"
    fi
else
    echo "⏭️  Skipping port check (--no-check flag)"
fi

# Start the application
echo ""
echo "🚀 Starting FastAPI server..."
echo "   - Web UI: http://localhost:8000/static/index.html"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Health Check: http://localhost:8000/healthz"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the application with error handling
if python main.py; then
    echo "✅ Server stopped gracefully"
else
    echo "❌ Server encountered an error"
    exit 1
fi
