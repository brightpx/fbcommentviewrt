#!/usr/bin/env python
"""Run the FB comment web dashboard.

Usage:
    python run_web.py [--host 127.0.0.1] [--port 5000] [--debug]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.web import create_app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FB comment web dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    create_app().run(host=args.host, port=args.port, debug=args.debug)
