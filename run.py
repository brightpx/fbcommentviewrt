#!/usr/bin/env python
"""Run script for Facebook Auto-Reply (optimized owner-detector).

Usage:
    python run.py [--post-test [MESSAGE]]
"""

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

# Clear all __pycache__ directories before starting
app_dir = Path(__file__).parent
for cache_dir in app_dir.rglob("__pycache__"):
    try:
        shutil.rmtree(cache_dir)
    except Exception:
        pass

# Add repo root to path
sys.path.insert(0, str(app_dir))

from app.main_optimized import main


def _ensure_single_instance(port: int = 51234):
    """Refuse to start when another monitor already holds the lock port.

    Prevents duplicate monitors fighting over the same browser session
    (which kills the browser with "Target page ... has been closed").
    """
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        print("ERROR: another monitor instance is already running. Exiting.")
        sys.exit(1)
    return sock  # keep referenced for the process lifetime


if __name__ == "__main__":
    _lock = _ensure_single_instance()
    parser = argparse.ArgumentParser(description="Run the optimized Facebook auto-reply monitor")
    parser.add_argument(
        "--post-test",
        nargs="?",
        const="",
        metavar="MESSAGE",
        help="Post a test comment in the monitor session before monitoring; optionally provide the message",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(post_test_message=args.post_test))
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
