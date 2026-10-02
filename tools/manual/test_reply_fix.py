"""Test: use scraper.reply_to_comment() directly with the fixes."""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper
import logging
logging.basicConfig(level=logging.INFO)

COMMENT_ID_T1 = "3410792339082758"  # TEST_AUTO_REPLY_160510

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(5)

    # Test the fixed reply_to_comment
    msg = "TEST_AUTO_REPLY_0922"
    print(f"Calling reply_to_comment({COMMENT_ID_T1}, '{msg}')...")
    success = await s.reply_to_comment(COMMENT_ID_T1, msg)
    print(f"Result: {success}")

    await asyncio.sleep(2)
    await s._take_screenshot("after_reply_fix")
    print("Screenshot saved")

    # Check if posted
    result = await s.page.evaluate("""
        () => {
            const body = document.body.textContent || '';
            return 'Has TEST_AUTO_REPLY_0922: ' + body.includes('TEST_AUTO_REPLY_0922');
        }
    """)
    print(result)

    await s.close()

asyncio.run(main())