"""Diagnostic: dump all elements whose text mentions sort-mode labels,
including their geometry and why they are (in)visible."""
import asyncio
import sys

import yaml
from playwright.async_api import async_playwright


async def main() -> None:
    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    url = cfg["target"]["post_url"]

    labels = ["\u0e40\u0e01\u0e35\u0e48\u0e22\u0e27\u0e02\u0e49\u0e2d\u0e07\u0e21\u0e32\u0e01\u0e17\u0e35\u0e48\u0e2a\u0e38\u0e14",
              "\u0e04\u0e27\u0e32\u0e21\u0e40\u0e01\u0e35\u0e48\u0e22\u0e27\u0e02\u0e49\u0e2d\u0e07\u0e21\u0e32\u0e01\u0e17\u0e35\u0e48\u0e2a\u0e38\u0e14",
              "\u0e43\u0e2b\u0e21\u0e48\u0e25\u0e48\u0e32\u0e2a\u0e38\u0e14",
              "Most relevant", "Most recent"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(storage_state="session/fb_session.json")
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(12000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(4000)

        rows = await page.evaluate(
            """(labels) => {
                const out = [];
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                let el;
                while ((el = walker.nextNode())) {
                    // Only leaf-ish elements to avoid huge containers
                    if (el.children.length > 3) continue;
                    const text = (el.textContent || '').trim();
                    if (!text || text.length > 80) continue;
                    if (!labels.some(l => text.includes(l))) continue;
                    const r = el.getBoundingClientRect();
                    let hiddenBy = null;
                    let cur = el;
                    while (cur && cur !== document.body) {
                        const s = getComputedStyle(cur);
                        if (s.display === 'none') { hiddenBy = 'display:none @' + cur.tagName + '.' + (cur.className || '').toString().slice(0, 30); break; }
                        if (s.visibility === 'hidden') { hiddenBy = 'visibility:hidden @' + cur.tagName; break; }
                        cur = cur.parentElement;
                    }
                    out.push({
                        tag: el.tagName,
                        role: el.getAttribute('role'),
                        aria: el.getAttribute('aria-label'),
                        text: text.slice(0, 60),
                        w: Math.round(r.width), h: Math.round(r.height),
                        hiddenBy
                    });
                }
                return out;
            }""",
            labels,
        )
        print(f"Found {len(rows)} elements mentioning sort labels:")
        for row in rows:
            print(" ", row)
        await browser.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
