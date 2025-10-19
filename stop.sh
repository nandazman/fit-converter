#!/bin/bash

# Huawei Swim OCR App - Stop Script
# This script stops the running server gracefully

set -e  # Exit on any error

echo "🛑 Stopping Huawei Swim OCR App..."

# Check if we're in the right directory
if [ ! -f "requirements.txt" ] || [ ! -f "app/main.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    echo "   Expected files: requirements.txt, app/main.py"
    exit 1
fi

# Find uvicorn processes running on port 8000
echo "🔍 Looking for running server processes..."

# Method 1: Find by port
PORT_PIDS=$(lsof -ti:8000 2>/dev/null || true)

# Method 2: Find by process name
UVICORN_PIDS=$(pgrep -f "uvicorn.*app.main:app" 2>/dev/null || true)

# Method 3: Find by python process with main.py
PYTHON_PIDS=$(pgrep -f "python.*app/main.py" 2>/dev/null || true)

# Combine all PIDs and remove duplicates
ALL_PIDS=$(echo "$PORT_PIDS $UVICORN_PIDS $PYTHON_PIDS" | tr ' ' '\n' | sort -u | grep -v '^$' || true)

if [ -z "$ALL_PIDS" ]; then
    echo "✅ No server processes found running"
    echo "   The server appears to already be stopped"
    exit 0
fi

echo "📋 Found running processes:"
for pid in $ALL_PIDS; do
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "   PID $pid: $(ps -p "$pid" -o comm= 2>/dev/null || echo 'unknown process')"
    fi
done

# Stop processes gracefully
echo ""
echo "🔄 Stopping server processes..."

for pid in $ALL_PIDS; do
    if ps -p "$pid" > /dev/null 2>&1; then
        echo "   Sending SIGTERM to PID $pid..."
        kill -TERM "$pid" 2>/dev/null || true
    fi
done

# Wait a moment for graceful shutdown
echo "⏳ Waiting for graceful shutdown..."
sleep 2

# Check if any processes are still running
REMAINING_PIDS=""
for pid in $ALL_PIDS; do
    if ps -p "$pid" > /dev/null 2>&1; then
        REMAINING_PIDS="$REMAINING_PIDS $pid"
    fi
done

# Force kill if necessary
if [ -n "$REMAINING_PIDS" ]; then
    echo "⚠️  Some processes didn't stop gracefully, forcing shutdown..."
    for pid in $REMAINING_PIDS; do
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "   Force killing PID $pid..."
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done
    sleep 1
fi

# Final check
FINAL_PIDS=$(lsof -ti:8000 2>/dev/null || true)
if [ -z "$FINAL_PIDS" ]; then
    echo "✅ Server stopped successfully"
    echo "   Port 8000 is now free"
else
    echo "❌ Warning: Some processes may still be running"
    echo "   Remaining PIDs: $FINAL_PIDS"
    echo "   You may need to manually kill them with: kill -9 $FINAL_PIDS"
    exit 1
fi

echo ""
echo "🏁 Stop script completed"
