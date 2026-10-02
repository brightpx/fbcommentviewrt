"""Robust verify: expand comments + replies, then search for the T2 text."""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper
import logging
logging.basicConfig(level=logging.INFO)

T1_ID = "3410792339082758"
SEARCH_TEXT = "TEST_T2_0916"

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(6)

    # Expand "View more comments" / replies several times
    for round_no in range(4):
        clicked = await s.page.evaluate("""
            () => {
                let count = 0;
                const sels = [
                    'div[role="button"]:has-text("ดูความคิดเห็นเพิ่มเติม")',
                    'div[role="button"]:has-text("View more comments")',
                    'div[role="button"]:has-text("ดูการตอบกลับ")',
                    'div[role="button"]:has-text("View more replies")',
                    'div[role="button"]:has-text("ดูความคิดเห็นก่อนหน้า")',
                    'div[role="button"]:has-text("View previous comments")'
                ];
                for (const sel of sels) {
                    document.querySelectorAll(sel).forEach(b => {
                        try {
                            const r = b.getBoundingClientRect();
                            if (r.height > 0) { b.click(); count++; }
                        } catch(e) {}
                    });
                }
                return count;
            }
        """)
        print(f"expand round {round_no}: clicked {clicked} buttons")
        if clicked == 0:
            break
        await asyncio.sleep(2.5)

    await asyncio.sleep(3)

    result = await s.page.evaluate("""
        ([T1_ID, SEARCH_TEXT]) => {
            const outs = [];
            const articles = document.querySelectorAll('div[role="article"]');
            // Find the SMALLEST article (deepest) containing our text = our T2 reply itself
            for (let i = 0; i < articles.length; i++) {
                const art = articles[i];
                const t = (art.textContent || '').replace(/\\s+/g, ' ');
                if (!t.includes(SEARCH_TEXT)) continue;
                const l = art.querySelector('a[href*="comment_id="]');
                const m = l ? (l.href.match(/comment_id=(\\d+)/) || [])[1] : null;
                const r = art.getBoundingClientRect();
                // walk UP to find enclosing T1 article
                let p = art.parentElement;
                let t1Info = 'NONE';
                while (p && p !== document.body) {
                    if (p.getAttribute && p.getAttribute('role') === 'article' && p !== art) {
                        const pl = p.querySelector('a[href*="comment_id="]');
                        const pm = pl ? (pl.href.match(/comment_id=(\\d+)/) || [])[1] : null;
                        t1Info = 'enclosing-article-id=' + pm;
                        break;
                    }
                    p = p.parentElement;
                }
                outs.push('article[' + i + '] h=' + Math.round(r.height)
                    + ' own-id=' + m + ' | nesting: ' + t1Info
                    + ' | text="' + t.slice(0, 80) + '"');
            }
            if (outs.length === 0) outs.push('NOT FOUND: ' + SEARCH_TEXT);
            return outs.join('\\n');
        }
    """, [T1_ID, SEARCH_TEXT])
    print(result)
    await s.close()

asyncio.run(main())