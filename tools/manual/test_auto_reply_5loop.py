"""Test auto-reply with 5 consecutive comments"""
import asyncio
from datetime import datetime
from app.scraper.facebook import FacebookScraper
import yaml

async def main():
    # Load config
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Initialize scraper
    scraper = FacebookScraper(config)
    
    print("Initializing browser and logging in...")
    await scraper.initialize()
    
    # Post URL
    post_url = "https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806"
    
    print(f"Navigating to post: {post_url}\n")
    await scraper.navigate_to_post(post_url)
    
    # Post 5 comments
    for i in range(1, 6):
        timestamp = datetime.now().strftime("%H%M%S")
        message = f"TEST_AUTO_REPLY_LOOP_{i:02d}_{timestamp}"
        
        print("=" * 60)
        print(f"Posting comment {i}/5: {message}")
        print("=" * 60)
        
        success = await scraper.post_comment(message)
        
        if success:
            print(f"✓ Comment {i}/5 posted successfully")
        else:
            print(f"✗ Comment {i}/5 failed")
        
        # Wait between posts to allow monitor to detect and reply
        if i < 5:
            print("Waiting 10 seconds for monitor to detect and reply...\n")
            await asyncio.sleep(10)
    
    print("\n" + "=" * 60)
    print("All 5 comments posted!")
    print("Monitor should now auto-reply to all 5 comments.")
    print("=" * 60)
    
    await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())
