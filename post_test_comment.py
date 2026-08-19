"""Post test comment using existing monitor session"""
import asyncio
from datetime import datetime
from app.scraper.facebook import FacebookScraper
import yaml

async def main():
    # Load config
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Initialize scraper with existing session
    scraper = FacebookScraper(config)
    
    print("Initializing browser with existing session...")
    await scraper.initialize()
    
    # Post URL
    post_url = "https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806"
    
    print(f"Navigating to post: {post_url}")
    await scraper.navigate_to_post(post_url)
    
    # Get timestamp
    timestamp = datetime.now().strftime("%H%M%S")
    message = f"TEST_MANUAL_{timestamp}"
    
    print(f"\nPosting comment: {message}")
    success = await scraper.post_comment(message)
    
    if success:
        print(f"✓ Comment posted successfully!")
        print("Monitor should detect and auto-reply within 3-5 seconds...")
    else:
        print(f"✗ Failed to post comment")
    
    await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())
