#!/bin/bash
# MINXG Setup Script
# Runs all setup tasks for a fresh installation.

set -e

echo "=========================================="
echo "  MINXG Setup Script"
echo "=========================================="

# Check Python version
echo ""
echo "[1/5] Checking Python version..."
python3 --version || { echo "ERROR: Python 3 not found"; exit 1; }

# Install dependencies
echo ""
echo "[2/5] Installing dependencies..."
pip3 install -e ".[dev]" || echo "WARNING: pip install failed, continuing..."

# Create directories
echo ""
echo "[3/5] Creating directories..."
mkdir -p ~/.minxg/{memory,workers,extensions,logs}

# Set permissions
echo ""
echo "[4/5] Setting permissions..."
chmod 755 ~/.minxg 2>/dev/null || true

# Run doctor
echo ""
echo "[5/5] Running diagnostic..."
python3 -m minxg.doctor 2>/dev/null || echo "WARNING: doctor check failed"

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Run 'minxg setup' to configure AI provider"
echo "  2. Run 'minxg' to start the TUI chat"
echo "  3. Run 'minxg web' to start the web UI"
echo ""
