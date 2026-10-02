"""Standalone test: verify switch_to_most_recent() works on the live post page.

Steps:
1. Launch browser with saved session
2. Open the target post
3. Call scraper.switch_to_most_recent()
4. Verify top comments are now the NEWEST ones
"""
import asyncio
import sys

import yaml

sys.path.insert(0, ".")

from app.scraper.facebook import FacebookScraper  # noqa: E402


async def main() -> None:
    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    scraper = FacebookScraper(cfg)
    await scraper.initialize()
    try:
        await scraper.navigate_to_post(cfg["target"]["post_url"])

        ok = await scraper.switch_to_most_recent()
        print(f"\n=== switch_to_most_recent result: {ok} ===\n")

        # Give Facebook a moment to re-render, then list what we see
        await scraper.page.wait_for_timeout(5000)
        rows = await scraper.page.evaluate(
            """() => {
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
                return t1.slice(0, 8).map(a => {
                    const link = a.querySelector('a[href*="comment_id="]');
                    const m = link ? link.href.match(/comment_id=(\\d+)/) : null;
                    const label = (a.getAttribute('aria-label') || '').replace(/\\u0e04\\u0e27\\u0e32\\u0e21\\u0e04\\u0e34\\u0e14\\u0e40\\u0e2b\\u0e47\\u0e19\\u0e08\\u0e32\\u0e01[^\\u0e40]*\\u0e40\\u0e21\\u0e37\\u0e48\\u0e2d\\s*/, '');
                    return (m ? m[1] : 'nolink') + ' | ' + label;
                });
            }"""
        )
        print("Top-level comments after switch:")
        for row in rows:
            print("  ", row)

        body = await scraper.page.evaluate("() => document.body.innerText")
        print("\nV2 visible:", "TEST_AUTOREPLY_E2E_V2" in body)
        print("E2E(v1) visible:", "TEST_AUTOREPLY_E2E" in body)
    finally:
        await scraper.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
