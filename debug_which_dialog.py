"""Which dialog hosts the VISIBLE comment links? Identify which dialogs to keep vs close."""
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
    await asyncio.sleep(6)

    result = await s.page.evaluate("""
        (commentId) => {
            const outs = [];
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            outs.push('Total dialogs: ' + dialogs.length);
            
            dialogs.forEach((d, i) => {
                const r = d.getBoundingClientRect();
                const vis = d.offsetParent !== null;
                
                // Count VISIBLE comment links inside this dialog (height > 0)
                let visLinks = 0, totalLinks = 0, targetLinks = 0;
                const links = d.querySelectorAll('a[href*="comment_id="]');
                totalLinks = links.length;
                links.forEach(l => {
                    const lr = l.getBoundingClientRect();
                    if (lr.height > 0) visLinks++;
                    if (l.getAttribute('href').includes(commentId)) targetLinks++;
                });
                
                // Count visible articles
                let visArticles = 0;
                d.querySelectorAll('div[role="article"]').forEach(a => {
                    if (a.getBoundingClientRect().height > 0) visArticles++;
                });
                
                const hasBox = !!d.querySelector('div[contenteditable="true"][role="textbox"]');
                outs.push('[' + i + '] vis=' + vis + ' x=' + Math.round(r.x) + ' y=' + Math.round(r.y) + ' w=' + Math.round(r.width) + ' h=' + Math.round(r.height));
                outs.push('    links=' + totalLinks + ' visibleLinks=' + visLinks + ' targetLinks=' + targetLinks + ' visArticles=' + visArticles + ' hasBox=' + hasBox);
            });
            
            // Also: is our target comment link among the visible links?
            const allTargetLinks = document.querySelectorAll('a[href*="comment_id="][href*="' + commentId + '"]');
            outs.push('\\nTarget comment links (all DOM): ' + allTargetLinks.length);
            allTargetLinks.forEach((l, i) => {
                const lr = l.getBoundingClientRect();
                // Find which dialog contains it
                let inDialog = 'none';
                dialogs.forEach((d, di) => { if (d.contains(l)) inDialog = 'dialog[' + di + ']'; });
                outs.push('  [' + i + '] h=' + Math.round(lr.height) + ' y=' + Math.round(lr.y) + ' in=' + inDialog);
            });
            
            return outs.join('\\n');
        }
    """, COMMENT_ID_T1)
    print(result)
    await s.close()

asyncio.run(main())