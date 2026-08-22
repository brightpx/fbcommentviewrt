"""Probe: open the target post in a FRESH browser and check what Facebook serves.

Ground-truth check independent of the running monitor:
1. Is TEST_AUTOREPLY_E2E_V2 visible?
2. Which comment IDs does a fresh page load see?
3. How many bot replies exist under the first test comment?
"""
import asyncio
import sys

import yaml
from playwright.async_api import async_playwright


async def main() -> None:
    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    url = cfg["target"]["post_url"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(storage_state="session/fb_session.json")
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(15000)

        # Scroll to comments area to force lazy loading
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(4000)

        info = await page.evaluate(
            """() => {
                const out = { t1Ids: [], sortLabel: null, hasV2: false, hasE2E: false };
                out.hasV2 = document.body.innerText.includes('TEST_AUTOREPLY_E2E_V2');
                out.hasE2E = document.body.innerText.includes('TEST_AUTOREPLY_E2E');

                // Same T1 filter as the detector: aria-label comment articles not nested
                const arts = Array.from(document.querySelectorAll('div[role="article"]'));
                const t1 = arts.filter(a => {
                    const label = a.getAttribute('aria-label') || '';
                    if (!(label.includes('\\u0e04\\u0e27\\u0e32\\u0e21\\u0e04\\u0e34\\u0e14\\u0e40\\u0e2b\\u0e47\\u0e19\\u0e08\\u0e32\\u0e01') || label.includes('Comment by'))) return false;
                    let parent = a.parentElement;
                    while (parent) {
                        if (parent !== a && parent.getAttribute('role') === 'article') return false;
                        parent = parent.parentElement;
                    }
                    return true;
                });
                for (const a of t1.slice(0, 15)) {
                    const link = a.querySelector('a[href*="comment_id="]');
                    const m = link ? link.href.match(/comment_id=(\\d+)/) : null;
                    const label = a.getAttribute('aria-label') || '';
                    out.t1Ids.push((m ? m[1] : 'nolink') + ' | ' + label.substring(0, 80));
                }

                // Sort dropdown label
                const sortEl = Array.from(document.querySelectorAll('span, div')).find(e =>
                    e.children.length === 0 && /\\u0e41\\u0e2a\\u0e14\\u0e07\\u0e04\\u0e27\\u0e32\\u0e21\\u0e04\\u0e34\\u0e14\\u0e40\\u0e2b\\u0e47\\u0e19/.test(e.textContent || '')
                );
                out.sortLabel = sortEl ? sortEl.textContent.trim() : null;
                return out;
            }"""
        )

        print("=== PROBE RESULTS ===")
        print("V2 visible:", info["hasV2"])
        print("E2E(v1) visible:", info["hasE2E"])
        print("Sort label:", info["sortLabel"])
        print(f"Top-level comments ({len(info['t1Ids'])}):")
        for row in info["t1Ids"]:
            print("  ", row)

        # Comment count text (e.g. "143 ความคิดเห็น") tells us whether Facebook
        # counts the new comment as published or filtered it out.
        count_text = await page.evaluate(
            """() => {
                const m = document.body.innerText.match(/(\\d+)\\s*\\u0e04\\u0e27\\u0e32\\u0e21\\u0e04\\u0e34\\u0e14\\u0e40\\u0e2b\\u0e47\\u0e19/g);
                return m ? m.slice(-3) : null;
            }"""
        )
        print("Comment count texts:", count_text)

        # Click 'View more comments' up to 3 times, then re-check visibility
        for i in range(3):
            btn = await page.query_selector(
                'div[role="button"]:has-text("\\u0e14\\u0e39\\u0e04\\u0e27\\u0e32\\u0e21\\u0e04\\u0e34\\u0e14\\u0e40\\u0e2b\\u0e47\\u0e19\\u0e40\\u0e1e\\u0e34\\u0e48\\u0e21\\u0e40\\u0e15\\u0e34\\u0e21"), '
                'div[role="button"]:has-text("View more comments")'
            )
            if not btn:
                break
            await btn.click()
            await page.wait_for_timeout(3000)

        body2 = await page.evaluate("() => document.body.innerText")
        print("After expansion -> V2 visible:", "TEST_AUTOREPLY_E2E_V2" in body2)
        print("After expansion -> E2E(v1) visible:", "TEST_AUTOREPLY_E2E" in body2)

        await page.screenshot(path="screenshots/probe_fresh_page.png", full_page=False)
        await browser.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
