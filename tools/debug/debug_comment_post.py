"""
Debug script for T1 comment posting
Shows detailed step-by-step process with screenshots
"""
import asyncio
import logging
import yaml
from datetime import datetime
from pathlib import Path
from app.scraper.facebook import FacebookScraper

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

async def debug_comment_post():
    """Debug T1 comment posting with detailed logging"""
    
    comment_text = f"DEBUG_T1_{datetime.now().strftime('%H%M%S')}"
    
    print(f"\n{'='*60}")
    print(f"🔍 DEBUG T1 Comment Posting")
    print(f"Comment: {comment_text}")
    print(f"{'='*60}\n")
    
    config = load_config()
    scraper = FacebookScraper(config)
    
    try:
        # Step 1: Initialize browser
        print("Step 1: Initializing browser...")
        await scraper.initialize()
        print("✅ Browser initialized\n")
        
        # Step 2: Navigate to post
        print("Step 2: Navigating to post...")
        post_url = config['target']['post_url']
        await scraper.navigate_to_post(post_url)
        await asyncio.sleep(3)
        print("✅ Navigation complete\n")
        
        # Step 2.5: Expand all comments
        print("Step 2.5: Expanding all comments...")
        page = scraper.page
        
        # Try to click "View more comments" buttons
        view_more_selectors = [
            'div[role="button"]:has-text("View")',
            'div[role="button"]:has-text("more comment")',
            'span:has-text("View") >> xpath=ancestor::div[@role="button"]',
        ]
        
        for selector in view_more_selectors:
            try:
                buttons = await page.query_selector_all(selector)
                print(f"  Found {len(buttons)} 'view more' buttons with selector: {selector}")
                for button in buttons:
                    try:
                        text = await button.inner_text()
                        if 'view' in text.lower() and 'comment' in text.lower():
                            print(f"  Clicking: {text}")
                            await button.click()
                            await asyncio.sleep(2)
                    except:
                        pass
            except Exception as e:
                print(f"  Selector failed: {e}")
        
        print("✅ Comments expanded\n")
        
        # Step 3: Find comment box
        print("Step 3: Looking for comment box...")
        page = scraper.page
        
        selectors = [
            'div[contenteditable="true"][role="textbox"]',
            'div[aria-label*="comment"]',
            '[role="textbox"]',
        ]
        
        comment_box = None
        for selector in selectors:
            print(f"  Trying selector: {selector}")
            boxes = await page.query_selector_all(selector)
            print(f"  Found {len(boxes)} elements")
            
            for box in boxes:
                is_visible = await box.is_visible()
                if is_visible:
                    comment_box = box
                    print(f"  ✅ Found visible comment box with: {selector}")
                    break
            
            if comment_box:
                break
        
        if not comment_box:
            print("❌ No comment box found!")
            await scraper._take_screenshot("debug_no_comment_box")
            return
        
        await scraper._take_screenshot("debug_01_found_comment_box")
        print()
        
        # Step 4: Focus comment box
        print("Step 4: Focusing comment box...")
        await comment_box.scroll_into_view_if_needed()
        await comment_box.click(force=True)
        await page.wait_for_timeout(1000)
        await scraper._take_screenshot("debug_02_focused")
        print("✅ Comment box focused\n")
        
        # Step 5: Type comment
        print(f"Step 5: Typing comment: {comment_text}")
        await comment_box.type(comment_text, delay=50)
        await page.wait_for_timeout(1000)
        await scraper._take_screenshot("debug_03_typed")
        print("✅ Comment typed\n")
        
        # Step 6: Submit with Enter key (Facebook standard method)
        print("Step 6: Pressing Enter to submit...")
        await comment_box.press('Enter')
        await page.wait_for_timeout(2000)
        await scraper._take_screenshot("debug_04_after_enter")
        print("✅ Enter key pressed\n")
        
        # Skip old button-click approach
        submit_button = None
        if False:  # Disabled - keeping for reference
            submit_selectors = [
                'div[aria-label*="Comment"][role="button"]',
                'div[aria-label*="ความคิดเห็น"][role="button"]',
                'div[aria-label="Post comment"]',
                'div[aria-label="โพสต์ความคิดเห็น"]',
            ]
            
            for selector in submit_selectors:
                print(f"  Trying selector: {selector}")
                buttons = await page.query_selector_all(selector)
                print(f"  Found {len(buttons)} buttons")
                
                for button in buttons:
                    is_visible = await button.is_visible()
                    if is_visible:
                        submit_button = button
                        print(f"  ✅ Found visible submit button with: {selector}")
                        break
                
                if submit_button:
                    break
        
        # Step 7: Wait for posting
        print("Step 7: Waiting for comment to post...")
        await page.wait_for_timeout(2000)
        await scraper._take_screenshot("debug_05_after_submit_2s")
        
        await page.wait_for_timeout(3000)
        await scraper._take_screenshot("debug_06_after_submit_5s")
        
        await page.wait_for_timeout(5000)
        await scraper._take_screenshot("debug_07_after_submit_10s")
        print("✅ Waiting complete\n")
        
        # Step 9: Check if comment appears
        print("Step 9: Checking if comment appears in page...")
        try:
            comment_exists = await page.evaluate(
                f"""
                () => {{
                    const text = document.body.innerText;
                    return text.includes('{comment_text}');
                }}
                """
            )
            
            if comment_exists:
                print(f"✅ Comment found in page: {comment_text}")
            else:
                print(f"❌ Comment NOT found in page: {comment_text}")
        except Exception as e:
            print(f"⚠️ Could not check comment: {e}")
        
        print()
        
        # Step 10: Wait longer to see result
        print("Step 10: Waiting 10 more seconds...")
        await page.wait_for_timeout(10000)
        await scraper._take_screenshot("debug_08_final_20s")
        print("✅ Final screenshot taken\n")
        
        print(f"\n{'='*60}")
        print("🎬 Debug complete - check screenshots folder")
        print("Browser will stay open for inspection...")
        print(f"{'='*60}\n")
        
        # Keep browser open
        print("⏸️  Browser is open - press Ctrl+C to close")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 Closing browser...")
            await scraper.close()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        logger.exception("Debug failed")
        await scraper._take_screenshot("debug_error")
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(debug_comment_post())
