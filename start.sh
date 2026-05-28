#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

if ! .venv/bin/python -c "import selenium" 2>/dev/null; then
    echo "Installing dependencies..."
    .venv/bin/pip install -q -r requirements.txt
fi

echo "Starting Turners Auction Logger..."
exec .venv/bin/python main.py
