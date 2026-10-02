#!/bin/bash
# Run script for Linux/Mac

# Activate virtual environment if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the application (optimized owner-detector; passes through extra args)
python run.py "$@"
