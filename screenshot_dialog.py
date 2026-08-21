"""Open reply dialog, type message, take screenshot to see the actual UI."""
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
    await s.page.keyboard.type("TEST_DIALOG_0916", delay=40)
    await s.page.wait_for_timeout(1000)

    # Save screenshot of the whole page (dialog visible)
    await s.page.screenshot(path="screenshots/dialog_with_text.png", full_page=False)
    print("Screenshot saved: screenshots/dialog_with_text.png")

    # Also screenshot just the dialog element
    shot = await s.page.evaluate("""
        () => {
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            for (const d of dialogs) {
                if (d.offsetParent !== null) {
                    const r = d.getBoundingClientRect();
                    return {x: r.x, y: r.y, w: r.width, h: r.height};
                }
            }
            return null;
        }
    """)
    print("Dialog rect:", shot)
    if shot:
        await s.page.screenshot(path="screenshots/dialog_crop.png", clip={"x": shot['x'], "y": shot['y'], "width": shot['w'], "height": shot['h']})
        print("Cropped screenshot saved: screenshots/dialog_crop.png")

    await s.close()

asyncio.run(main())