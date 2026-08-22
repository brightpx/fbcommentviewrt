"""Run script for optimized owner comment detector.

Usage:
    python run_optimized.py
    
Or with batch file:
    run_optimized.bat
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.main_optimized import main

if __name__ == "__main__":
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
        # Pass post_test_message to main() - use empty string if --post-test without message
        # None means don't post, "" means post with default timestamp message
        asyncio.run(main(post_test_message=args.post_test))
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
