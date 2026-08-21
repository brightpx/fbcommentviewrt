"""Check how comment links look right now after navigation."""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper
import logging
logging.basicConfig(level=logging.WARNING)

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(6)

    result = await s.page.evaluate("""
        () => {
            const outs = [];
            const links = document.querySelectorAll('a[href*="comment_id"]');
            outs.push('Total links with comment_id: ' + links.length);
            links.forEach((l, i) => {
                if (i >= 15) return;
                const h = l.getAttribute('href') || '';
                const vis = l.offsetParent !== null;
                const rect = l.getBoundingClientRect();
                outs.push('[' + i + '] vis=' + vis + ' y=' + Math.round(rect.y) + ' :: ' + h.slice(0, 150));
            });
            return outs.join('\\n');
        }
    """)
    print(result)
    await s.close()

asyncio.run(main())