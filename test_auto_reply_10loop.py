"""Test auto-reply functionality with 10 consecutive comments."""
import asyncio
import yaml
from datetime import datetime
from pathlib import Path
from app.scraper.facebook import FacebookScraper

async def test_10_loop():
    """Post 10 test comments to trigger auto-reply."""
    # Load config
    config_path = Path("config.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Initialize scraper
    scraper = FacebookScraper(config)
    
    try:
        # Initialize browser and login
        print("Initializing browser and logging in...")
        await scraper.initialize()
        await scraper.login()
        
        post_url = config['target']['post_url']
        print(f"Navigating to post: {post_url}")
        await scraper.page.goto(post_url, wait_until="domcontentloaded")
        await asyncio.sleep(2)  # Wait for page to load
        
        # Post 10 comments
        for i in range(1, 11):
            timestamp = datetime.now().strftime("%H%M%S")
            message = f"TEST_AUTO_REPLY_LOOP_{i:02d}_{timestamp}"
            
            print(f"\n{'='*60}")
            print(f"Posting comment {i}/10: {message}")
            print(f"{'='*60}")
            
            success = await scraper.post_comment(message)
            
            if success:
                print(f"✓ Comment {i}/10 posted successfully")
            else:
                print(f"✗ Failed to post comment {i}/10")
                break
            
            # Wait between posts to allow monitor to detect and reply
            if i < 10:
                print(f"Waiting 10 seconds for monitor to detect and reply...")
                await asyncio.sleep(10)
        
        print(f"\n{'='*60}")
        print("All 10 comments posted!")
        print("Monitor should now auto-reply to all 10 comments.")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(test_10_loop())
