"""Test auto-reply with one new owner comment."""
import asyncio
from datetime import datetime
from pathlib import Path
import yaml
from app.scraper.facebook import FacebookScraper


async def main():
    with open(Path("config.yaml"), encoding="utf-8") as f:
        config = yaml.safe_load(f)

    scraper = FacebookScraper(config)
    try:
        print("Initializing browser and logging in...")
        await scraper.initialize()
        await scraper.login()

        post_url = config["target"]["post_url"]
        print(f"Navigating to post: {post_url}")
        await scraper.navigate_to_post(post_url)

        message = f"TEST_AUTO_REPLY_LOOP_01_{datetime.now().strftime('%H%M%S')}"
        print(f"Posting comment: {message}")
        success = await scraper.post_comment(message)
        print("✓ Comment posted successfully" if success else "✗ Comment posting failed")

        if success:
            print("Waiting 10 seconds for monitor to detect and reply...")
            await asyncio.sleep(10)
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
