"""
Facebook Group Comment Monitor
Real-time CLI monitoring tool for Facebook Group comments

Usage:
    python -m app.main

First run:
    1. Browser will open for Facebook login
    2. Login with your account
    3. Session will be saved automatically
    
Subsequent runs:
    1. Session will be loaded automatically
    2. Enter the Facebook Post URL when prompted
    3. Monitor will start displaying comments in real-time

Features:
    - Real-time comment monitoring (0.5s refresh)
    - Tree-structured display with tier levels
    - Color-coded by tier (T1-T4+)
    - Persistent SQLite storage
    - Session management (login once)
    - Support for public and private groups
    - Notifications for new comments/replies

Configuration:
    Edit config.yaml to customize settings

For more information, see README.md
"""

from .main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
