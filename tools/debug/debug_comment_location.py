"""Thorough debug: where is the comment link, and which articles contain it."""
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
            const outs = [];
            
            // 1. All links matching our comment ID
            const links = document.querySelectorAll('a[href*="comment_id="][href*="' + commentId + '"]');
            outs.push('=== Links for comment ' + commentId + ': ' + links.length);
            links.forEach((l, i) => {
                const vis = l.offsetParent !== null;
                // Walk up to nearest article
                let cur = l, art = null, artDepth = 0;
                while (cur && cur !== document.body) {
                    if (cur.getAttribute && cur.getAttribute('role') === 'article') { art = cur; break; }
                    cur = cur.parentElement;
                    artDepth++;
                }
                let artVis = art ? art.offsetParent !== null : 'no-art';
                let replyCount = 0;
                if (art) {
                    art.querySelectorAll('div[role="button"], button').forEach(b => {
                        const t = (b.textContent || '').trim();
                        if ((t === 'ตอบกลับ' || t === 'Reply') && b.offsetParent !== null) replyCount++;
                    });
                }
                const rect = l.getBoundingClientRect();
                outs.push('  [' + i + '] linkVisible=' + vis + ' y=' + Math.round(rect.y) + ' articleVisible=' + artVis + ' artDepth=' + artDepth + ' visibleReplyBtns=' + replyCount);
            });
            
            // 2. List all articles on page with visibility and reply button info
            outs.push('\\n=== All articles ===');
            const arts = document.querySelectorAll('div[role="article"]');
            arts.forEach((a, i) => {
                const r = a.getBoundingClientRect();
                const vis = a.offsetParent !== null;
                let replyTotal = 0, replyVisible = 0;
                a.querySelectorAll('div[role="button"], button').forEach(b => {
                    const t = (b.textContent || '').trim();
                    if (t === 'ตอบกลับ' || t === 'Reply') {
                        replyTotal++;
                        if (b.offsetParent !== null) replyVisible++;
                    }
                });
                // Does it contain ANY of our links?
                let contains = 0;
                links.forEach(l => { if (a.contains(l)) contains++; });
                const text = (a.textContent || '').replace(/\\s+/g, ' ').slice(0, 35);
                outs.push('  [' + i + '] vis=' + vis + ' y=' + Math.round(r.y) + ' h=' + Math.round(r.height) + ' reply=' + replyTotal + '/' + replyVisible + ' containsLink=' + contains + ' :: ' + text);
            });
            
            // 3. Check scrollable containers - find the comment list scroll area
            outs.push('\\n=== Scroll containers ===');
            const scrollers = document.querySelectorAll('[style*="overflow"]');
            let sc = 0;
            scrollers.forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.height > 400 && r.height < 3000 && el.offsetParent !== null && el.scrollHeight > r.height) {
                    sc++;
                    if (sc <= 5) {
                        const cls = String(el.className || '').slice(0, 50);
                        outs.push('  scroller: scrollH=' + el.scrollHeight + ' clientH=' + Math.round(r.height) + ' class=' + cls);
                    }
                }
            });
            outs.push('  total scrollable containers: ' + sc);
            
            return outs.join('\\n');
        }
    """, COMMENT_ID_T1)
    print(result)
    await s.close()

asyncio.run(main())