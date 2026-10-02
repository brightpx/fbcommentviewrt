"""Diagnostic harness: run the REAL OwnerCommentDetector pipeline with full
visibility to answer WHY fast-path detection misses remote comments.

Instrumentation:
- Wraps detector._install_mutation_observer to log every reinstall (= reload happened)
- Logs feed-activity deltas and observer-extracted IDs every loop
- Prints top-3 comment IDs every ~5s
- A second browser posts a comment mid-run (t0 recorded)

Run: .venv\\Scripts\\python.exe test_fastpath_harness.py
"""

import asyncio
import json
import time
from datetime import datetime

import yaml
from playwright.async_api import async_playwright

from app.monitor.owner_detector import OwnerCommentDetector

POST_URL = "https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806"
TEST_MSG = f"TEST_HARNESS_V8_{datetime.now().strftime('%H%M%S')}"
RUN_SECONDS = 100
POST_AT = 35  # seconds into the run

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


def log(tag, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] [{tag}] {msg}", flush=True)


async def run_poster(pw):
    """Second browser posts TEST_MSG at ~POST_AT seconds."""
    await asyncio.sleep(POST_AT)
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(
        storage_state="session/fb_session.json",
        viewport={"width": 1920, "height": 1080},
        locale="th-TH",
    )
    page = await context.new_page()
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
        log("POST", "FAILED: comment box never appeared")
        await browser.close()
        return None

    await editable.scroll_into_view_if_needed()
    await editable.click(force=True)
    await page.wait_for_timeout(800)
    await editable.type(TEST_MSG, delay=30)
    await page.wait_for_timeout(500)
    t0 = time.time()
    await page.keyboard.press("Enter")
    log("POST", f"t0 ENTER pressed for {TEST_MSG}")
    echo = False
    for _ in range(15):
        echo = await page.evaluate(
            "(needle) => document.body.innerText.includes(needle)", TEST_MSG)
        if echo:
            break
        await page.wait_for_timeout(1000)
    log("POST", f"echo in poster DOM: {echo}")
    await browser.close()
    return t0


async def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    results = {"test_msg": TEST_MSG, "detected": False}
    async with async_playwright() as pw:
        # ---- Monitor browser (headless, real session) ----
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state="session/fb_session.json",
            viewport={"width": 1920, "height": 1080},
            locale="th-TH",
        )
        page = await context.new_page()

        class _StubScraper:
            def __init__(self, p):
                self.page = p

        detector = OwnerCommentDetector(scraper=_StubScraper(page), config=config)
        detector.page = page
        detector.owner_name = "Possawee Dechsaradecho"
        detector.post_url = POST_URL

        # Instrument: log observer reinstalls (= proof a reload happened)
        orig_install = detector._install_mutation_observer

        async def logged_install():
            log("HARNESS", ">>> MutationObserver (re)installed => reload happened")
            await orig_install()

        detector._install_mutation_observer = logged_install

        log("MON", "Opening post...")
        await page.goto(POST_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)

        detector.monitoring_start_time = datetime.now()
        await detector._install_mutation_observer()
        detector.last_reload_time = time.time()
        log("MON", f"Setup done. Monitoring start={detector.monitoring_start_time:%H:%M:%S}")

        poster_task = asyncio.create_task(run_poster(pw))

        interval = config.get("monitor", {}).get("refresh_interval", 200) / 1000.0
        start = time.time()
        next_status = 0
        try:
            while time.time() - start < RUN_SECONDS:
                loop_t = time.time() - start

                activity = await detector._get_feed_activity()
                mut_ids = await detector._get_mutation_observer_comments()
                if activity or mut_ids:
                    log("LOOP", f"t={loop_t:5.1f}s activity={activity} obs_ids={mut_ids}")

                comments = await detector.detect_new_owner_comments()
                if comments:
                    for c in comments:
                        log("DETECT", f"NEW OWNER COMMENT id={c.id} msg={c.message[:40]!r}")
                        if c.message.startswith(TEST_MSG[:20]):
                            lat = time.time() - poster_task.result() if poster_task.done() else -1
                            results["detected"] = True
                            results["latency_s"] = round(lat, 2)
                            log("DETECT", f"LATENCY vs t0: {lat:.2f}s")

                if loop_t >= next_status:
                    tops = await page.evaluate("""
                        () => Array.from(
                            document.querySelectorAll('div[role="article"][aria-label*="ความคิดเห็นจาก"]')
                        ).slice(0, 3).map(a => {
                            const link = a.querySelector('a[href*="comment_id="]');
                            const m = link ? link.href.match(/comment_id=(\\d+)/) : null;
                            return m ? m[1] : null;
                        })
                    """)
                    has_new = await page.evaluate(
                        "(n) => document.body.innerText.includes(n)", TEST_MSG)
                    log("STAT", f"t={loop_t:5.1f}s top3={tops} | TEST_MSG_in_DOM={has_new}")
                    next_status += 5

                await asyncio.sleep(interval)
        finally:
            poster_task.cancel()
            await browser.close()

    with open("fastpath_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
    log("DONE", f"results={results}")


if __name__ == "__main__":
    asyncio.run(main())
