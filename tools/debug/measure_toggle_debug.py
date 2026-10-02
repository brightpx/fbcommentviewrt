"""Debug WHY the sort-mode toggle fails in the measurement script.

Replicates production conditions step by step with rich diagnostics:
1920x1080 viewport, initial scroll (like navigate_to_post), locate trigger,
click, then dump menu state + screenshots at each step.
"""

import asyncio
from datetime import datetime

from playwright.async_api import async_playwright

POST_URL = "https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}", flush=True)


LOCATE_JS = """(labels) => {
    const out = { all: [], best: null };
    for (const el of document.querySelectorAll('div[role="button"], span[role="button"], [aria-haspopup="menu"]')) {
        const text = (el.textContent || '').trim();
        if (!text || text.length > 60) continue;
        if (!labels.some(l => text === l || text.endsWith(' ' + l))) continue;
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        out.all.push({
            text,
            visible: r.height > 0 && r.width > 0,
            rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
            vis: s.visibility, disp: s.display,
        });
        if (r.height > 0 && r.width > 0 && s.visibility !== 'hidden' && s.display !== 'none') {
            if (!out.best || text.length < (out.best.text || '').length) {
                out.best = { text };
                el.scrollIntoView({ block: 'center', behavior: 'instant' });
                const r2 = el.getBoundingClientRect();
                out.click = { x: r2.x + r2.width / 2, y: r2.y + r2.height / 2 };
            }
        }
    }
    return out;
}"""

MENU_STATE_JS = """() => {
    const menus = [];
    for (const m of document.querySelectorAll('[role="menu"]')) {
        const r = m.getBoundingClientRect();
        menus.push({
            visible: r.width > 0 && r.height > 0,
            items: Array.from(m.querySelectorAll('*'))
                .map(e => (e.textContent || '').trim())
                .filter(t => t && t.length < 40)
                .slice(0, 15),
        });
    }
    return menus;
}"""


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state="session/fb_session.json",
            viewport={"width": 1920, "height": 1080},
            locale="th-TH",
        )
        page = await context.new_page()
        log("Opening post...")
        await page.goto(POST_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)

        # Replicate production initial scroll (navigate_to_post)
        log("Initial scroll x2 (production pattern)...")
        await page.evaluate("""
            async () => {
                for (let i = 0; i < 2; i++) {
                    window.scrollBy(0, 1000);
                    await new Promise(r => setTimeout(r, 800));
                }
                window.scrollTo(0, 0);
            }
        """)
        await page.wait_for_timeout(2000)

        labels = ["เกี่ยวข้องมากที่สุด", "ความเกี่ยวข้องมากที่สุด", "Most relevant",
                  "ใหม่ล่าสุด", "Most recent", "ความคิดเห็นทั้งหมด", "All comments"]

        info = await page.evaluate(LOCATE_JS, labels)
        log(f"Trigger candidates: {len(info['all'])}")
        for c in info["all"]:
            log(f"  cand: '{c['text']}' visible={c['visible']} rect={c['rect']} "
                f"vis={c['vis']} disp={c['disp']}")
        if not info.get("click"):
            log("NO clickable trigger found - aborting")
            await page.screenshot(path="screenshots/toggle_debug_no_trigger.png")
            await browser.close()
            return
        log(f"Clicking trigger at {info['click']}")

        # Mark + click exactly like production attempt 1
        await page.mouse.click(info["click"]["x"], info["click"]["y"])

        for i in range(8):
            await page.wait_for_timeout(500)
            menus = await page.evaluate(MENU_STATE_JS)
            vis_menus = [m for m in menus if m["visible"]]
            log(f"  t+{(i + 1) * 0.5:.1f}s menus={len(menus)} visible={len(vis_menus)}")
            if vis_menus:
                for m in vis_menus:
                    log(f"    menu items: {m['items']}")
                await page.screenshot(path="screenshots/toggle_debug_menu_open.png")
                break
        else:
            log("Menu NEVER opened")
            await page.screenshot(path="screenshots/toggle_debug_menu_never.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
