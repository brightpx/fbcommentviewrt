"""Probe: why does the production scan JS / Python filter drop the new comment?

Opens the post fresh (V8 comment already exists), then:
1. Runs the EXACT production scan JS -> prints returned IDs
2. Dumps diagnostics for the V8 article: aria-label, T1-nesting result,
   Thai regex captures, link presence
"""

import asyncio
import json
import re

from playwright.async_api import async_playwright

POST_URL = "https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806"
TARGET_ID = "3413075168854475"  # TEST_HARNESS_V8_155203

# EXACT production scan JS copied from app/monitor/owner_detector.py
# (_get_top_n_comments), minus the f-string wrapper.
SCAN_JS = """
(topN) => {
    const allArticles = document.querySelectorAll('div[role="article"]');
    const commentArticles = Array.from(allArticles).filter(article => {
        const label = article.getAttribute('aria-label');
        return label && (label.includes('ความคิดเห็นจาก') || label.includes('Comment by'));
    });
    const topLevelComments = commentArticles.filter(article => {
        let parent = article.parentElement;
        while (parent) {
            if (parent !== article && parent.getAttribute('role') === 'article') {
                return false;
            }
            parent = parent.parentElement;
        }
        return true;
    });
    const results = [];
    for (let i = 0; i < Math.min(topLevelComments.length, topN); i++) {
        const article = topLevelComments[i];
        const ariaLabel = article.getAttribute('aria-label');
        let author = '';
        let match = ariaLabel.match(/ความคิดเห็นจาก\\s+(.+?)\\s+เมื่อ\\s+(.+)/);
        let timestamp = null;
        if (match) {
            author = match[1];
            timestamp = match[2];
        } else {
            match = ariaLabel.match(/Comment by\\s+(.+?)\\s+from\\s+(.+)/);
            if (match) {
                author = match[1];
                timestamp = match[2];
            }
        }
        if (!author) { continue; }
        const link = article.querySelector('a[href*="comment_id="]');
        if (!link) { continue; }
        const href = link.href;
        let commentId = null;
        const replyMatch = href.match(/reply_comment_id=(\\d+)/);
        if (replyMatch) {
            commentId = replyMatch[1];
        } else {
            const commentMatch = href.match(/comment_id=(\\d+)/);
            if (commentMatch) {
                commentId = commentMatch[1];
            }
        }
        if (!commentId) { continue; }
        let message = '';
        const messageDivs = article.querySelectorAll('div[dir="auto"]');
        for (const div of messageDivs) {
            const text = div.innerText.trim();
            if (text && text !== author && text.length > 2) {
                message = text;
                break;
            }
        }
        results.push({
            id: commentId,
            author: author,
            message: message,
            href: href,
            timestamp: timestamp
        });
    }
    return results;
}
"""

DIAG_JS = """
(targetId) => {
    const links = document.querySelectorAll('a[href*="comment_id=' + targetId + '"]');
    if (links.length === 0) return {found: false};
    const link = links[0];
    let el = link;
    while (el && el.getAttribute('role') !== 'article') el = el.parentElement;
    if (!el) return {found: false, reason: 'no article ancestor'};
    const label = el.getAttribute('aria-label');

    // T1 nesting check (exact production logic)
    let nested = false;
    let p = el.parentElement;
    while (p) {
        if (p !== el && p.getAttribute('role') === 'article') { nested = true; break; }
        p = p.parentElement;
    }

    const thai = label.match(/ความคิดเห็นจาก\\s+(.+?)\\s+เมื่อ\\s+(.+)/);
    return {
        found: true,
        ariaLabel: label,
        nestedInArticle: nested,
        thaiRegexMatch: !!thai,
        thaiAuthor: thai ? thai[1] : null,
        thaiTimestamp: thai ? thai[2] : null,
        articleIndex: Array.from(document.querySelectorAll('div[role="article"]')).indexOf(el),
    };
}
"""


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state="session/fb_session.json",
            viewport={"width": 1920, "height": 1080},
            locale="th-TH",
        )
        page = await context.new_page()
        await page.goto(POST_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)

        # scroll like production does
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(300)

        results = await page.evaluate(SCAN_JS, 20)
        print(f"[SCAN] returned {len(results)} comments:")
        for r in results[:8]:
            print(f"   id={r['id']} ts={r['timestamp']!r} author={r['author'][:25]!r} msg={r['message'][:30]!r}")
        ids = [r["id"] for r in results]
        print(f"[SCAN] TARGET {TARGET_ID} in results: {TARGET_ID in ids}")

        diag = await page.evaluate(DIAG_JS, TARGET_ID)
        print("[DIAG] target article:")
        print(json.dumps(diag, ensure_ascii=False, indent=2))

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
