"""Inspect submit approach: after typing in reply dialog, what happens on Enter vs button click?"""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper
import logging
logging.basicConfig(level=logging.WARNING)

COMMENT_ID_T1 = "3410792339082758"  # TEST_AUTO_REPLY_160510

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

    # Find the LAST visible dialog's box and type
    typed = await s.page.evaluate("""
        () => {
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            let lastVisible = null;
            for (const d of dialogs) {
                if (d.offsetParent !== null) lastVisible = d;
            }
            if (!lastVisible) return 'no visible dialog';
            const box = lastVisible.querySelector('div[contenteditable="true"][role="textbox"]');
            if (!box) return 'no box in dialog';
            box.focus();
            return 'focused box in last dialog';
        }
    """)
    print("Box:", typed)

    # Type using keyboard
    msg = "TEST_REPLY_BTN_0919"
    await s.page.keyboard.type(msg, delay=30)
    await s.page.wait_for_timeout(800)

    # Inspect dialog buttons AFTER typing (submit button becomes enabled)
    buttons_info = await s.page.evaluate("""
        () => {
            const outs = [];
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            let lastVisible = null;
            for (const d of dialogs) {
                if (d.offsetParent !== null) lastVisible = d;
            }
            if (!lastVisible) return ['no visible dialog'];
            const btns = lastVisible.querySelectorAll('div[role="button"], button, [aria-label]');
            btns.forEach((b, j) => {
                const t = (b.textContent || '').trim().slice(0, 40);
                const aria = b.getAttribute('aria-label') || '';
                const dir = b.getAttribute('dir') || '';
                const visible = b.offsetParent !== null;
                const tag = b.tagName;
                // Submit buttons usually have dir=auto and short text like "Post", "Comment", "ตอบกลับ", "ส่ง"
                if ((t || aria) && visible && t.length < 25) {
                    outs.push('  <' + tag + '> text="' + t + '" aria="' + aria + '" dir="' + dir + '"');
                }
            });
            return outs;
        }
    """)
    print("Buttons after typing:\n" + '\n'.join(buttons_info))

    await s.close()

asyncio.run(main())