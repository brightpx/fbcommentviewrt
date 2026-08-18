#!/usr/bin/env python
"""
Run script for Facebook Comment Monitor

Usage:
    python run.py
    
Or make executable and run:
    chmod +x run.py (Linux/Mac)
    ./run.py
"""

import sys
import asyncio
import shutil
from pathlib import Path

# Clear all __pycache__ directories before starting
app_dir = Path(__file__).parent
for cache_dir in app_dir.rglob("__pycache__"):
    try:
        shutil.rmtree(cache_dir)
    except Exception:
        pass

# Add app directory to path
sys.path.insert(0, str(app_dir))

from app.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        sys.exit(1)
