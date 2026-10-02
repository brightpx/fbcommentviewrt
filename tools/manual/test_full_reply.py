"""Test: Click Reply, type in dialog, post, and verify it becomes T2 nested reply."""
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

    # Step 1: Click Reply button
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

    # Step 2: Find the visible dialog reply box
    box_found = await s.page.evaluate("""
        () => {
            const dialogs = document.querySelectorAll('div[role="dialog"]');
            for (const d of dialogs) {
                if (d.offsetParent === null) continue;
                const box = d.querySelector('div[contenteditable="true"][role="textbox"]');
                if (box && box.offsetParent !== null) {
                    box.focus();
                    return 'found dialog box: ' + (box.getAttribute('aria-label') || '');
                }
            }
            return 'no dialog box found';
        }
    """)
    print("Box:", box_found)

    # Step 3: Type the message in the dialog box
    msg = "TEST_AUTO_REPLY_0921"
    await s.page.keyboard.type(msg, delay=50)
    await s.page.wait_for_timeout(500)

    # Step 4: Press Enter
    await s.page.keyboard.press('Enter')
    print("Enter pressed, waiting for post...")
    await s.page.wait_for_timeout(3000)

    await s._take_screenshot("after_reply_post")
    print("Screenshot saved: after_reply_post")

    # Step 5: Refresh and check if the reply appears as T2
    await s.page.reload()
    await s.page.wait_for_load_state('networkidle')
    await asyncio.sleep(4)

    # Check our test comment's replies
    result = await s.page.evaluate("""
        (commentId) => {
            const link = document.querySelector('a[href*="comment_id="][href*="' + commentId + '"]');
            if (!link) return 'comment link not found';
            let current = link;
            let container = null;
            while (current && current.tagName !== 'BODY') {
                if (current.getAttribute('role') === 'article') { container = current; break; }
                current = current.parentElement;
            }
            if (!container) return 'no container';
            
            const outs = [];
            // Count all articles inside this container (nested replies)
            const nestedArticles = container.querySelectorAll('div[role="article"]');
            outs.push('Nested articles inside container: ' + nestedArticles.length);
            
            // All comment IDs in this scope
            const ids = [];
            container.querySelectorAll('a[href*="comment_id="]').forEach(a => {
                const m = a.href.match(/comment_id=(\\d+)/);
                if (m) ids.push(m[1]);
            });
            outs.push('Comment IDs: ' + ids.join(', '));
            
            // Text content
            const texts = [];
            container.querySelectorAll('div[dir="auto"]').forEach(d => {
                const t = (d.textContent || '').trim();
                if (t.length > 5 && t.length < 100) texts.push(t);
            });
            outs.push('Texts: ' + texts.join(' | '));
            
            return outs.join('\\n');
        }
    """, COMMENT_ID_T1)
    print("After refresh:", result)

    await s.close()

asyncio.run(main())