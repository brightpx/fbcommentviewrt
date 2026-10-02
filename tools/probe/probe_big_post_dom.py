"""Probe: diagnose why the BIG POST yields ZERO comments in the detector scan.

The detector JS requires, per comment:
  div[role="article"] + aria-label containing "ความคิดเห็นจาก"/"Comment by"
  + a link containing "comment_id=".

On the big post (12:27 session, profile pfbid URL) the scan returned 0
comments for 300 consecutive scans while group permalinks return 10-20.
This probe dumps the actual DOM structure of both URLs so we can see what
differs.
"""
import asyncio

import yaml
from playwright.async_api import async_playwright

URLS = {
    "config(group permalink)": None,  # filled from config.yaml below
    "profile(pfbid)": (
        "https://www.facebook.com/Somyinginpp/posts/"
        "pfbid025wQaSrfnCUFXwBjEPxHEHhAeicqHGpE7HALgfJYMK8K1FxHvJVjW2fpy5RTcKR4ql"
        "?rdid=VL2zkLNwtosPnbZV#"
    ),
}

DIAG_JS = """
() => {
    const out = {};
    const arts = Array.from(document.querySelectorAll('div[role="article"]'));
    out.totalArticles = arts.length;

    // 1) aria-label census over ALL role=article nodes
    let withLabel = 0, thaiLabel = 0, engLabel = 0;
    const labelSamples = [];
    for (const a of arts) {
        const label = a.getAttribute('aria-label');
        if (!label) continue;
        withLabel++;
        const norm = label.replace(/\\s+/g, ' ');
        if (norm.includes('ความคิดเห็นจาก')) thaiLabel++;
        if (norm.includes('Comment by')) engLabel++;
        if (labelSamples.length < 8) labelSamples.push(norm.substring(0, 110));
    }
    out.articlesWithAriaLabel = withLabel;
    out.thaiCommentLabels = thaiLabel;
    out.engCommentLabels = engLabel;
    out.labelSamples = labelSamples;

    // 2) comment_id links anywhere on the page
    const links = Array.from(document.querySelectorAll('a[href*="comment_id="]'));
    out.commentIdLinks = links.length;
    const replyLinks = links.filter(l => /reply_comment_id=/.test(l.href)).length;
    out.replyCommentIdLinks = replyLinks;
    out.t1LinkIds = links
        .filter(l => !/reply_comment_id=/.test(l.href))
        .slice(0, 10)
        .map(l => (l.href.match(/comment_id=(\\d+)/) || [])[1] || '?' );

    // 3) Where do "ความคิดเห็นจาก" strings live if NOT in article aria-labels?
    //    Walk all elements having an aria-label with that prefix and report
    //    their tag + role chain.
    const altHolders = [];
    const walker = document.evaluate(
        '//*[@aria-label]', document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
    const seen = new Set();
    for (let i = 0; i < walker.snapshotLength && altHolders.length < 10; i++) {
        const el = walker.snapshotItem(i);
        const label = (el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ');
        if (!label.includes('ความคิดเห็นจาก') && !label.includes('Comment by')) continue;
        let roles = [];
        let p = el;
        let depth = 0;
        while (p && depth < 6) {
            const r = p.getAttribute && p.getAttribute('role');
            if (r) roles.push(r + ':' + p.tagName);
            p = p.parentElement; depth++;
        }
        const key = roles.join('>') + '|' + label.substring(0, 40);
        if (seen.has(key)) continue;
        seen.add(key);
        altHolders.push({ tag: el.tagName, roles: roles.join('>'), label: label.substring(0, 90) });
    }
    out.altLabelHolders = altHolders;

    // 4) Fallback census: how many visible "author-like" blocks exist?
    //    Count elements whose direct text matches Thai relative timestamps.
    const tsRe = /(วินาที|นาที|ชั่วโมง|วัน|สัปดาห์)ที่แล้ว/;
    let tsCount = 0;
    const tsSamples = [];
    for (const el of document.querySelectorAll('span,div,a')) {
        if (el.children.length > 0) continue;
        const t = (el.textContent || '').trim();
        if (t && tsRe.test(t)) {
            tsCount++;
            if (tsSamples.length < 6) tsSamples.push(t.substring(0, 60));
        }
    }
    out.relativeTimestampLeaves = tsCount;
    out.tsSamples = tsSamples;

    // 5) Comment count header ("N ความคิดเห็น")
    const m = (document.body.innerText || '').match(/(\\d+)\\s*ความคิดเห็น/g);
    out.commentCountTexts = m ? m.slice(-3) : [];

    // 6) Sort trigger present?
    out.hasSortTrigger = !!Array.from(document.querySelectorAll('span,div')).find(
        e => e.children.length === 0 &&
        /แสดงความคิดเห็น|ความคิดเห็นทั้งหมด|ใหม่ล่าสุด/.test(e.textContent || ''));

    return out;
}
"""


async def probe(page, name: str, url: str) -> None:
    print(f"\n{'=' * 70}\nPROBE {name}\n  {url}\n{'=' * 70}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=90000)
    except Exception as e:
        print(f"  GOTO FAILED: {e}")
        return
    await page.wait_for_timeout(12000)
    # scroll to comments to force lazy render
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(5000)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(2000)

    info = await page.evaluate(DIAG_JS)
    for k, v in info.items():
        if isinstance(v, list):
            print(f"{k}: ({len(v)})")
            for item in v[:10]:
                print(f"   - {item}")
        else:
            print(f"{k}: {v}")


async def main() -> None:
    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    URLS["config(group permalink)"] = cfg["target"]["post_url"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(storage_state="session/fb_session.json")
        page = await ctx.new_page()
        for name, url in URLS.items():
            await probe(page, name, url)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
