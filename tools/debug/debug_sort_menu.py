"""Diagnostic: click the sort trigger exactly like the scraper does, then dump
everything that appears (menus, dialogs, any element mentioning recent/new)."""
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
        await page.wait_for_timeout(12000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(4000)

        # Mark + click trigger center (same as scraper)
        box = await page.evaluate(
            """(labels) => {
                const candidates = document.querySelectorAll(
                    'div[role="button"], span[role="button"], [aria-haspopup="menu"]'
                );
                let best = null;
                for (const el of candidates) {
                    const text = (el.textContent || '').trim();
                    if (!text || text.length > 60) continue;
                    if (!labels.some(l => text === l || text.endsWith(' ' + l))) continue;
                    const r = el.getBoundingClientRect();
                    if (r.height <= 0 || r.width <= 0) continue;
                    const s = getComputedStyle(el);
                    if (s.visibility === 'hidden' || s.display === 'none') continue;
                    if (!best || text.length < (best.textContent || '').trim().length) best = el;
                }
                if (!best) return null;
                best.scrollIntoView({ block: 'center', behavior: 'instant' });
                const r = best.getBoundingClientRect();
                return { x: r.x + r.width / 2, y: r.y + r.height / 2,
                         w: r.width, h: r.height };
            }""",
            ["\u0e40\u0e01\u0e35\u0e48\u0e22\u0e27\u0e02\u0e49\u0e2d\u0e07\u0e21\u0e32\u0e01\u0e17\u0e35\u0e48\u0e2a\u0e38\u0e14",
             "\u0e04\u0e27\u0e32\u0e21\u0e40\u0e01\u0e35\u0e48\u0e22\u0e27\u0e02\u0e49\u0e2d\u0e07\u0e21\u0e32\u0e01\u0e17\u0e35\u0e48\u0e2a\u0e38\u0e14",
             "Most relevant"],
        )
        print("Trigger box:", box)
        if not box:
            print("NO TRIGGER FOUND")
            await browser.close()
            return

        await page.mouse.click(box["x"], box["y"])
        await page.wait_for_timeout(2500)
        await page.screenshot(path="screenshots/debug_after_click.png")

        # Dump menus/dialogs and anything mentioning recent/new keywords
        dump = await page.evaluate(
            """() => {
                const out = { menus: [], dialogs: 0, keywordEls: [] };
                document.querySelectorAll('[role="menu"], [role="dialog"]').forEach(el => {
                    const r = el.getBoundingClientRect();
                    const entry = {
                        role: el.getAttribute('role'),
                        w: Math.round(r.width), h: Math.round(r.height),
                        text: (el.textContent || '').trim().slice(0, 200)
                    };
                    if (el.getAttribute('role') === 'menu') out.menus.push(entry);
                    else out.dialogs++;
                });
                const kws = ['\\u0e43\\u0e2b\\u0e21\\u0e48\\u0e25\\u0e48\\u0e32\\u0e2a\\u0e38\\u0e14', '\\u0e25\\u0e48\\u0e32\\u0e2a\\u0e38\\u0e14', 'Newest', 'Recent', '\\u0e17\\u0e31\\u0e49\\u0e07\\u0e2b\\u0e21\\u0e14'];
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
                let el;
                while ((el = walker.nextNode())) {
                    if (el.children.length > 2) continue;
                    const text = (el.textContent || '').trim();
                    if (!text || text.length > 50) continue;
                    if (!kws.some(k => text.includes(k))) continue;
                    const r = el.getBoundingClientRect();
                    if (r.height <= 0) continue;
                    out.keywordEls.push({
                        tag: el.tagName, role: el.getAttribute('role'),
                        text: text.slice(0, 50),
                        w: Math.round(r.width), h: Math.round(r.height)
                    });
                }
                return out;
            }"""
        )
        print("Menus found:", len(dump["menus"]))
        for m in dump["menus"]:
            print("  MENU:", m)
        print("Dialogs on page:", dump["dialogs"])
        print(f"Keyword elements ({len(dump['keywordEls'])}):")
        for k in dump["keywordEls"][:15]:
            print("  ", k)
        await browser.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
