"""Test the NEW _verify_reply_in_dom JS logic against the real page DOM.

The reply from V4 attempt 3 is still on the post, so if the new logic
returns success here, the fix works.
"""

import asyncio
import json

from playwright.async_api import async_playwright

REPLY_TEXT = "ขอบคุณสำหรับความคิดเห็นครับ"
POST_URL = "https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806"

# EXACT copy of the JS inside _verify_reply_in_dom (facebook.py)
VERIFY_JS = """
() => {
    try {
        const needle = replyMessage.substring(0, 20);
        const vis = (el) => {
            const r = el.getBoundingClientRect();
            return r.height > 0 && r.width > 0;
        };
        const leaves = document.querySelectorAll('div, span');
        let nestedHit = false;
        let articleHit = 0;
        for (const el of leaves) {
            if (el.childElementCount !== 0) continue;
            if (!vis(el)) continue;
            if (el.isContentEditable || el.closest('[contenteditable="true"]')) continue;
            const txt = el.innerText || '';
            if (!txt.includes(needle)) continue;
            const art = el.closest('div[role="article"]');
            if (!art) continue;
            articleHit++;
            let p = art.parentElement;
            while (p) {
                if (p.getAttribute && p.getAttribute('role') === 'article' && vis(p)) {
                    nestedHit = true;
                    break;
                }
                p = p.parentElement;
            }
            if (nestedHit) break;
        }
        if (nestedHit) return { success: true, mode: 'nested_article' };
        if (articleHit > 0) return { success: true, mode: 'article_text', count: articleHit };
        return { success: false, error: 'reply_text_not_found' };
    } catch (e) {
        return { success: false, error: e.toString() };
    }
}
"""


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state="session/fb_session.json",
            viewport={"width": 1440, "height": 900},
            locale="th-TH",
        )
        page = await context.new_page()
        await page.goto(POST_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)

        # Run the exact verify logic
        result = await page.evaluate(
            VERIFY_JS.replace("() => {", "() => {\n const replyMessage = %s;" % json.dumps(REPLY_TEXT)),
        )
        print("NEW verify logic:", json.dumps(result, ensure_ascii=False))

        # Negative control: a text that does NOT exist must fail
        neg = await page.evaluate(
            VERIFY_JS.replace("() => {", "() => {\n const replyMessage = 'NO_SUCH_TEXT_XYZ';"),
        )
        print("Negative control :", json.dumps(neg, ensure_ascii=False))

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
