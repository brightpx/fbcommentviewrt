"""Inspect Facebook comment DOM to find the reply button structure."""
import asyncio
import sys
import os
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.scraper.facebook import FacebookScraper

async def main():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    scraper = FacebookScraper(config)
    await scraper.initialize()
    
    post_url = config['target']['post_url']
    await scraper.navigate_to_post(post_url)
    await asyncio.sleep(3)
    
    # Scroll to load comments
    await scraper.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(2)
    
    # Find all comment articles (skip the post itself)
    result = await scraper.page.evaluate("""
        () => {
            const output = [];
            // Find all articles that contain comment links
            const articles = document.querySelectorAll('div[role="article"]');
            output.push('Total articles: ' + articles.length);
            
            let commentCount = 0;
            for (let i = 0; i < articles.length && commentCount < 3; i++) {
                const art = articles[i];
                // Only look at articles that have a comment link
                const link = art.querySelector('a[href*="comment_id="]');
                if (!link) continue;
                
                const cid = link.getAttribute('href').match(/comment_id=(\\d+)/)?.[1] || 'no-id';
                output.push(`\\n=== Comment ${commentCount} (comment_id=${cid}) ===`);
                commentCount++;
                
                // Dump ALL clickable/button elements
                const btns = art.querySelectorAll('[role="button"], button, div[aria-label]');
                output.push(`Elements with role/aria: ${btns.length}`);
                let found = 0;
                btns.forEach((b) => {
                    const txt = (b.textContent || '').trim().slice(0, 80);
                    const aria = b.getAttribute('aria-label') || '';
                    const role = b.getAttribute('role') || '';
                    const tag = b.tagName;
                    const visible = b.offsetParent !== null;
                    
                    // Only show reply-related or visible clickable elements
                    if (txt.includes('ตอบ') || txt.toLowerCase().includes('reply') || 
                        aria.includes('ตอบ') || aria.toLowerCase().includes('reply') ||
                        (role === 'button' && visible && txt.length < 30)) {
                        output.push(`  <${tag}> role='${role}' text='${txt}' aria='${aria}' visible=${visible}`);
                        found++;
                    }
                });
                if (found === 0) {
                    output.push('  No reply-related elements found. Dumping all visible buttons:');
                    let shown = 0;
                    btns.forEach((b) => {
                        if (shown >= 5) return;
                        const txt = (b.textContent || '').trim().slice(0, 80);
                        const aria = b.getAttribute('aria-label') || '';
                        const role = b.getAttribute('role') || '';
                        const visible = b.offsetParent !== null;
                        if (visible) {
                            output.push(`  <${b.tagName}> role='${role}' text='${txt}' aria='${aria}'`);
                            shown++;
                        }
                    });
                }
            }
            return output.join('\\n');
        }
    """)
    
    print(result)
    await scraper.close()

if __name__ == '__main__':
    asyncio.run(main())