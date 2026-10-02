"""Deep-dive: find BOTH test comments, walk ancestors, print ALL articles with their comment IDs and reply buttons."""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper

COMMENT_ID_T2 = "3410859655742693"  # TEST_AUTO_REPLY_1730
COMMENT_ID_T1 = "3410792339082758"  # TEST_AUTO_REPLY_160510
COMMENT_ID_BOT = "3410859939075998"  # bot's prior reply

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(5)

    for cid in [COMMENT_ID_T1, COMMENT_ID_T2, COMMENT_ID_BOT]:
        result = await s.page.evaluate("""
            (commentId) => {
                const outs = [];
                const link = document.querySelector('a[href*="comment_id=' + commentId + '"]');
                if (!link) {
                    return '=== ' + commentId + ': COMMENT LINK NOT FOUND ===';
                }
                outs.push('=== ' + commentId + ': found ===');
                
                // All article ancestors
                let current = link;
                let depth = 0;
                const articles = [];
                while (current && current.tagName !== 'BODY' && depth < 40) {
                    if (current.getAttribute('role') === 'article') {
                        articles.push(current);
                    }
                    current = current.parentElement;
                    depth++;
                }
                outs.push('Total article ancestors: ' + articles.length);
                
                articles.forEach((art, i) => {
                    // Comment IDs inside this article
                    const ids = [];
                    art.querySelectorAll('a[href*="comment_id="]').forEach(a => {
                        const m = a.href.match(/comment_id=(\\d+)/);
                        if (m) ids.push(m[1]);
                    });
                    // Reply buttons inside
                    const replyBtns = Array.from(art.querySelectorAll('div[role="button"], button')).filter(b => {
                        const t = (b.textContent || '').trim();
                        return (t === 'ตอบกลับ' || t === 'Reply') && b.offsetParent !== null;
                    }).length;
                    // Contenteditable boxes
                    const boxes = art.querySelectorAll('div[contenteditable="true"]').length;
                    // Depth of this article
                    let d = 0;
                    let p = art;
                    while (p && p.tagName !== 'BODY') { d++; p = p.parentElement; }
                    outs.push('  Article[' + i + '] atDepth=' + d + ' containsIds=[' + ids.join(',') + '] replyBtns=' + replyBtns + ' editableBoxes=' + boxes);
                });
                return outs.join('\\n');
            }
        """, cid)
        print(result)
        print()

    await s.close()

asyncio.run(main())