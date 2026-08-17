#!/bin/bash
# Run script for Linux/Mac

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the application
python -m app.main
