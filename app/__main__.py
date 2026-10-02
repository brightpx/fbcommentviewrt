"""Facebook Auto-Reply (optimized owner-detector).

Usage:
    python -m app
"""

from .main_optimized import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
