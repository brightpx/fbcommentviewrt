"""Inspect the DOM structure around a specific comment to understand reply button placement and nesting."""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper

# T1 comment
# COMMENT_ID = "3410792339082758"  # TEST_AUTO_REPLY_160510
# T2 comment (a reply nested under a T1 comment)
COMMENT_ID = "3410859655742693"  # TEST_AUTO_REPLY_1730

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(4)
    
    result = await s.page.evaluate("""
        (commentId) => {
            const outs = [];
            const link = document.querySelector('a[href*="comment_id=' + commentId + '"]');
            if (!link) {
                return 'COMMENT LINK NOT FOUND for ' + commentId;
            }
            outs.push('Found comment link. Walking ancestors:');
            
            let current = link;
            let depth = 0;
            while (current && current.tagName !== 'BODY' && depth < 30) {
                const role = current.getAttribute('role') || '';
                const tag = current.tagName;
                const hasReplyBtn = role === 'article' ? 
                    Array.from(current.querySelectorAll('div[role="button"], button')).filter(b => {
                        const t = (b.textContent || '').trim();
                        return (t === 'ตอบกลับ' || t === 'Reply') && b.offsetParent !== null;
                    }).length : 0;
                
                let info = '  [' + depth + '] <' + tag + '> role="' + role + '"';
                if (hasReplyBtn) info += ' hasReplyBtn=' + hasReplyBtn;
                outs.push(info);
                
                current = current.parentElement;
                depth++;
            }
            return outs.join('\\n');
        }
    """, COMMENT_ID)
    print(result)
    
    await asyncio.sleep(1)
    await s.close()

asyncio.run(main())