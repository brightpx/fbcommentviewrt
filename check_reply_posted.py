"""Check on Facebook whether our test reply TEST_AUTO_REPLY_0921 was posted."""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(6)

    # Search entire page for our test text
    result = await s.page.evaluate("""
        () => {
            const outs = [];
            const body = document.body.textContent || '';
            outs.push('Page contains TEST_AUTO_REPLY_0921: ' + body.includes('TEST_AUTO_REPLY_0921'));
            outs.push('Page contains TEST_AUTO_REPLY_160510: ' + body.includes('TEST_AUTO_REPLY_160510'));
            
            // Find all comments containing TEST_AUTO_REPLY
            const all = document.querySelectorAll('div[dir="auto"]');
            let count = 0;
            all.forEach(d => {
                const t = (d.textContent || '').trim();
                if (t.includes('TEST_AUTO_REPLY')) {
                    count++;
                    outs.push('  FOUND TEXT: ' + t.slice(0, 80));
                }
            });
            outs.push('Total TEST_AUTO_REPLY text nodes: ' + count);
            return outs.join('\\n');
        }
    """)
    print(result)

    # Now check if the reply is nested under the T1 comment
    result2 = await s.page.evaluate("""
        (commentId) => {
            const outs = [];
            const link = document.querySelector('a[href*="comment_id="][href*="' + commentId + '"]');
            if (!link) return 'T1 comment link not found';
            let current = link;
            let container = null;
            while (current && current.tagName !== 'BODY') {
                if (current.getAttribute('role') === 'article') { container = current; break; }
                current = current.parentElement;
            }
            if (!container) return 'no T1 container';
            
            // Count nested articles (T2 comments) inside the T1 container
            const nested = container.querySelectorAll('div[role="article"]');
            outs.push('Nested articles inside T1 container: ' + nested.length);
            
            // Look for TEST_AUTO_REPLY_0921 inside
            const texts = [];
            container.querySelectorAll('div[dir="auto"]').forEach(d => {
                const t = (d.textContent || '').trim();
                if (t.includes('TEST_AUTO_REPLY')) texts.push(t.slice(0, 80));
            });
            outs.push('TEST_AUTO_REPLY texts inside T1: ' + texts.join(' | '));
            
            // All comment IDs inside
            const ids = [];
            container.querySelectorAll('a[href*="comment_id="]').forEach(a => {
                const m = a.href.match(/comment_id=(\\d+)/);
                if (m) ids.push(m[1]);
            });
            outs.push('Comment IDs inside T1: ' + ids.join(', '));
            return outs.join('\\n');
        }
    """, "3410792339082758")
    print(result2)

    await s.close()

asyncio.run(main())