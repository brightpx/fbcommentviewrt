"""Find the submit button: scan the ENTIRE visible dialog after typing for enabled submit buttons."""
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

    # Click reply
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

    # Type in the box
    focused = await s.page.evaluate("""
        () => {
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            let last = null;
            for (const d of dialogs) {
                if (d.offsetParent !== null) last = d;
            }
            if (!last) return 'no visible dialog';
            const box = last.querySelector('div[contenteditable="true"][role="textbox"]');
            if (!box) return 'no box';
            box.focus();
            return 'ok';
        }
    """)
    print("Focused:", focused)
    await s.page.keyboard.type("TEST_SUBMIT_0917", delay=30)
    await s.page.wait_for_timeout(1000)

    # Now scan ALL elements in the dialog for anything that looks like a submit button
    # (enabled, visible, short label, blue-ish)
    info = await s.page.evaluate("""
        () => {
            const outs = [];
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            let last = null;
            for (const d of dialogs) {
                if (d.offsetParent !== null) last = d;
            }
            if (!last) return ['no visible dialog'];
            
            // ALL visible buttons in the dialog
            const all = last.querySelectorAll('div[role="button"], button, [role="button"] a span');
            all.forEach((b, j) => {
                if (b.offsetParent === null) return;
                const text = (b.textContent || '').trim();
                const aria = b.getAttribute('aria-label') || '';
                const ariaDisabled = b.getAttribute('aria-disabled');
                const cls = (b.className || '').slice(0, 40);
                // Focus on short text or aria
                if ((text && text.length <= 20) || aria) {
                    outs.push('[' + j + '] tag=' + b.tagName + ' text="' + text + '" aria="' + aria + '" ariadisabled=' + ariaDisabled);
                }
            });
            return outs;
        }
    """)
    print("ALL dialog buttons:\n" + '\n'.join(info))
    await s.close()

asyncio.run(main())