"""Inspect the reply dialog: does its editable box belong to the target comment?"""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper

COMMENT_ID_T1 = "3410792339082758"  # TEST_AUTO_REPLY_160510 (T1 - owner comment)

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

    # Inspect dialogs in detail
    info = await s.page.evaluate("""
        (commentId) => {
            const outs = [];
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            outs.push('Dialogs found: ' + dialogs.length);
            dialogs.forEach((d, i) => {
                const visible = d.offsetParent !== null;
                const cls = (d.className || '').slice(0, 50);
                outs.push('  dialog[' + i + '] visible=' + visible + ' class=' + cls);
                
                const box = d.querySelector('div[contenteditable="true"][role="textbox"]');
                if (box) {
                    const aria = box.getAttribute('aria-label') || 'none';
                    const boxCls = (box.className || '').slice(0, 60);
                    outs.push('    box aria="' + aria + '" class=' + boxCls);
                    // Does the dialog contain the comment link?
                    const hasLink = d.querySelector('a[href*="comment_id="][href*="' + commentId + '"]');
                    outs.push('    dialog contains target comment link: ' + !!hasLink);
                    // Does the dialog contain ANY comment link?
                    const anyLink = d.querySelector('a[href*="comment_id="]');
                    outs.push('    dialog contains ANY comment link: ' + !!anyLink);
                    // What about the comment author name?
                    const text = d.textContent.slice(0, 200).replace(/\\n/g, ' | ');
                    outs.push('    dialog preview text: ' + text);
                }
            });
            return outs;
        }
    """, COMMENT_ID_T1)
    print('\n'.join(info))
    await s.close()

asyncio.run(main())