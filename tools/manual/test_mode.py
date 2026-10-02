"""Test mode: Monitor with auto-reply testing (5 loops)."""
import asyncio
from datetime import datetime
from app.main import FacebookCommentMonitor

async def test_auto_reply_mode():
    """Run monitor and test auto-reply with 5 consecutive comments."""
    print("\n" + "="*80)
    print("TEST MODE: Auto-Reply Testing (5 loops)")
    print("="*80 + "\n")
    
    monitor = FacebookCommentMonitor()
    
    try:
        # Initialize
        print("Initializing monitor...")
        await monitor.initialize()
        print("✓ Monitor initialized\n")
        
        # Start monitoring in background task
        post_url = monitor.config['target']['post_url']
        print(f"Starting monitor on: {post_url}")
        print("Monitor will run in background...\n")
        
        # Create monitoring task
        monitor_task = asyncio.create_task(monitor.start_monitoring(post_url))
        
        # Wait for monitor to initialize
        await asyncio.sleep(5)
        print("✓ Monitor started\n")
        
        # Post 5 test comments
        print("="*80)
        print("Posting 5 test comments...")
        print("="*80 + "\n")
        
        for i in range(1, 6):
            timestamp = datetime.now().strftime("%H%M%S")
            test_message = f"TEST_AUTO_REPLY_LOOP_{i:02d}_{timestamp}"
            
            print(f"[{i}/5] Posting: {test_message}")
            success = await monitor.post_new_comment(test_message)
            
            if success:
                print(f"     ✓ Posted successfully")
            else:
                print(f"     ✗ Failed to post")
            
            # Wait between posts
            if i < 5:
                print(f"     Waiting 8 seconds before next post...\n")
                await asyncio.sleep(8)
        
        print("\n" + "="*80)
        print("All 5 comments posted!")
        print("="*80 + "\n")
        
        # Wait for auto-replies to trigger
        print("Waiting 15 seconds for auto-replies to appear...")
        await asyncio.sleep(15)
        
        print("\n" + "="*80)
        print("Test completed!")
        print("Check the monitor display for T2 replies.")
        print("="*80 + "\n")
        
        # Stop monitoring
        monitor.detector.stop_monitoring()
        
        # Wait for monitor task to complete
        try:
            await asyncio.wait_for(monitor_task, timeout=5.0)
        except asyncio.TimeoutError:
            print("Monitor task timeout - cancelling...")
            monitor_task.cancel()
        
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await monitor.cleanup()
        print("\n✓ Cleanup completed")

if __name__ == "__main__":
    try:
        asyncio.run(test_auto_reply_mode())
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
