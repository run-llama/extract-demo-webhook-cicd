#!/usr/bin/env bash
set -e

echo "=== LlamaExtract CI/CD Demo Setup ==="
echo ""

# Check Python
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "Error: Python is not installed. Please install Python 3.11+."
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1)
echo "Using: $PY_VERSION"

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
else
    echo "Virtual environment already exists."
fi

# Activate
source .venv/bin/activate
echo "Virtual environment activated."

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

# Create .env if needed
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "Created .env from .env.example."
    echo ">>> IMPORTANT: Edit .env and add your LLAMA_CLOUD_API_KEY <<<"
else
    echo ".env already exists."
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Usage:"
echo "  source .venv/bin/activate           # Activate virtual environment"
echo "  python extract.py                   # Extract data from receipts"
echo "  python extract.py --init-ground-truth  # Initialize ground truth"
echo "  python evaluate.py                  # Evaluate accuracy"
echo "  python evaluate.py --output-markdown   # Generate PR comment markdown"
echo ""
echo "Don't forget to set LLAMA_CLOUD_API_KEY in your .env file!"
