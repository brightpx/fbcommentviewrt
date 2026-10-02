"""Debug: what dialogs exist on the post page, and what happens when we close them."""
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

    print("=== BEFORE closing any dialog ===")
    result = await s.page.evaluate("""
        () => {
            const outs = [];
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            outs.push('Total dialogs: ' + dialogs.length);
            dialogs.forEach((d, i) => {
                const r = d.getBoundingClientRect();
                const vis = d.offsetParent !== null;
                const title = (d.getAttribute('aria-label') || '');
                const txt = (d.textContent || '').replace(/\\s+/g, ' ').slice(0, 80);
                const hasBox = !!d.querySelector('div[contenteditable="true"][role="textbox"]');
                const commentLinks = d.querySelectorAll('a[href*="comment_id="]').length;
                // find close button
                const closeBtn = d.querySelector('div[aria-label="ปิด"], div[aria-label="Close"]');
                outs.push('[' + i + '] vis=' + vis + ' x=' + Math.round(r.x) + ' y=' + Math.round(r.y) + ' w=' + Math.round(r.width) + ' h=' + Math.round(r.height));
                outs.push('    aria="' + title + '" textbox=' + hasBox + ' commentLinks=' + commentLinks + ' closeBtn=' + (!!closeBtn));
                outs.push('    text: ' + txt);
            });
            // Also count comment links on the page overall and if visible
            const visLinks = Array.from(document.querySelectorAll('a[href*="comment_id="]')).filter(l => l.offsetParent !== null && l.getBoundingClientRect().height > 0);
            outs.push('Visible comment links on whole page: ' + visLinks.length);
            return outs.join('\\n');
        }
    """)
    print(result)

    # Now close ALL visible dialogs (like the code does)
    print("\n=== Closing all visible dialogs ===")
    closed = await s.page.evaluate("""
        () => {
            let count = 0;
            document.querySelectorAll('div[role="dialog"]').forEach(d => {
                if (d.offsetParent !== null) {
                    const closeBtn = d.querySelector('div[aria-label="ปิด"], div[aria-label="Close"], div[aria-label="ปิดหน้าต่าง"]');
                    if (closeBtn) { closeBtn.click(); count++; }
                }
            });
            return count;
        }
    """)
    print("Closed:", closed)
    await asyncio.sleep(1500 / 1000)

    result2 = await s.page.evaluate("""
        () => {
            const outs = [];
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            outs.push('Dialogs after close: ' + dialogs.length);
            const visLinks = Array.from(document.querySelectorAll('a[href*="comment_id="]')).filter(l => l.offsetParent !== null && l.getBoundingClientRect().height > 0);
            outs.push('Visible comment links after close: ' + visLinks.length);
            const arts = document.querySelectorAll('div[role="article"]');
            outs.push('Articles after close: ' + arts.length);
            return outs.join('\\n');
        }
    """)
    print(result2)
    await s.close()

asyncio.run(main())