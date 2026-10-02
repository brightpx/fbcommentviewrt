"""Test script to post a comment using the new post_new_comment() function"""
import asyncio
import yaml
from pathlib import Path
from datetime import datetime
from app.main import FacebookCommentMonitor

async def main():
    """Test posting a comment"""
    # Load config
    config_path = Path("config.yaml")
    
    # Create monitor instance (pass path, not dict)
    monitor = FacebookCommentMonitor(config_path)
    
    # Get post URL from config
    post_url = monitor.config['target']['post_url']
    
    print("=" * 80)
    print("Testing post_new_comment() function")
    print("=" * 80)
    
    # Initialize monitor components
    print("\n1. Initializing monitor components...")
    success = await monitor.initialize()
    if not success:
        print("✗ Failed to initialize")
        return
    
    print("✓ Initialization successful")
    
    # Navigate to post
    print(f"\n2. Navigating to post: {post_url}")
    success = await monitor.scraper.navigate_to_post(post_url)
    if not success:
        print("✗ Failed to navigate to post")
        return
    
    print("✓ Navigation successful")
    
    # Post a test comment
    timestamp = datetime.now().strftime("%H%M%S")
    test_message = f"TEST_FUNCTION_COMMENT_{timestamp}"
    
    print(f"\n3. Posting comment via post_new_comment(): {test_message}")
    result = await monitor.post_new_comment(test_message)
    
    if result:
        print(f"\n✓ SUCCESS: Comment posted and displayed!")
    else:
        print(f"\n✗ FAILED: Could not post comment")
    
    print("\n4. Keeping browser open for 30 seconds to verify...")
    await asyncio.sleep(30)
    
    print("\nTest complete!")

if __name__ == "__main__":
    asyncio.run(main())
