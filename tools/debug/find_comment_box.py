"""Find the comment box selector on the current Facebook post."""
import asyncio
import yaml
from app.scraper.facebook import FacebookScraper

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(4)
    
    result = await s.page.evaluate("""
        () => {
            const outs = [];
            const sel = [
                'div[aria-label*="Write a comment"]',
                'div[aria-label*="เขียนความคิดเห็น"]',
                'div[contenteditable="true"][role="textbox"]',
                'div[data-lexical-editor="true"]',
                '[contenteditable="true"]',
            ];
            for (const s of sel) {
                const el = document.querySelector(s);
                if (el) {
                    const tag = el.tagName;
                    const visible = el.offsetParent !== null;
                    const aria = el.getAttribute('aria-label') || 'none';
                    const role = el.getAttribute('role') || 'none';
                    outs.push('FOUND: ' + s + ' <' + tag + '> visible=' + visible + ' aria=' + aria + ' role=' + role);
                } else {
                    outs.push('NOT FOUND: ' + s);
                }
            }
            
            const allEditable = document.querySelectorAll('[contenteditable="true"]');
            outs.push('Total contenteditable elements: ' + allEditable.length);
            allEditable.forEach((el, i) => {
                const tag = el.tagName;
                const visible = el.offsetParent !== null;
                const aria = el.getAttribute('aria-label') || 'none';
                const role = el.getAttribute('role') || 'none';
                const placeholder = el.getAttribute('placeholder') || el.getAttribute('aria-placeholder') || 'none';
                outs.push('  [' + i + '] <' + tag + '> visible=' + visible + ' aria=' + aria + ' role=' + role + ' placeholder=' + placeholder);
            });
            
            return outs.join('\\n');
        }
    """)
    print(result)
    await s.close()

asyncio.run(main())