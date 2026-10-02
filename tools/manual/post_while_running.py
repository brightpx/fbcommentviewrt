"""Post a test comment while CLI is running"""
import asyncio
from datetime import datetime
from app.main import FacebookCommentMonitor

async def main():
    monitor = FacebookCommentMonitor()
    
    try:
        await monitor.initialize()
        
        timestamp = datetime.now().strftime("%H%M%S")
        message = f"TEST_WHILE_RUNNING_{timestamp}"
        
        print(f"\n🔵 Posting comment: {message}")
        success = await monitor.post_new_comment(message)
        
        if success:
            print(f"✅ Comment posted! Check CLI for marker ●")
        else:
            print(f"❌ Failed to post comment")
            
    finally:
        await monitor.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
