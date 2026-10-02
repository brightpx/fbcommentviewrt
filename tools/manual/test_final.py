import asyncio
from app.scraper.facebook import FacebookScraper
from datetime import datetime
import logging
import yaml

logging.basicConfig(level=logging.INFO)

async def main():
    # Load config
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    scraper = FacebookScraper(config)
    
    # Initialize scraper
    print("Initializing scraper...")
    await scraper.initialize()
    
    # Navigate to post
    post_url = config['target']['post_url']
    print(f"Navigating to post...")
    await scraper.navigate_to_post(post_url)
    
    timestamp = datetime.now().strftime("%H%M%S")
    message = f"TEST_FINAL_{timestamp}"
    
    print(f"Posting comment: {message}")
    success = await scraper.post_comment(message)
    
    if success:
        print(f"✅ Posted: {message}")
    else:
        print(f"❌ Failed to post")
    
    await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())
