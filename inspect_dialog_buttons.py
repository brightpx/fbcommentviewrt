"""Inspect the reply dialog buttons in detail - what submit buttons exist?"""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper

COMMENT_ID_T1 = "3410792339082758"  # TEST_AUTO_REPLY_160510

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(5)

    # Click reply button
    clicked = await s.page.evaluate("""
        (commentId) => {
            const link = document.querySelector('a[href*="comment_id="][href*="' + commentId + '"]');
            if (!link) return 'no link';
            let current = link;
            let container = null;
            while (current && current.tagName !== 'BODY') {
                if (current.getAttribute('role') === 'article') { container = current; break; }
                current = current.parentElement;
            }
            if (!container) return 'no container';
            container.scrollIntoView({ behavior: 'instant', block: 'center' });
            const buttons = container.querySelectorAll('div[role="button"], button');
            for (const btn of buttons) {
                const text = (btn.textContent || '').trim();
                if ((text === 'ตอบกลับ' || text === 'Reply') && btn.offsetParent !== null) {
                    btn.click();
                    return 'clicked';
                }
            }
            return 'no reply btn';
        }
    """, COMMENT_ID_T1)
    print("Reply button:", clicked)

    await s.page.wait_for_timeout(1500)

    # Dump ALL buttons in visible dialogs
    result = await s.page.evaluate("""
        () => {
            const outs = [];
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            dialogs.forEach((d, i) => {
                if (d.offsetParent === null) return;
                outs.push('=== Visible dialog[' + i + '] ===');
                const btns = d.querySelectorAll('div[role="button"], button');
                btns.forEach((b, j) => {
                    const t = (b.textContent || '').trim().slice(0, 50);
                    const aria = b.getAttribute('aria-label') || '';
                    const visible = b.offsetParent !== null;
                    if (t || aria) {
                        outs.push('  btn[' + j + '] text="' + t + '" aria="' + aria + '" visible=' + visible);
                    }
                });
                // Also look for submit-like aria labels
                const ariaBtns = d.querySelectorAll('[aria-label]');
                ariaBtns.forEach((b, j) => {
                    const aria = b.getAttribute('aria-label') || '';
                    if (aria.includes('ตอบ') || aria.includes('Reply') || aria.includes('ส่ง') || aria.includes('โพสต์') || aria.includes('Post') || aria.includes('Submit')) {
                        outs.push('  ARIA btn[' + j + '] aria="' + aria + '" visible=' + (b.offsetParent !== null));
                    }
                });
            });
            return outs.join('\\n');
        }
    """)
    print(result)

    await s.close()

asyncio.run(main())