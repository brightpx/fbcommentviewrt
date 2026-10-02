"""E2E fast-path test: post a comment from a SECOND browser (like another user)
while the production monitor is running, then record the submit wall-clock time.

The monitor terminal output is checked separately for the DETECTED line.
"""

import asyncio
import json
import time
from datetime import datetime

from playwright.async_api import async_playwright

POST_URL = "https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806"
TEST_MSG = f"TEST_REMOTE_V7_{datetime.now().strftime('%H%M%S')}"
RESULT_FILE = "remote_post_result.json"

# EXACT copy of production _find_visible_comment_box logic (validated in V5 E2E)
FIND_BOX_JS = """
() => {
    const sels = [
        'div[aria-label*="Write a comment"]',
        'div[aria-label*="เขียนความคิดเห็น"]',
        'div[aria-label*="ความคิดเห็น"]',
        'div[contenteditable="true"][role="textbox"]',
        'div[data-lexical-editor="true"]',
    ];
    const isVisible = (el) => {
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        return el.offsetParent !== null || el.getClientRects().length > 0;
    };
    const candidates = [];
    for (const sel of sels) {
        for (const el of document.querySelectorAll(sel)) {
            if (!isVisible(el)) continue;
            const ce = el.getAttribute('contenteditable');
            const role = el.getAttribute('role');
            if (ce !== 'true' && role !== 'textbox') continue;
            const rect = el.getBoundingClientRect();
            candidates.push({
                el,
                inDialog: !!el.closest('div[role="dialog"]'),
                area: rect.width * rect.height,
            });
        }
    }
    if (candidates.length === 0) return false;
    candidates.sort((a, b) => (b.inDialog - a.inDialog) || (a.area - b.area));
    candidates[0].el.setAttribute('data-comment-box-marker', '1');
    return true;
}
"""


async def main() -> None:
    results = {"test_msg": TEST_MSG, "posted": False, "poster_echo": False}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state="session/fb_session.json",
            viewport={"width": 1920, "height": 1080},
            locale="th-TH",
        )
        page = await context.new_page()
        print(f"[POST] Opening post... msg={TEST_MSG}")
        await page.goto(POST_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)

        editable = None
        elapsed = 0
        while elapsed < 15000:
            marked = await page.evaluate(FIND_BOX_JS)
            if marked:
                editable = await page.query_selector('[data-comment-box-marker="1"]')
                if editable:
                    break
            await page.wait_for_timeout(400)
            elapsed += 400
        if not editable:
            print("[POST] FAILED: comment box never appeared")
            await page.screenshot(path="screenshots/remote_no_box.png")
            with open(RESULT_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False)
            await browser.close()
            return

        await editable.scroll_into_view_if_needed()
        await editable.click(force=True)
        await page.wait_for_timeout(800)
        await editable.type(TEST_MSG, delay=30)
        await page.wait_for_timeout(500)

        t_submit = time.time()
        await page.keyboard.press("Enter")
        results["submit_wall"] = t_submit
        results["submit_iso"] = datetime.fromtimestamp(t_submit).strftime("%H:%M:%S.%f")[:-3]
        results["posted"] = True
        print(f"[POST] Enter pressed at {results['submit_iso']} (t0)")

        for _ in range(15):
            echo = await page.evaluate(
                "(needle) => document.body.innerText.includes(needle)", TEST_MSG)
            if echo:
                results["poster_echo"] = True
                break
            await page.wait_for_timeout(1000)
        print(f"[POST] Echo in own DOM: {results['poster_echo']}")

        await browser.close()

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
    print(f"[POST] Done. Result written to {RESULT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
