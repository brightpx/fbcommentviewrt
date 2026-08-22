"""Structural probe: map ALL articles / comment_id links for the target comment
to understand why T1-nesting filter behaves inconsistently."""

import asyncio
import json

from playwright.async_api import async_playwright

POST_URL = "https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806"
TARGET_ID = "3413075168854475"

STRUCT_JS = """
(targetId) => {
    const all = Array.from(document.querySelectorAll('div[role="article"]'));
    const labeled = all.filter(a => {
        const l = a.getAttribute('aria-label') || '';
        return l.includes('ความคิดเห็นจาก') || l.includes('Comment by');
    });
    const isTopLevel = (article) => {
        let p = article.parentElement;
        while (p) {
            if (p !== article && p.getAttribute('role') === 'article') return false;
            p = p.parentElement;
        }
        return true;
    };
    const topLevel = labeled.filter(isTopLevel);

    // All links pointing at the target comment
    const links = Array.from(document.querySelectorAll(
        'a[href*="comment_id=' + targetId + '"]'));
    const linkInfos = links.map(link => {
        // nearest article ancestor
        let el = link;
        while (el && el.getAttribute('role') !== 'article') el = el.parentElement;
        const artIdx = el ? all.indexOf(el) : -1;
        const artLabel = el ? el.getAttribute('aria-label') : null;
        return {
            href: link.href.slice(0, 120),
            nearestArticleIdx: artIdx,
            nearestArticleLabel: artLabel,
            nearestIsTopLevel: el ? isTopLevel(el) : null,
        };
    });

    // Which labeled articles contain a link to the target?
    const artsContainingTarget = [];
    labeled.forEach((a, i) => {
        if (a.querySelector('a[href*="comment_id=' + targetId + '"]')) {
            artsContainingTarget.push({
                idx: i,
                label: a.getAttribute('aria-label'),
                topLevel: isTopLevel(a),
                inTopLevelList: topLevel.includes(a),
            });
        }
    });

    // Structure summary: for each top-level comment article, its aria-label
    const topLevelLabels = topLevel.slice(0, 12).map(a => a.getAttribute('aria-label'));

    // Ancestor chain roles for the first artsContainingTarget entry
    let chain = null;
    if (artsContainingTarget.length) {
        // find the article element again
        const target = labeled[artsContainingTarget[0].idx];
        chain = [];
        let p = target.parentElement;
        let depth = 0;
        while (p && depth < 15) {
            chain.push({
                tag: p.tagName,
                role: p.getAttribute('role'),
                label: (p.getAttribute('aria-label') || '').slice(0, 60),
            });
            p = p.parentElement;
            depth++;
        }
    }

    return {
        counts: {
            allArticles: all.length,
            labeledCommentArticles: labeled.length,
            topLevelCommentArticles: topLevel.length,
        },
        linksToTarget: linkInfos,
        artsContainingTarget,
        topLevelLabels,
        ancestorChainOfFirstTargetArticle: chain,
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
        await page.evaluate("window.scrollTo(0, 300)")
        await page.wait_for_timeout(1500)

        res = await page.evaluate(STRUCT_JS, TARGET_ID)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
