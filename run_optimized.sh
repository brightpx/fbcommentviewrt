#!/bin/bash
# Run optimized Facebook Auto-Reply system
# Uses owner-focused detection for 10x performance improvement

echo "====================================="
echo "Optimized Facebook Auto-Reply"
echo "====================================="
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "Virtual environment activated"
    echo ""
fi

# Run the optimized version
python run_optimized.py
