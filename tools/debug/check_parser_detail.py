"""Check what parser actually sees"""
import asyncio
import json
from app.scraper.facebook import FacebookScraper
from app.scraper.parser import FacebookParser

async def main():
    # Read config
    with open('config.yaml', 'r', encoding='utf-8') as f:
        import yaml
        config = yaml.safe_load(f)
    
    scraper = FacebookScraper(config)
    await scraper.initialize()
    
    post_url = config['target']['post_url']
    await scraper.navigate_to_post(post_url)
    
    # Create parser
    max_tier = config.get('monitor', {}).get('max_tier', 999)
    max_comments = config.get('monitor', {}).get('max_comments', 0)
    parser = FacebookParser(scraper.page, max_tier=max_tier, max_comments=max_comments, post_url=post_url)
    
    # Get HTML
    html = await scraper.page.content()
    print(f"HTML contains TEST_CLI_DETECTION_175453: {'TEST_CLI_DETECTION_175453' in html}")
    print()
    
    # Parse comments
    comments = await parser.parse_comments()
    print(f"Parser found {len(comments)} comments:")
    for i, comment in enumerate(comments, 1):
        print(f"{i}. {comment.message[:50]} - {comment.author}")
    print()
    
    # Check if new comment is in parsed list
    new_comment = [c for c in comments if 'TEST_CLI_DETECTION_175453' in c.message]
    if new_comment:
        print(f"✅ Parser FOUND the new comment!")
        print(f"   Message: {new_comment[0].message}")
        print(f"   Tier: {new_comment[0].tier}")
    else:
        print(f"❌ Parser DID NOT find the new comment")
        print(f"   Even though it's in the HTML")
    
    await scraper.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
