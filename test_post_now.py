"""Test posting a new comment to verify CLI detection"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.main import FacebookCommentMonitor

async def main():
    """Post a test comment"""
    monitor = FacebookCommentMonitor()
    
    # Initialize (load config, setup browser)
    await monitor.initialize()
    
    # Navigate to the post
    post_url = monitor.config['target']['post_url']
    print(f"Navigating to: {post_url}")
    await monitor.scraper.navigate_to_post(post_url)
    
    # Post comment
    from datetime import datetime
    timestamp = datetime.now().strftime("%H%M%S")
    message = f"TEST_CLI_DETECTION_{timestamp}"
    
    print(f"Posting comment: {message}")
    success = await monitor.post_new_comment(message)
    
    if success:
        print(f"Comment posted successfully!")
        print(f"Check the running CLI to see if it appears with a marker")
    else:
        print(f"Failed to post comment")
    
    # Keep browser open for a moment
    print("Waiting 5 seconds before closing...")
    await asyncio.sleep(5)
    
    await monitor.cleanup()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
