"""Probe the real DOM structure around a posted reply to fix _verify_reply_in_dom.

Opens a SEPARATE browser (shares session/fb_session.json) and inspects:
1. Links pointing to the parent comment (comment_id=...)
2. Whether those links live inside div[role="article"]
3. Whether nested div[role="article"] exist under that article
4. Where the reply text actually lives relative to the link
"""

import asyncio
import json

from playwright.async_api import async_playwright

PARENT_ID = "3412972672198058"
REPLY_TEXT = "ขอบคุณสำหรับความคิดเห็นครับ"
POST_URL = "https://www.facebook.com/groups/2965724366922893/permalink/2972275236267806"


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state="session/fb_session.json",
            viewport={"width": 1440, "height": 900},
            locale="th-TH",
        )
        page = await context.new_page()
        await page.goto(POST_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)

        result = await page.evaluate(
            """([parentId, replyText]) => {
                const out = { links: [], articlesTotal: 0, replyTextNodes: [], diagnostics: {} };
                const vis = (el) => {
                    const r = el.getBoundingClientRect();
                    return r.height > 0 && r.width > 0;
                };

                // 1. All links referencing the parent comment
                const sel = 'a[href*="comment_id=' + parentId + '"]';
                const links = [...document.querySelectorAll(sel)];
                out.diagnostics.linksTotal = links.length;
                for (const l of links.slice(0, 10)) {
                    const info = {
                        href: l.href.substring(0, 160),
                        visible: vis(l),
                        text: (l.innerText || '').substring(0, 40),
                        insideArticle: !!l.closest('div[role="article"]'),
                        ancestorChain: [],
                    };
                    // Walk up 14 levels recording tag[role]
                    let node = l.parentElement;
                    for (let i = 0; i < 14 && node; i++) {
                        const role = node.getAttribute ? node.getAttribute('role') : null;
                        const al = node.getAttribute ? node.getAttribute('aria-label') : null;
                        info.ancestorChain.push(node.tagName + (role ? `[role=${role}]` : '') + (al ? `[label=${al.substring(0,25)}]` : ''));
                        node = node.parentElement;
                    }
                    out.links.push(info);
                }

                // 2. Articles: total + which contain the parent link + nested articles
                const arts = [...document.querySelectorAll('div[role="article"]')];
                out.articlesTotal = arts.length;
                out.diagnostics.articlesContainingLink = arts.filter(a => a.querySelector(sel)).length;
                out.diagnostics.articlesVisible = arts.filter(vis).length;
                // For first article containing the link: how many nested articles + does nested contain reply text?
                const host = arts.find(a => vis(a) && a.querySelector(sel));
                if (host) {
                    const nested = [...host.querySelectorAll('div[role="article"]')];
                    out.diagnostics.hostNestedArticles = nested.length;
                    out.diagnostics.hostNestedContainsReply = nested.some(n => (n.innerText || '').includes(replyText));
                    out.diagnostics.hostSelfContainsReply = (host.innerText || '').includes(replyText);
                }

                // 3. Where does the reply text live? Find smallest elements containing it
                const candidates = [...document.querySelectorAll('div,span')]
                    .filter(el => el.childElementCount === 0 && (el.innerText || '').trim().includes(replyText))
                    .slice(0, 6);
                for (const el of candidates) {
                    const info = {
                        tag: el.tagName,
                        visible: vis(el),
                        textSnippet: (el.innerText || '').substring(0, 60),
                        insideNestedArticle: false,
                        distanceToParentLinkLevels: null,
                    };
                    // Is any ancestor-of-ancestor an article nested in another article?
                    let art = el.closest('div[role="article"]');
                    if (art && art.parentElement && art.parentElement.closest('div[role="article"]')) {
                        info.insideNestedArticle = true;
                    }
                    // How many levels up until we reach an element that contains a link to parentId?
                    let node = el.parentElement;
                    let levels = 0;
                    while (node && levels < 40) {
                        if (node.querySelector && node.querySelector(sel)) { break; }
                        node = node.parentElement;
                        levels++;
                    }
                    info.distanceToParentLinkLevels = node ? levels : null;
                    out.replyTextNodes.push(info);
                }

                // 4. reply_comment_id links (proof a nested reply exists)
                const replyLinks = [...document.querySelectorAll('a[href*="reply_comment_id="]')];
                out.diagnostics.replyCommentLinks = replyLinks.length;
                out.diagnostics.replyCommentLinkSample = replyLinks.slice(0, 3).map(l => l.href.substring(0, 160));

                return out;
            }""",
            [PARENT_ID, REPLY_TEXT],
        )

        print(json.dumps(result, ensure_ascii=False, indent=2))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
