"""Find comment ID of TEST_FUNCTION_COMMENT_121602 and reply to it."""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper
import logging
logging.basicConfig(level=logging.INFO)

SEARCH = "TEST_FUNCTION_COMMENT_121602"

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(6)

    # Find all T1 comments with their IDs
    result = await s.page.evaluate("""
        (SEARCH) => {
            const allArticles = document.querySelectorAll('div[role="article"]');
            const commentArticles = Array.from(allArticles).filter(article => {
                const label = article.getAttribute('aria-label');
                return label && (label.includes('ความคิดเห็นจาก') || label.includes('Comment by'));
            });
            const topLevel = commentArticles.filter(article => {
                let parent = article.parentElement;
                while (parent) {
                    if (parent !== article && parent.getAttribute('role') === 'article') return false;
                    parent = parent.parentElement;
                }
                return true;
            });
            const out = [];
            topLevel.forEach((article, i) => {
                const text = (article.textContent || '').replace(/\\s+/g, ' ');
                const link = article.querySelector('a[href*="comment_id="]');
                let cid = null;
                if (link) {
                    const rm = link.href.match(/reply_comment_id=(\\d+)/);
                    const cm = link.href.match(/comment_id=(\\d+)/);
                    cid = rm ? rm[1] : (cm ? cm[1] : null);
                }
                const r = article.getBoundingClientRect();
                out.push({i: i, id: cid, h: Math.round(r.height), text: text.slice(0, 100)});
            });
            return JSON.stringify(out);
        }
    """, [SEARCH])
    import json
    arr = json.loads(result)
    target_id = None
    for a in arr:
        mark = " <===" if SEARCH in a['text'] else ""
        print(f"[{a['i']}] id={a['id']} h={a['h']} text=\"{a['text'][:60]}\"{mark}")
        if SEARCH in a['text']:
            target_id = a['id']

    if not target_id:
        print(f"\nNOT FOUND: {SEARCH} in any T1 comment")
        await s.close()
        return

    print(f"\nFound target comment ID: {target_id}")
    print("Replying to it...")
    ok = await s.reply_to_comment(target_id, "ขอบคุณสำหรับความคิดเห็นครับ")
    print(f"reply_to_comment returned: {ok}")

    await asyncio.sleep(4)
    # Verify
    verify = await s.page.evaluate("""
        (SEARCH) => {
            const articles = document.querySelectorAll('div[role="article"]');
            for (const art of articles) {
                const t = (art.textContent || '').replace(/\\s+/g, ' ');
                if (t.includes(SEARCH) && t.includes('ขอบคุณสำหรับความคิดเห็นครับ')) {
                    return 'T2 reply confirmed under comment containing ' + SEARCH;
                }
            }
            return 'T2 reply not found';
        }
    """, [SEARCH])
    print(f"Verify: {verify}")
    await s.close()

asyncio.run(main())