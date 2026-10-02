"""Test: click Reply on a T1 comment, verify the reply input box lands inside the comment's own article."""
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

    # Step 1: locate comment link and innermost article
    info = await s.page.evaluate("""
        (commentId) => {
            const link = document.querySelector('a[href*="comment_id="][href*="' + commentId + '"]');
            if (!link) return { error: 'link not found' };
            let current = link;
            let container = null;
            while (current && current.tagName !== 'BODY') {
                if (current.getAttribute('role') === 'article') { container = current; break; }
                current = current.parentElement;
            }
            if (!container) return { error: 'no article container' };
            return { found: true };
        }
    """, COMMENT_ID_T1)
    print("Locate:", info)
    if info.get('error'):
        await s.close()
        return

    # Step 2: click the Reply button inside the innermost article
    clicked = await s.page.evaluate("""
        (commentId) => {
            const link = document.querySelector('a[href*="comment_id="][href*="' + commentId + '"]');
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

    # Step 3: after clicking Reply, find where the reply input box is
    info2 = await s.page.evaluate("""
        (commentId) => {
            const outs = [];
            const link = document.querySelector('a[href*="comment_id="][href*="' + commentId + '"]');
            if (!link) return { error: 'link not found after click' };
            let current = link;
            let innerArticle = null;
            while (current && current.tagName !== 'BODY') {
                if (current.getAttribute('role') === 'article') { innerArticle = current; break; }
                current = current.parentElement;
            }
            if (!innerArticle) return { error: 'no container after click' };

            // All contenteditable boxes on page
            const allBoxes = document.querySelectorAll('div[contenteditable="true"][role="textbox"]');
            outs.push('Total editable boxes: ' + allBoxes.length);
            allBoxes.forEach((b, i) => {
                const visible = b.offsetParent !== null;
                const aria = b.getAttribute('aria-label') || 'none';
                const inInner = innerArticle.contains(b);
                outs.push('  box[' + i + '] visible=' + visible + ' aria="' + aria + '" insideInnerArticle=' + inInner);
            });

            // Also check dialog
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            outs.push('Dialogs: ' + dialogs.length);
            dialogs.forEach((d, i) => {
                const boxInDialog = d.querySelector('div[contenteditable="true"]');
                outs.push('  dialog[' + i + '] hasEditable=' + (!!boxInDialog) + ' visible=' + (d.offsetParent !== null));
            });
            return outs;
        }
    """, COMMENT_ID_T1)
    print("After click:", info2)

    await s.close()

asyncio.run(main())