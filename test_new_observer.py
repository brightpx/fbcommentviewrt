"""One-shot validation of the rewritten broad MutationObserver.

Extracts the EXACT observer JS from app/monitor/owner_detector.py, installs it
in a real Chromium page, then simulates BOTH Facebook insertion styles:
  1. Measured style: plain DIV wrapper + characterData fill (no article node)
  2. Legacy style: div[role=article] with a comment_id link
"""
import asyncio
import re

from playwright.async_api import async_playwright

SRC = open("app/monitor/owner_detector.py", encoding="utf-8").read()
m = re.search(r'await self\.page\.evaluate\("""\n(.*?)"""\)', SRC, re.S)
assert m, "observer JS not found in source"
# The file stores the JS as a Python string literal, so '\\d' on disk means
# '\d' at runtime - unescape before sending to the browser.
OBSERVER_JS = m.group(1).replace("\\\\", "\\")


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content('<div id="feed"><div role="article">old</div></div>')
        await page.evaluate(OBSERVER_JS)  # install the production observer verbatim

        # Style 1 (measured): plain DIV + text fill - no article, no link
        await page.evaluate("""
            () => {
                const d = document.createElement('div');
                d.textContent = 'plain wrapper';
                document.getElementById('feed').appendChild(d);
            }
        """)
        await page.wait_for_timeout(200)
        act = await page.evaluate("() => window.__feedActivity")
        ids = await page.evaluate(
            "() => { const i = window.__newCommentIds; window.__newCommentIds = []; return i; }")
        print(f"plain-DIV insert : activity={act} article-ids={ids}")

        # Style 2 (legacy): real article node with comment_id link
        await page.evaluate("""
            () => {
                const a = document.createElement('div');
                a.setAttribute('role', 'article');
                a.innerHTML = '<a href="https://facebook.com/x?comment_id=999">c</a>';
                document.getElementById('feed').appendChild(a);
            }
        """)
        await page.wait_for_timeout(200)
        act2 = await page.evaluate("() => window.__feedActivity")
        ids2 = await page.evaluate(
            "() => { const i = window.__newCommentIds; window.__newCommentIds = []; return i; }")
        print(f"article insert   : activity={act2} article-ids={ids2}")

        assert act >= 1 and not ids, "plain DIV must bump activity, extract no IDs"
        assert act2 >= 1 and ids2 == ["999"], "article path must still extract IDs"
        print("OK: observer catches BOTH insertion styles")
        await browser.close()


asyncio.run(main())
