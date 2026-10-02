"""Find the actual submit button near the reply box in the dialog."""
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

    # Click reply button on the T1 comment
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
    await s.page.wait_for_timeout(2000)

    # Focus text box and type
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
            box.textContent = 'TEST_SUBMIT_0916';
            // Dispatch input event so Facebook knows text was entered
            box.dispatchEvent(new Event('input', { bubbles: true }));
            return 'ok';
        }
    """)
    print("Focused:", focused)
    await s.page.wait_for_timeout(1500)

    # Now scan ALL elements near the text box in the dialog - look for "โพสต์", "Post", blue buttons, etc.
    result = await s.page.evaluate("""
        () => {
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            let last = null;
            for (const d of dialogs) {
                if (d.offsetParent !== null) last = d;
            }
            if (!last) return 'no dialog';
            
            const box = last.querySelector('div[contenteditable="true"][role="textbox"]');
            if (!box) return 'no box in dialog';
            
            const boxRect = box.getBoundingClientRect();
            const outs = [];
            outs.push('Box at: y=' + Math.round(boxRect.y) + ' h=' + Math.round(boxRect.height));
            
            // 1. Look for "โพสต์" or "Post" text anywhere in dialog
            const all = last.querySelectorAll('*');
            for (const el of all) {
                const t = (el.textContent || '').trim();
                if (t === 'โพสต์' || t === 'Post' || t === 'ส่ง' || t === 'Submit') {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        const tag = el.tagName;
                        const role = el.getAttribute('role') || '';
                        const cls = String(el.className || '').slice(0, 60);
                        outs.push('FOUND: tag=' + tag + ' role="' + role + '" text="' + t + '" at y=' + Math.round(r.y) + ' w=' + Math.round(r.width) + 'h=' + Math.round(r.height) + ' class=' + cls);
                    }
                }
            }
            
            // 2. Find all elements within 200px below the box (submit area)
            const belowY = boxRect.y + boxRect.height;
            const submitArea = belowY + 200;
            outs.push('\\nElements near box (y=' + Math.round(belowY) + ' to ' + Math.round(submitArea) + '):');
            let found = 0;
            for (const el of all) {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && r.y >= belowY - 10 && r.y <= submitArea && r.y > boxRect.y) {
                    const tag = el.tagName;
                    const role = el.getAttribute('role') || '';
                    const aria = el.getAttribute('aria-label') || '';
                    const t = (el.textContent || '').trim().slice(0, 40);
                    const cls = String(el.className || '').slice(0, 40);
                    // Only show clickable/interactive elements
                    if (role || tag === 'BUTTON' || tag === 'A' || tag === 'svg' || t) {
                        found++;
                        if (found <= 30) {
                            outs.push('  [' + found + '] tag=' + tag + ' role="' + role + '" text="' + t + '" aria="' + aria + '" y=' + Math.round(r.y) + ' class=' + cls);
                        }
                    }
                }
            }
            outs.push('  Total interactive near box: ' + found);
            
            return outs.join('\\n');
        }
    """)
    print(result)

    await s.close()

asyncio.run(main())