"""Test manual comment with separate browser session."""
import asyncio
from datetime import datetime
from app.main import FacebookCommentMonitor

async def test_manual_comment():
    """Test posting a manual comment while monitor is running."""
    print("\n" + "="*80)
    print("TEST: Manual Comment with Separate Session")
    print("="*80 + "\n")
    
    # Create monitor instance
    monitor = FacebookCommentMonitor()
    
    try:
        # Initialize
        await monitor.initialize()
        print("✓ Monitor initialized\n")
        
        # Get post URL from config
        post_url = monitor.config['target']['post_url']
        print(f"Post URL: {post_url}\n")
        
        # Post a test comment using separate session
        timestamp = datetime.now().strftime("%H%M%S")
        test_message = f"TEST_MANUAL_COMMENT_SEPARATE_SESSION_{timestamp}"
        
        print(f"Posting test comment: {test_message}")
        print("This should open a SEPARATE browser window...\n")
        
        success = await monitor.post_new_comment(test_message)
        
        if success:
            print(f"\n✓ Manual comment posted successfully!")
            print(f"Message: {test_message}")
            print("\nThe separate browser session should have closed automatically.")
            print("The monitoring session should remain running.")
        else:
            print(f"\n✗ Failed to post manual comment")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await monitor.cleanup()
        print("\n✓ Cleanup completed")

if __name__ == "__main__":
    asyncio.run(test_manual_comment())
