"""Debug: find where the reply button is relative to the comment article structure."""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper
import logging
logging.basicConfig(level=logging.WARNING)

COMMENT_ID_T1 = "3410792339082758"

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(5)

    result = await s.page.evaluate("""
        (commentId) => {
            const link = document.querySelector('a[href*="comment_id="][href*="' + commentId + '"]');
            if (!link) return 'NO LINK FOUND';
            
            const outs = [];
            outs.push('Link href: ' + link.href.slice(0, 120));
            
            // Walk up from link, collect article chain with depth info
            let current = link;
            let depth = 0;
            while (current && current.tagName !== 'BODY' && depth < 12) {
                const role = current.getAttribute ? current.getAttribute('role') : null;
                if (role === 'article') {
                    let replyCount = 0;
                    let replyTexts = [];
                    const btns = current.querySelectorAll('div[role="button"], button');
                    for (const b of btns) {
                        const t = (b.textContent || '').trim();
                        if (t === 'ตอบกลับ' || t === 'Reply') replyCount++;
                        if (replyCount <= 6 && (t === 'ตอบกลับ' || t === 'Reply')) {
                            replyTexts.push('visible=' + (b.offsetParent !== null));
                        }
                    }
                    const cls = String(current.className || '').slice(0, 50);
                    const rect = current.getBoundingClientRect();
                    outs.push('article depth=' + depth + ' replyBtns=' + replyCount + ' visible=' + (current.offsetParent !== null) + ' y=' + Math.round(rect.y) + ' h=' + Math.round(rect.height) + ' class=' + cls);
                }
                current = current.parentElement;
                depth++;
            }
            
            // Also list ALL articles on the page with their first 40 chars
            outs.push('\\n-- All articles --');
            const arts = document.querySelectorAll('div[role="article"]');
            arts.forEach((a, i) => {
                const t = (a.textContent || '').replace(/\\s+/g, ' ').slice(0, 40);
                const r = a.getBoundingClientRect();
                let rb = 0;
                a.querySelectorAll('div[role="button"], button').forEach(b => {
                    const bt = (b.textContent || '').trim();
                    if (bt === 'ตอบกลับ' || bt === 'Reply') rb++;
                });
                outs.push('[' + i + '] y=' + Math.round(r.y) + ' h=' + Math.round(r.height) + ' replyBtns=' + rb + ' :: ' + t);
            });
            
            return outs.join('\\n');
        }
    """, COMMENT_ID_T1)
    print(result)
    await s.close()

asyncio.run(main())