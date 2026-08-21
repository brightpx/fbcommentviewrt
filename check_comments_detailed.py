"""Check precisely whether our test replies were actually posted as comments (not just sitting in input box)."""
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

    # Check comments only (inside role=article elements), not input boxes
    result = await s.page.evaluate("""
        () => {
            const outs = [];
            const articles = document.querySelectorAll('div[role="article"]');
            outs.push('Total articles: ' + articles.length);
            
            const searchTerms = ['TEST_AUTO_REPLY_0922', 'TEST_REPLY_BTN_0919', 'TEST_SUBMIT_0918', 'TEST_SUBMIT_0917', 'TEST_AUTO_REPLY_0921'];
            
            // Only articles that have a comment link (real comments)
            let commentCount = 0;
            articles.forEach((art, i) => {
                const link = art.querySelector('a[href*="comment_id="]');
                if (!link) return;
                commentCount++;
                const text = (art.textContent || '').replace(/\\s+/g, ' ');
                for (const term of searchTerms) {
                    if (text.includes(term)) {
                        outs.push('  Article[' + i + '] CONTAINS ' + term);
                    }
                }
            });
            outs.push('Comment articles (with comment link): ' + commentCount);
            
            // Show comment IDs and first 60 chars of each comment article
            let idx = 0;
            articles.forEach((art) => {
                const link = art.querySelector('a[href*="comment_id="]');
                if (!link) return;
                idx++;
                const m = link.href.match(/comment_id=(\\d+)/);
                const text = (art.textContent || '').replace(/\\s+/g, ' ').slice(0, 70);
                outs.push('  [' + idx + '] ID=' + (m ? m[1] : '?') + ' :: ' + text);
            });
            return outs.join('\\n');
        }
    """)
    print(result)
    await s.close()

asyncio.run(main())