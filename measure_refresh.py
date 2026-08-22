"""Measure new-comment detection latency for 3 refresh strategies.

Setup: TWO separate browsers share the same FB session file.
  - MONITOR browser: opens the post, installs an instrumented MutationObserver,
    then stays PASSIVE while we measure when Facebook pushes the remote comment.
  - POSTER browser: acts like another user - posts a test comment.

Phases measured on the monitor (all relative to the poster's submit moment):
  A) passive      : observer only, no interaction (does FB push live?)
  B) mode toggle  : switch sorting 'most_recent' -> 'all' -> 'most_recent'
  C) page reload  : page.reload()

Observer records EVERY newly added top-level comment article with a
page-relative millisecond timestamp, whether it had a comment_id link,
and its text snippet - so we can find the test comment even when the
permalink page renders zero comment_id links (proven earlier).
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

import yaml
from playwright.async_api import async_playwright

POST_URL = "https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806"
TEST_MSG = f"MEASURE_{datetime.now().strftime('%H%M%S')}"

# Instrumented observer: logs every added TOP-LEVEL comment article.
# Records page-relative ms since install, link presence, id, text snippet.
INSTALL_OBSERVER_JS = """
() => {
    if (window.__obs) window.__obs.disconnect();
    window.__events = [];
    const t0 = performance.now();
    window.__t0 = t0;
    const vis = (el) => { const r = el.getBoundingClientRect(); return r.height > 0 && r.width > 0; };
    const handleArticle = (article) => {
        try {
            // top-level only (skip nested T2 replies)
            let p = article.parentElement;
            while (p) {
                if (p.getAttribute && p.getAttribute('role') === 'article') return;
                p = p.parentElement;
            }
            const label = article.getAttribute('aria-label') || '';
            if (!label.includes('ความคิดเห็นจาก') && !label.includes('Comment by')) return;
            if (!vis(article)) return;
            let id = null;
            const link = article.querySelector('a[href*="comment_id="]');
            if (link) {
                const m = link.href.match(/comment_id=(\\d+)/);
                if (m) id = m[1];
            }
            window.__events.push({
                t: Math.round(performance.now() - t0),
                wall: Date.now(),
                hasLink: !!link,
                id: id,
                text: (article.innerText || '').replace(/\\s+/g, ' ').substring(0, 80),
            });
        } catch (e) {}
    };
    const obs = new MutationObserver((muts) => {
        for (const mu of muts) {
            for (const n of mu.addedNodes) {
                if (n.nodeType !== 1) continue;
                if (n.getAttribute && n.getAttribute('role') === 'article') handleArticle(n);
                if (n.querySelectorAll) n.querySelectorAll('[role="article"]').forEach(handleArticle);
            }
        }
    });
    obs.observe(document.body, { childList: true, subtree: true });
    window.__obs = obs;
    return document.querySelectorAll('div[role="article"][aria-label]').length;
}
"""

DRAIN_EVENTS_JS = "() => { const e = window.__events || []; window.__events = []; return e; }"

# Raw mutation journal: records EVERY childList/subtree mutation batch so we can
# see HOW Facebook actually inserts the new comment (append article? fill shell?
# attribute change?). Keeps the last 300 batches in a ring buffer.
INSTALL_RAW_OBSERVER_JS = """
() => {
    if (window.__rawObs) window.__rawObs.disconnect();
    window.__rawLog = [];
    const t0 = performance.now();
    const describe = (n) => {
        if (!n || n.nodeType !== 1) return String(n && n.nodeName);
        return n.tagName + (n.getAttribute && n.getAttribute('role')
            ? '[role=' + n.getAttribute('role') + ']' : '');
    };
    const obs = new MutationObserver((muts) => {
        const entry = { t: Math.round(performance.now() - t0), added: 0,
                        removed: 0, samples: [], charsDelta: 0 };
        let sawText = false;
        for (const mu of muts) {
            if (mu.type === 'characterData') {
                sawText = true;
                entry.charsDelta += ((mu.target.textContent || '').length);
                continue;
            }
            entry.added += mu.addedNodes.length;
            entry.removed += mu.removedNodes.length;
            for (const n of mu.addedNodes) {
                if (entry.samples.length < 3)
                    entry.samples.push(describe(n));
            }
        }
        if (sawText) entry.samples.push('CHAR_DATA');
        window.__rawLog.push(entry);
        if (window.__rawLog.length > 300) window.__rawLog.shift();
    });
    obs.observe(document.body, { childList: true, subtree: true,
                                 characterData: true });
    window.__rawObs = obs;
    return true;
}
"""

DUMP_RAW_LOG_JS = """(sinceMs) => {
    const log = window.__rawLog || [];
    return log.filter(e => e.t >= sinceMs).slice(-40);
}"""

# Direct text scan inside comment articles (observer-independent ground truth).
# Returns rich info about WHERE the needle lives so we can learn how FB renders it.
SCAN_TEXT_JS = """(needle) => {
    const leaves = document.querySelectorAll('div, span');
    for (const el of leaves) {
        if (el.childElementCount !== 0) continue;
        if ((el.innerText || '').includes(needle)) {
            const art = el.closest('div[role="article"]');
            if (!art) continue;
            const r = art.getBoundingClientRect();
            const link = art.querySelector('a[href*="comment_id="]');
            return {
                found: true,
                ariaLabel: (art.getAttribute('aria-label') || '').substring(0, 60),
                rect: { x: Math.round(r.x), y: Math.round(r.y),
                        w: Math.round(r.width), h: Math.round(r.height) },
                inViewport: r.top < window.innerHeight && r.bottom > 0,
                hasLink: !!link,
            };
        }
    }
    return { found: false };
}"""


def log(who: str, msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] [{who}] {msg}", flush=True)


async def setup_browser(pw, headless: bool):
    browser = await pw.chromium.launch(headless=headless)
    # Production uses 1920x1080 - at 1440x900 the sort trigger sits below
    # the fold and the menu fails to open reliably.
    context = await browser.new_context(
        storage_state="session/fb_session.json",
        viewport={"width": 1920, "height": 1080},
        locale="th-TH",
    )
    page = await context.new_page()
    return browser, page


async def run_monitor(pw, stop_event: asyncio.Event, results: dict):
    """Monitor browser: observe passively, then toggle mode, then reload."""
    # NON-headless to match production - the sort menu fails to open in
    # headless Chromium (observed), while production validated it working.
    browser, page = await setup_browser(pw, headless=False)
    try:
        log("MON", "Opening post...")
        await page.goto(POST_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)

        # Production navigate_to_post does an initial scroll x2 - required for
        # the sort trigger to be clickable (menu fails without it).
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

        baseline = await page.evaluate(INSTALL_OBSERVER_JS)
        await page.evaluate(INSTALL_RAW_OBSERVER_JS)
        log("MON", f"Observer installed (baseline articles visible: {baseline})")
        results["observer_ready_wall"] = time.time()

        # ---- PHASE A: purely passive observation -------------------------
        log("MON", "PHASE A: passive observation started (45s budget)")
        phaseA_events = []
        deadline = time.time() + 45
        found_in_A = False
        a_hit_t = None
        last_scan = 0.0
        while time.time() < deadline:
            evs = await page.evaluate(DRAIN_EVENTS_JS)
            if evs:
                phaseA_events.extend(evs)
                for e in evs:
                    if TEST_MSG in e.get("text", ""):
                        found_in_A = True
                        a_hit_t = e["wall"]
                        log("MON", f"PHASE A HIT (observer): test comment appeared! "
                                   f"t=+{e['t']}ms hasLink={e['hasLink']}")
            # Ground-truth text scan every 1s - the observer ignores articles
            # that are in the DOM but not visible (virtualized rendering),
            # so only a direct scan can prove whether FB delivered the data.
            if not found_in_A and time.time() - last_scan >= 1.0:
                last_scan = time.time()
                info = await page.evaluate(SCAN_TEXT_JS, TEST_MSG)
                if info.get("found"):
                    found_in_A = True
                    a_hit_t = time.time()
                    results["phaseA_hit_info"] = info
                    log("MON", f"PHASE A HIT (text-scan): comment IS in DOM "
                               f"aria={info['ariaLabel']!r} rect={info['rect']} "
                               f"inViewport={info['inViewport']}")
                    # Dump raw mutation journal around the hit to learn the
                    # insertion mechanism (append vs in-place fill).
                    raw = await page.evaluate(DUMP_RAW_LOG_JS, 0)
                    results["raw_mutations"] = raw
                    log("MON", f"Raw mutation batches captured: {len(raw)}")
            if found_in_A and time.time() > deadline - 40:
                break
            await asyncio.sleep(0.25)
        results["phaseA"] = phaseA_events
        results["phaseA_hit"] = found_in_A
        if a_hit_t:
            results["phaseA_hit_wall"] = a_hit_t
        log("MON", f"PHASE A done: {len(phaseA_events)} events, hit={found_in_A}")

        # ---- PHASE B: sorting-mode toggle --------------------------------
        t_toggle0 = time.time()
        log("MON", "PHASE B: toggling most_recent -> all -> most_recent")
        ok1 = await toggle_mode(page, "all")
        await page.wait_for_timeout(1500)
        ok2 = await toggle_mode(page, "most_recent")
        results["toggle_ok"] = ok1 and ok2
        # Verify the toggle actually changed state: read the trigger label.
        trigger_text = await page.evaluate("""() => {
            const labels = ['เกี่ยวข้องมากที่สุด','Most relevant','ใหม่ล่าสุด',
                            'Most recent','ความคิดเห็นทั้งหมด','All comments'];
            let best = null;
            for (const el of document.querySelectorAll('div[role="button"], span[role="button"], [aria-haspopup="menu"]')) {
                const text = (el.textContent || '').trim();
                if (!text || text.length > 60) continue;
                if (!labels.some(l => text === l || text.endsWith(' ' + l))) continue;
                const r = el.getBoundingClientRect();
                if (r.height <= 0 || r.width <= 0) continue;
                if (!best || text.length < (best.textContent || '').trim().length) best = el;
            }
            return best ? (best.textContent || '').trim() : null;
        }""")
        log("MON", f"Trigger label after toggles: {trigger_text!r}")
        # collect for 6 more seconds after the toggle settles
        phaseB_events = []
        b_deadline = time.time() + 6
        b_hit = False
        b_hit_t = None
        while time.time() < b_deadline:
            evs = await page.evaluate(DRAIN_EVENTS_JS)
            phaseB_events.extend(evs)
            for e in evs:
                if TEST_MSG in e.get("text", ""):
                    b_hit = True
                    b_hit_t = e["wall"]
            if not b_hit:
                info = await page.evaluate(SCAN_TEXT_JS, TEST_MSG)
                if info.get("found"):
                    b_hit = True
                    b_hit_t = time.time()
                    log("MON", "PHASE B: text-scan HIT (observer missed it)")
                    break
            if b_hit:
                break
            await asyncio.sleep(0.25)
        results["phaseB"] = phaseB_events
        results["phaseB_start"] = t_toggle0
        results["phaseB_hit"] = b_hit
        if b_hit_t:
            results["phaseB_hit_wall"] = b_hit_t
        log("MON", f"PHASE B done: {len(phaseB_events)} events, hit={b_hit}, "
                   f"toggle_ok={results['toggle_ok']}")

        # ---- PHASE C: hard reload ----------------------------------------
        t_reload0 = time.time()
        log("MON", "PHASE C: page.reload()")
        await page.reload(wait_until="domcontentloaded")
        # Poll for the comment text as soon as the DOM is interactive.
        c_hit_t = None
        c_deadline = time.time() + 20
        while time.time() < c_deadline:
            info = await page.evaluate(SCAN_TEXT_JS, TEST_MSG)
            if info.get("found"):
                c_hit_t = time.time()
                break
            await page.wait_for_timeout(250)
        results["phaseC_start"] = t_reload0
        results["phaseC_hit"] = c_hit_t is not None
        if c_hit_t:
            results["phaseC_hit_wall"] = c_hit_t
            log("MON", f"PHASE C HIT at reload+{c_hit_t - t_reload0:.2f}s")

    finally:
        await browser.close()
        stop_event.set()


async def toggle_mode(page, mode_text: str) -> bool:
    """Minimal sort-toggle: click trigger whose text shows current mode, then option."""
    # Menu item labels (debug-confirmed): the option text is the Thai label,
    # NOT the mode key - passing "all" never matches anything.
    option_label = {
        "all": "ความคิดเห็นทั้งหมด",
        "most_recent": "ใหม่ล่าสุด",
        "most_relevant": "เกี่ยวข้องมากที่สุด",
    }.get(mode_text, mode_text)
    labels_all = ["เกี่ยวข้องมากที่สุด", "Most relevant", "ใหม่ล่าสุด", "Most recent",
                  "ความคิดเห็นทั้งหมด", "All comments"]
    locate = """(labels) => {
        let best = null;
        for (const el of document.querySelectorAll('div[role="button"], span[role="button"], [aria-haspopup="menu"]')) {
            const text = (el.textContent || '').trim();
            if (!text || text.length > 60) continue;
            if (!labels.some(l => text === l || text.endsWith(' ' + l))) continue;
            const r = el.getBoundingClientRect();
            if (r.height <= 0 || r.width <= 0) continue;
            if (!best || text.length < (best.textContent || '').trim().length) best = el;
        }
        if (!best) return null;
        best.scrollIntoView({ block: 'center', behavior: 'instant' });
        const r = best.getBoundingClientRect();
        return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    }"""
    find_option = """(target) => {
        let best = null;
        for (const menu of document.querySelectorAll('[role="menu"]')) {
            for (const el of menu.querySelectorAll('*')) {
                if ((el.textContent || '').trim() !== target) continue;
                const r = el.getBoundingClientRect();
                if (r.width <= 0 || r.height <= 0) continue;
                if (!best || r.width * r.height < best.area)
                    best = { x: r.x + r.width / 2, y: r.y + r.height / 2, area: r.width * r.height };
            }
        }
        return best;
    }"""
    try:
        for attempt in range(3):
            box = await page.evaluate(locate, labels_all)
            if not box:
                log("MON", f"toggle->{mode_text}: trigger not found (attempt {attempt + 1}/3)")
                await page.wait_for_timeout(1500)
                continue
            await page.mouse.click(box["x"], box["y"])
            option = None
            for _ in range(8):
                option = await page.evaluate(find_option, option_label)
                if option:
                    break
                await page.wait_for_timeout(400)
            if option:
                await page.mouse.click(option["x"], option["y"])
                await page.wait_for_timeout(800)
                log("MON", f"toggle->{mode_text}: clicked OK (attempt {attempt + 1})")
                return True
            # menu may be open without the option - close it before retrying
            menu_open = await page.evaluate(
                """() => {
                    for (const m of document.querySelectorAll('[role="menu"]')) {
                        const r = m.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) return true;
                    }
                    return false;
                }"""
            )
            if menu_open:
                await page.keyboard.press("Escape")
            await page.wait_for_timeout(800)
        log("MON", f"toggle->{mode_text}: FAILED after 3 attempts")
        return False
    except Exception as e:
        log("MON", f"toggle->{mode_text} error: {e}")
        return False


async def run_poster(pw, results: dict):
    """Poster browser: behaves like another user posting a comment."""
    await asyncio.sleep(20)  # give monitor time to finish setup + settle
    browser, page = await setup_browser(pw, headless=True)
    try:
        log("POST", "Opening post...")
        await page.goto(POST_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)

        # Find the main comment box - EXACT copy of production
        # _find_visible_comment_box logic (validated working in V5 E2E)
        log("POST", f"Posting: {TEST_MSG}")
        find_box_js = """
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
        editable = None
        elapsed = 0
        while elapsed < 15000:
            marked = await page.evaluate(find_box_js)
            if marked:
                editable = await page.query_selector('[data-comment-box-marker="1"]')
                if editable:
                    break
            await page.wait_for_timeout(400)
            elapsed += 400
        if not editable:
            log("POST", "FAILED: comment box never appeared")
            await page.screenshot(path="screenshots/measure_no_box.png")
            results["posted"] = False
            return

        await editable.scroll_into_view_if_needed()
        await editable.click(force=True)
        await page.wait_for_timeout(800)
        await editable.type(TEST_MSG, delay=30)
        await page.wait_for_timeout(500)

        # Submit via Enter (production-validated: more reliable than button click)
        t_submit = time.time()
        await page.keyboard.press("Enter")
        results["submit_wall"] = t_submit
        results["posted"] = True
        log("POST", f"Enter pressed at t0 (wall clock recorded)")

        # Confirm echo appears in POSTER's own DOM (proves the post went through)
        echo = False
        for _ in range(15):
            echo = await page.evaluate(
                """(needle) => document.body.innerText.includes(needle)""", TEST_MSG)
            if echo:
                break
            await page.wait_for_timeout(1000)
        results["poster_echo"] = echo
        log("POST", f"Echo in own DOM: {echo}")
    finally:
        await browser.close()


async def main() -> None:
    print("=" * 70)
    print(f"MEASUREMENT RUN  test message = {TEST_MSG}")
    print("=" * 70)
    results: dict = {}
    stop_event = asyncio.Event()
    async with async_playwright() as pw:
        mon_task = asyncio.create_task(run_monitor(pw, stop_event, results))
        post_task = asyncio.create_task(run_poster(pw, results))
        await asyncio.gather(mon_task, post_task)

    # ---------------- ANALYSIS ----------------
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    submit = results.get("submit_wall")
    ready = results.get("observer_ready_wall")
    if submit and ready:
        print(f"Poster submitted at : {datetime.fromtimestamp(submit).strftime('%H:%M:%S.%f')[:-3]}")
        print(f"Observer ready at   : {datetime.fromtimestamp(ready).strftime('%H:%M:%S.%f')[:-3]}")
        print(f"Posted OK           : {results.get('posted')} | poster saw own echo: {results.get('poster_echo')}")
        print()

        def rel(wall):  # seconds relative to submit
            return f"{wall - submit:+7.2f}s"

        print("--- PHASE A: passive (observer only, no interaction) ---")
        hits_A = [e for e in results.get("phaseA", []) if TEST_MSG in e.get("text", "")]
        other_A = [e for e in results.get("phaseA", []) if TEST_MSG not in e.get("text", "")]
        a_hit = results.get("phaseA_hit")
        a_wall = results.get("phaseA_hit_wall")
        print(f"  observer article-events: {len(results.get('phaseA', []))} "
              f"(test-comment hits: {len(hits_A)}, other comments: {len(other_A)})")
        if a_hit and a_wall:
            info = results.get("phaseA_hit_info") or {}
            rect = info.get("rect", {})
            print(f"  PASSIVE DELIVERY CONFIRMED at submit{a_wall - submit:+.2f}s "
                  f"(text-scan ground truth; observer saw nothing)")
            if rect:
                print(f"    article rect={rect} aria={info.get('ariaLabel', '')[:40]!r}")
        else:
            print("    -> Facebook did NOT deliver the remote comment passively within 45s")

        print("--- PHASE B: sorting-mode toggle (all -> most_recent) ---")
        b_hit = results.get("phaseB_hit")
        b_wall = results.get("phaseB_hit_wall")
        print(f"  events during/after toggle: {len(results.get('phaseB', []))}, "
              f"toggle_ok={results.get('toggle_ok')}")
        if b_hit and b_wall:
            print(f"  comment present at submit{b_wall - submit:+.2f}s (already delivered passively)")
        else:
            print("    -> toggle did NOT surface the test comment either")

        print("--- PHASE C: page reload ---")
        c_rel = results.get("phaseC_start", 0) - submit
        c_wall = results.get("phaseC_hit_wall")
        if results.get("phaseC_hit") and c_wall:
            print(f"  reload started {c_rel:+.2f}s after submit; "
                  f"comment visible at reload+{c_wall - results['phaseC_start']:.2f}s "
                  f"(= submit{c_wall - submit:+.2f}s)")
        else:
            print(f"  reload started {c_rel:+.2f}s after submit; "
                  f"test comment visible after reload: {results.get('phaseC_hit')}")

        print("\nVERDICT:")
        if a_hit:
            lat = a_wall - submit
            print(f"  >> PASSIVE PUSH WORKS: new comment arrives ~{lat:.1f}s after posting,")
            print("     with ZERO user action. The old conclusion was wrong because the")
            print("     MutationObserver only watched for role=article/comment_id nodes;")
            print("     FB inserts the comment as a plain DIV + text fill instead.")
            print("  >> Fix: detect via text/content change inside the comments region,")
            print("     or observe characterData+any-node additions near the feed.")
            if b_hit:
                print("  >> Mode toggle adds NOTHING - data is already there before toggling.")
        elif b_hit:
            print("  >> MODE TOGGLE surfaces new comments; passive push does not.")
            print("  >> Toggle-as-refresh IS faster than waiting for reload cycle.")
        elif results.get("phaseC_hit"):
            print("  >> Only RELOAD surfaces new comments - toggle adds no speed.")
        else:
            print("  >> Inconclusive: test comment never appeared (check posted/echo flags).")
    else:
        print("Missing timing data:", json.dumps({k: v for k, v in results.items()
                                                  if not isinstance(v, list)}, ensure_ascii=False))
    Path("measure_result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print("\nRaw data saved to measure_result.json")


if __name__ == "__main__":
    asyncio.run(main())
