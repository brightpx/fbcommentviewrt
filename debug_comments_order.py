"""Debug: dump all T1 comments with id, author, timestamp, message in DOM order."""
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

    data = await s.page.evaluate("""
        () => {
            const allArticles = document.querySelectorAll('div[role="article"]');
            const commentArticles = Array.from(allArticles).filter(article => {
                const label = article.getAttribute('aria-label');
                return label && (label.includes('ความคิดเห็นจาก') || label.includes('Comment by'));
            });
            // top-level only
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
                const label = article.getAttribute('aria-label') || '';
                const link = article.querySelector('a[href*="comment_id="]');
                let cid = null;
                if (link) {
                    const rm = link.href.match(/reply_comment_id=(\\d+)/);
                    const cm = link.href.match(/comment_id=(\\d+)/);
                    cid = rm ? rm[1] : (cm ? cm[1] : null);
                }
                const r = article.getBoundingClientRect();
                out.push({
                    i: i,
                    aria: label,
                    id: cid,
                    h: Math.round(r.height),
                    text: article.textContent.replace(/\\s+/g, ' ').slice(0, 60)
                });
            });
            return JSON.stringify(out);
        }
    """)
    import json
    arr = json.loads(data)
    for a in arr:
        print(f"[{a['i']}] id={a['id']} h={a['h']}")
        print(f"    aria=\"{a['aria']}\"")
        print(f"    text=\"{a['text']}\"")
    await s.close()

asyncio.run(main())