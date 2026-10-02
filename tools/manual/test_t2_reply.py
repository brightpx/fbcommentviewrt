"""End-to-end test of reply_to_comment() — verify T2 nested reply actually posts."""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper
import logging
logging.basicConfig(level=logging.INFO)

COMMENT_ID_T1 = "3410792339082758"  # TEST_AUTO_REPLY_160510 (owner's T1)
TEST_MSG = "TEST_T2_0916"

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(5)

    ok = await s.reply_to_comment(COMMENT_ID_T1, TEST_MSG)
    print(f"\n=== reply_to_comment returned: {ok} ===")
    await asyncio.sleep(4)

    # Verify the reply was actually posted — search for the test text in comment articles
    result = await s.page.evaluate("""
        () => {
            const outs = [];
            const articles = document.querySelectorAll('div[role="article"]');
            // Find articles containing our test message
            articles.forEach((art, i) => {
                const text = (art.textContent || '').replace(/\\s+/g, ' ');
                if (text.includes('TEST_T2_0916')) {
                    const link = art.querySelector('a[href*="comment_id="]');
                    const m = link ? link.href.match(/comment_id=(\\d+)/) : null;
                    outs.push('FOUND TEST_T2_0916 in article[' + i + '] ID=' + (m ? m[1] : '?'));
                    // Show parent structure of this comment to verify nesting
                    let p = art.parentElement;
                    let depth = 0;
                    let parentInfo = '';
                    while (p && p !== document.body && depth < 5) {
                        if (p.getAttribute && p.getAttribute('role') === 'article') {
                            const ptext = (p.textContent || '').replace(/\\s+/g, ' ').slice(0, 50);
                            parentInfo += ' | parent-article: ' + ptext;
                        }
                        p = p.parentElement;
                        depth++;
                    }
                    outs.push('  Nesting:' + parentInfo);
                }
            });
            if (outs.length === 0) outs.push('TEST_T2_0916 NOT FOUND in any comment article');
            return outs.join('\\n');
        }
    """)
    print(result)
    await s.close()

asyncio.run(main())