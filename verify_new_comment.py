import asyncio
import yaml
from app.scraper.facebook import FacebookScraper

async def verify():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    scraper = FacebookScraper(config)
    await scraper.initialize()
    
    url = 'https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806'
    await scraper.navigate_to_post(url)
    
    html = await scraper.page.content()
    
    print("\n=== Searching for TEST_WHILE_RUNNING_180937 ===")
    if 'TEST_WHILE_RUNNING_180937' in html:
        print("✅ Comment EXISTS on Facebook page")
    else:
        print("❌ Comment NOT FOUND on Facebook page")
    
    # Also check parser
    from app.scraper.parser import FacebookParser
    parser = FacebookParser(scraper.page, post_url=url)
    comments = await parser.parse_comments()
    
    print(f"\n=== Parser found {len(comments)} comments total ===")
    for c in comments:
        if 'TEST_WHILE_RUNNING' in c.message or 'TEST_CLI_DETECTION' in c.message:
            print(f"  - {c.message[:50]}")
    
    await scraper.cleanup()

asyncio.run(verify())
