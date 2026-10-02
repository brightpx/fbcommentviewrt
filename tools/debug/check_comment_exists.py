"""Check if a specific comment exists in the page HTML"""
import asyncio
import sys
import yaml
from app.scraper.facebook import FacebookScraper

async def main():
    comment_to_find = "TEST_CLI_DETECTION_175453"
    
    # Load config
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    scraper = FacebookScraper(config)
    await scraper.initialize()
    
    url = 'https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806'
    print(f"Navigating to: {url}")
    await scraper.navigate_to_post(url)
    
    print("Getting page HTML...")
    html = await scraper.page.content()
    
    if comment_to_find in html:
        print(f"✅ Found '{comment_to_find}' in page HTML")
    else:
        print(f"❌ NOT found '{comment_to_find}' in page HTML")
    
    # Also check parser
    from app.scraper.parser import FacebookParser
    parser = FacebookParser(scraper.page, max_tier=1, post_url=url)
    comments = await parser.parse_comments()
    
    print(f"\nParser found {len(comments)} comments total")
    found_in_parser = any(comment_to_find in c.message for c in comments)
    
    if found_in_parser:
        print(f"✅ Found '{comment_to_find}' in parsed comments")
        for c in comments:
            if comment_to_find in c.message:
                print(f"   Message: {c.message}")
                print(f"   Time: {c.time}")
    else:
        print(f"❌ NOT found '{comment_to_find}' in parsed comments")
        print("   Available comments:")
        for c in comments[:10]:
            print(f"   - {c.message[:50]}")
    
    await scraper.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
