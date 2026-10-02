"""Inspect the reply dialog layout around the textbox to find the submit button."""
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

    # Focus the box in the visible dialog that has aria-label containing "ตอบกลับในชื่อ"
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
            return 'focused: ' + (box.getAttribute('aria-label') || '');
        }
    """)
    print("Focused:", focused)

    await s.page.keyboard.type("TEST_SUBMIT_0918", delay=30)
    await s.page.wait_for_timeout(800)

    # Inspect: from the textbox, look at nearby buttons (siblings, parent's buttons)
    info = await s.page.evaluate("""
        () => {
            const outs = [];
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            let last = null;
            for (const d of dialogs) {
                if (d.offsetParent !== null) last = d;
            }
            if (!last) return ['no visible dialog'];
            const box = last.querySelector('div[contenteditable="true"][role="textbox"]');
            if (!box) return ['no box'];
            
            // Walk up 4 levels and collect role=button descendants at each level
            let node = box;
            for (let lvl = 0; lvl < 5 && node; lvl++) {
                node = node.parentElement;
                if (!node) break;
                const btns = Array.from(node.querySelectorAll('div[role="button"], button')).filter(b => b.offsetParent !== null);
                const interesting = [];
                btns.forEach(b => {
                    const t = (b.textContent || '').trim();
                    const aria = b.getAttribute('aria-label') || '';
                    const disabled = b.getAttribute('aria-disabled');
                    if ((t.length > 0 && t.length <= 20) || aria) {
                        interesting.push('text="' + t + '" aria="' + aria + '" disabled=' + disabled);
                    }
                });
                if (interesting.length) {
                    outs.push('Level ' + lvl + ' (tag=' + node.tagName + '):');
                    interesting.forEach(x => outs.push('  ' + x));
                }
            }
            return outs;
        }
    """)
    print("Around textbox:\n" + '\n'.join(info))
    await s.close()

asyncio.run(main())