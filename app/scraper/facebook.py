"""Facebook scraper using Playwright."""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from datetime import datetime


logger = logging.getLogger(__name__)


class FacebookScraper:
    """Facebook browser automation and scraping."""
    
    def __init__(self, config: dict):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.session_file = config['session']['file']
        
    async def initialize(self) -> None:
        """Initialize Playwright browser."""
        self.playwright = await async_playwright().start()
        
        browser_config = self.config['browser']
        self.browser = await self.playwright.chromium.launch(
            headless=browser_config['headless'],
            slow_mo=browser_config['slow_mo']
        )
        
        # Try to load existing session
        if Path(self.session_file).exists():
            try:
                await self._load_session()
                logger.info("Session loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load session: {e}")
                await self._create_new_context()
        else:
            await self._create_new_context()
    
    async def _create_new_context(self) -> None:
        """Create new browser context."""
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Block images to save bandwidth and improve performance
        async def block_images(route):
            if route.request.resource_type == "image":
                logger.debug(f"Blocking image: {route.request.url[:100]}")
                await route.abort()
            else:
                await route.continue_()
        
        await self.context.route("**/*", block_images)
        logger.info("Image blocking enabled for all images")
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.config['browser']['timeout'])
    
    async def _load_session(self) -> None:
        """Load session from file."""
        with open(self.session_file, 'r') as f:
            session_data = json.load(f)
        
        self.context = await self.browser.new_context(
            storage_state=session_data,
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Block images to save bandwidth and improve performance
        async def block_images(route):
            if route.request.resource_type == "image":
                logger.debug(f"Blocking image: {route.request.url[:100]}")
                await route.abort()
            else:
                await route.continue_()
        
        await self.context.route("**/*", block_images)
        logger.info("Image blocking enabled for all images")
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.config['browser']['timeout'])
    
    async def save_session(self) -> None:
        """Save current session to file."""
        if self.context:
            Path(self.session_file).parent.mkdir(parents=True, exist_ok=True)
            session_data = await self.context.storage_state()
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            logger.info(f"Session saved to {self.session_file}")
    
    async def is_logged_in(self) -> bool:
        """Check if user is logged in to Facebook."""
        try:
            await self.page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=10000)
            await self.page.wait_for_timeout(2000)
            
            # Check for common logged-in indicators
            is_logged_in = await self.page.evaluate("""
                () => {
                    return document.querySelector('[data-visualcompletion="ignore-dynamic"]') !== null ||
                           document.querySelector('[aria-label="Account"]') !== null ||
                           document.querySelector('[aria-label="บัญชี"]') !== null;
                }
            """)
            
            return is_logged_in
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False
    
    async def login(self) -> bool:
        """Perform Facebook login."""
        try:
            logger.info("Opening Facebook login page...")
            await self.page.goto("https://www.facebook.com", wait_until="domcontentloaded")
            
            # Wait for user to login manually
            logger.info("Please login to Facebook in the browser window...")
            
            # Wait until logged in (check for home page elements)
            await self.page.wait_for_selector('[data-visualcompletion="ignore-dynamic"], [aria-label="Account"], [aria-label="บัญชี"]', timeout=300000)
            
            logger.info("Login successful!")
            await self.save_session()
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    async def navigate_to_post(self, url: str) -> bool:
        """Navigate to a specific post."""
        try:
            logger.info(f"Navigating to post: {url}")
            await self.page.goto(url, wait_until="domcontentloaded")
            
            # Get scroll_times from config for initial load
            scroll_times = self.config.get('monitor', {}).get('scroll_times', 2)
            wait_time = 500 if scroll_times <= 2 else 1000  # Shorter wait for fewer scrolls
            
            await self.page.wait_for_timeout(wait_time)
            
            # Scroll down to load comments (use config scroll_times)
            logger.info(f"Initial scroll ({scroll_times} times) to load comments...")
            await self.page.evaluate(f"""
                async () => {{
                    for (let i = 0; i < {scroll_times}; i++) {{
                        window.scrollBy(0, 1000);
                        await new Promise(resolve => setTimeout(resolve, {wait_time}));
                    }}
                    window.scrollTo(0, 0);
                }}
            """)
            await self.page.wait_for_timeout(500)
            
            # Take screenshot after initial load
            await self._take_screenshot("01_after_navigation")
            
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to post: {e}")
            return False
    
    async def switch_to_most_recent(self) -> bool:
        """Switch comment sorting to 'Most Recent' mode."""
        return await self.switch_sorting_mode("most_recent")
    
    async def switch_sorting_mode(self, mode: str = "most_recent") -> bool:
        """
        Switch comment sorting mode.
        
        Args:
            mode: Sorting mode - "most_recent" (ใหม่ล่าสุด), "most_relevant" (เกี่ยวข้องมากที่สุด), "all" (ทั้งหมด)
        """
        try:
            mode_text_map = {
                "most_recent": ["Most recent", "ใหม่ล่าสุด"],
                "most_relevant": ["Most relevant", "เกี่ยวข้องมากที่สุด"],
                "all": ["All comments", "ความคิดเห็นทั้งหมด"]
            }
            
            if mode not in mode_text_map:
                logger.warning(f"Unknown sorting mode: {mode}, defaulting to most_recent")
                mode = "most_recent"
            
            target_texts = mode_text_map[mode]
            logger.info(f"Switching to '{mode}' comment view...")
            
            # Look for sorting dropdown - try multiple selectors
            sorting_selectors = [
                'div[role="button"]:has-text("Most relevant")',
                'div[role="button"]:has-text("เกี่ยวข้องมากสุด")',
                'div[role="button"]:has-text("All comments")',
                'div[role="button"]:has-text("ความคิดเห็นทั้งหมด")',
                # Try to find by aria-label
                '[aria-label*="Sort"]',
                '[aria-label*="เรียง"]',
            ]
            
            sorting_button = None
            for selector in sorting_selectors:
                try:
                    sorting_button = await self.page.query_selector(selector)
                    if sorting_button:
                        logger.info(f"Found sorting button with selector: {selector}")
                        break
                except:
                    continue
            
            if not sorting_button:
                logger.warning("Could not find sorting dropdown button")
                await self._take_screenshot("02_no_sorting_button")
                return False
            
            # Click sorting button
            await sorting_button.scroll_into_view_if_needed()
            await sorting_button.click()
            await self.page.wait_for_timeout(300)
            await self._take_screenshot("03_sorting_menu_opened")
            
            # Click target sorting option
            option_selectors = []
            for text in target_texts:
                option_selectors.extend([
                    f'div[role="menuitem"]:has-text("{text}")',
                    f'div[role="menuitemradio"]:has-text("{text}")',
                ])
            
            target_option = None
            for selector in option_selectors:
                try:
                    target_option = await self.page.query_selector(selector)
                    if target_option:
                        logger.info(f"Found '{mode}' option with selector: {selector}")
                        break
                except:
                    continue
            
            if not target_option:
                logger.warning(f"Could not find '{mode}' option in menu")
                await self._take_screenshot("04_no_option")
                return False
            
            # Click the sorting option
            await target_option.click()
            await self.page.wait_for_timeout(2000)
            await self._take_screenshot(f"05_switched_to_{mode}")
            
            logger.info(f"Successfully switched to '{mode}' view")
            return True
            
        except Exception as e:
            logger.error(f"Error switching to most recent: {e}")
            await self._take_screenshot("06_switch_error")
            return False
    
    async def refresh_page(self) -> bool:
        """
        Refresh the current page quickly using page.reload().
        Much faster than full navigation.
        """
        try:
            logger.info("Refreshing page...")
            await self.page.reload(wait_until="domcontentloaded")
            await self.page.wait_for_timeout(500)
            logger.info("Page refresh completed")
            return True
        except Exception as e:
            logger.error(f"Error during page refresh: {e}")
            return False
    
    async def force_refresh_comments(self) -> bool:
        """
        Force refresh comments by toggling sorting mode.
        Switches to 'all' mode then back to 'most_recent' to force Facebook to reload comments.
        """
        try:
            logger.info("Force refreshing comments by toggling sorting mode...")
            
            # Switch to "all comments" mode
            success = await self.switch_sorting_mode("all")
            if not success:
                logger.warning("Failed to switch to 'all' mode, trying alternative method...")
                # Try most_relevant as alternative
                success = await self.switch_sorting_mode("most_relevant")
            
            await self.page.wait_for_timeout(200)
            
            # Scroll slightly to trigger content load
            await self.page.evaluate("window.scrollBy(0, 100)")
            await self.page.wait_for_timeout(100)
            
            # Switch back to "most recent" mode
            await self.switch_sorting_mode("most_recent")
            await self.page.wait_for_timeout(200)
            
            # Scroll slightly again to trigger content load
            await self.page.evaluate("window.scrollBy(0, 100)")
            await self.page.wait_for_timeout(100)
            
            logger.info("Force refresh completed - comments should be updated")
            return True
            
        except Exception as e:
            logger.error(f"Error during force refresh: {e}")
            return False
    
    async def _take_screenshot(self, name: str) -> None:
        """Take a screenshot for debugging."""
        try:
            screenshot_dir = Path("screenshots")
            screenshot_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = screenshot_dir / f"{timestamp}_{name}.png"
            
            await self.page.screenshot(path=str(screenshot_path), full_page=False)
            logger.debug(f"Screenshot saved: {screenshot_path}")
        except Exception as e:
            logger.debug(f"Failed to take screenshot: {e}")
    
    async def expand_all_comments(self, max_tier: int = 999) -> None:
        """Expand all comments and replies."""
        try:
            # Scroll down to load more comments first
            await self.page.evaluate("window.scrollBy(0, 500)")
            await self.page.wait_for_timeout(300)
            
            # Click "View more comments" buttons - limit attempts to avoid hanging
            max_attempts = 3
            attempts = 0
            total_clicked = 0
            while attempts < max_attempts:
                try:
                    more_buttons = await self.page.query_selector_all(
                        'div[role="button"]:has-text("View more comments"), '
                        'div[role="button"]:has-text("ดูความคิดเห็นเพิ่มเติม")'
                    )
                    logger.info(f"Found {len(more_buttons)} 'View more comments' buttons")
                    
                    if not more_buttons:
                        break
                    
                    clicked = False
                    for button in more_buttons[:3]:  # Smaller batches for speed
                        try:
                            await button.scroll_into_view_if_needed()
                            await button.click(force=True, timeout=5000)  # Force click with 5s timeout
                            await self.page.wait_for_timeout(100)  # Reduced from 500ms
                            clicked = True
                            total_clicked += 1
                        except Exception as e:
                            logger.warning(f"Failed to click 'View more comments' button: {e}")
                    
                    attempts += 1
                    
                    if not clicked:
                        break
                        
                except Exception as e:
                    logger.warning(f"Error finding more buttons: {e}")
                    break
            
            logger.info(f"Clicked {total_clicked} 'View more comments' buttons in {attempts} attempts")
            
            # Skip expanding replies if max_tier is 1 (main comments only)
            if max_tier < 2:
                logger.info(f"Skipping reply expansion (max_tier={max_tier})")
                return
            
            # Click "View more replies" buttons - limit attempts
            attempts = 0
            while attempts < max_attempts:
                try:
                    reply_buttons = await self.page.query_selector_all(
                        'div[role="button"]:has-text("replies"), '
                        'div[role="button"]:has-text("การตอบกลับ"), '
                        'div[role="button"]:has-text("View more replies"), '
                        'div[role="button"]:has-text("ดูการตอบกลับเพิ่มเติม")'
                    )
                    if not reply_buttons:
                        break
                    
                    clicked = False
                    for button in reply_buttons[:3]:
                        try:
                            await button.scroll_into_view_if_needed()
                            await button.click()
                            await self.page.wait_for_timeout(100)  # Reduced from 500ms
                            clicked = True
                        except Exception as e:
                            logger.warning(f"Failed to click reply button: {e}")
                    
                    if not clicked:
                        break
                    attempts += 1
                        
                except Exception:
                    break
                    
        except Exception as e:
            logger.error(f"Error expanding comments: {e}")
    
    async def get_raw_comments_html(self) -> str:
        """Get raw HTML of comments section."""
        try:
            # Get scroll_times from config (default to 5 for backward compatibility)
            scroll_times = self.config.get('monitor', {}).get('scroll_times', 5)
            
            # Scroll down multiple times to load more comments
            logger.info(f"Scrolling {scroll_times} times to load comments...")
            for i in range(scroll_times):
                await self.page.evaluate("window.scrollBy(0, 1000)")
                await self.page.wait_for_timeout(1000)
            
            # Take screenshot after scrolling
            await self._take_screenshot("07_after_scrolling")
            
            # Scroll back to top
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(500)
            
            # Find the main comments container
            html = await self.page.evaluate("""
                () => {
                    const container = document.querySelector('[role="article"]')?.parentElement?.parentElement;
                    return container ? container.innerHTML : '';
                }
            """)
            return html
        except Exception as e:
            logger.error(f"Error getting comments HTML: {e}")
            return ""
    
    async def post_comment(self, message: str) -> bool:
        """
        Post a comment on the current Facebook post.
        
        Args:
            message: The comment text to post
            
        Returns:
            True if comment was posted successfully, False otherwise
        """
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[DEBUG] post_comment() called with message: {message[:50]}...")
            logger.info(f"[{timestamp}] Starting comment post process")
            logger.info(f"[{timestamp}] Comment message: {message}")
            logger.info(f"[{timestamp}] Message length: {len(message)} characters")
            
            # Scroll to find comment box
            print("[DEBUG] Scrolling to bottom...")
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.page.wait_for_timeout(1000)
            
            # Find comment input box - try multiple selectors
            print("[DEBUG] Finding comment box...")
            comment_box = None
            selectors = [
                'div[aria-label*="Write a comment"]',
                'div[aria-label*="เขียนความคิดเห็น"]',
                'div[contenteditable="true"][role="textbox"]',
                'div[data-lexical-editor="true"]',
            ]
            
            for selector in selectors:
                try:
                    print(f"[DEBUG] Trying selector: {selector}")
                    comment_box = await self.page.query_selector(selector)
                    if comment_box:
                        print(f"[DEBUG] Found comment box with selector: {selector}")
                        logger.info(f"Found comment box with selector: {selector}")
                        break
                except Exception as e:
                    print(f"[DEBUG] Selector {selector} failed: {e}")
                    continue
            
            if not comment_box:
                print("[DEBUG] ERROR: Could not find comment input box")
                logger.error("Could not find comment input box")
                await self._take_screenshot("error_no_comment_box")
                return False
            
            # Click to focus with force=True
            print("[DEBUG] Clicking comment box...")
            await comment_box.scroll_into_view_if_needed()
            await comment_box.click(force=True)
            await self.page.wait_for_timeout(500)
            
            # Type the message
            print(f"[DEBUG] Typing message: {message}")
            await comment_box.type(message, delay=50)
            await self.page.wait_for_timeout(500)
            await self._take_screenshot("comment_typed")
            
            # Press Enter to submit (more reliable than clicking submit button)
            print("[DEBUG] Pressing Enter to submit...")
            logger.info("Pressing Enter to submit comment...")
            await self.page.keyboard.press('Enter')
            
            # Wait for the comment to actually appear (check that comment box is cleared)
            print("[DEBUG] Waiting for comment box to clear...")
            try:
                await self.page.wait_for_function(
                    """
                    () => {
                        const box = document.querySelector('div[contenteditable="true"][role="textbox"]');
                        return !box || box.textContent.trim() === '';
                    }
                    """,
                    timeout=10000
                )
                print("[DEBUG] Comment box cleared - comment posted")
                logger.info("Comment box cleared - comment posted")
            except Exception as e:
                print(f"[DEBUG] Warning: Could not confirm comment box cleared: {e}")
                logger.warning(f"Could not confirm comment box cleared: {e}")
            
            # Check immediately if we're still on the correct post URL (before any delay)
            current_url = self.page.url
            expected_url = self.config.get('target', {}).get('post_url', '')
            
            # Extract key identifiers from expected URL (permalink or post ID)
            is_correct_page = False
            if expected_url:
                # Check if URL contains the post/permalink identifier
                if 'permalink' in expected_url:
                    permalink_id = expected_url.split('permalink/')[-1].split('/')[0].split('?')[0]
                    is_correct_page = permalink_id in current_url
                elif 'posts' in expected_url:
                    post_id = expected_url.split('posts/')[-1].split('/')[0].split('?')[0]
                    is_correct_page = post_id in current_url
                else:
                    # Fallback: check if current URL contains expected URL
                    is_correct_page = expected_url in current_url
            
            if not is_correct_page and expected_url:
                print(f"[DEBUG] ⚠ Page redirected! Current: {current_url}")
                print(f"[DEBUG] Expected: {expected_url}")
                print("[DEBUG] Navigating back to post immediately...")
                logger.warning(f"Page redirected after posting comment. Current: {current_url}, Expected: {expected_url}")
                await self.page.goto(expected_url, wait_until="domcontentloaded")
                await self.page.wait_for_timeout(2000)
                print("[DEBUG] ✓ Navigated back to post")
                logger.info("Successfully navigated back to post page")
            
            # Now wait to ensure comment appears
            print("[DEBUG] Waiting 3 seconds for comment to appear...")
            await self.page.wait_for_timeout(3000)
            await self._take_screenshot("comment_posted")
            
            print("[DEBUG] Comment posted successfully!")
            from datetime import datetime
            success_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{success_time}] Comment posted successfully!")
            logger.info(f"[{success_time}] Posted message: {message}")
            logger.info(f"[{success_time}] Current URL: {current_url}")
            return True
            
        except Exception as e:
            from datetime import datetime
            error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[DEBUG] EXCEPTION in post_comment: {e}")
            print(f"[DEBUG] Exception type: {type(e)}")
            import traceback
            print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
            logger.error(f"[{error_time}] ✗ Error posting comment: {e}")
            logger.error(f"[{error_time}] Failed message: {message}")
            logger.error(f"[{error_time}] Exception type: {type(e).__name__}")
            logger.error(f"[{error_time}] Traceback: {traceback.format_exc()}")
            await self._take_screenshot("error_post_comment")
            return False
    
    async def reply_to_latest_owner_comment(self, message: str, owner_name: str) -> bool:
        """
        Reply to the latest comment from the post owner.
        
        Args:
            message: The reply text to post
            owner_name: The name of the post owner to identify their comments
            
        Returns:
            True if reply was posted successfully, False otherwise
        """
        try:
            logger.info(f"Looking for latest comment from owner: {owner_name}")
            
            # Scroll to top to see all comments
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(1000)
            
            # Take screenshot to debug
            await self._take_screenshot("before_find_owner")
            
            # Find all comment containers - try multiple selectors
            comment_selectors = [
                'div[role="article"]',
                'div[data-visualcompletion="ignore-dynamic"]',
            ]
            
            owner_comment = None
            for selector in comment_selectors:
                comment_divs = await self.page.query_selector_all(selector)
                logger.info(f"Found {len(comment_divs)} elements with selector: {selector}")
                
                for comment_div in comment_divs:
                    try:
                        # Get all text content from this comment
                        text_content = await comment_div.inner_text()
                        
                        # Find author link - try multiple selectors
                        author_selectors = [
                            'a[role="link"]',
                            'a[href*="/user/"]',
                            'a[href*="/profile.php"]',
                            'span[dir="auto"] a',
                        ]
                        
                        author_text = None
                        for author_selector in author_selectors:
                            author_link = await comment_div.query_selector(author_selector)
                            if author_link:
                                author_text = await author_link.inner_text()
                                if author_text and author_text.strip():
                                    break
                        
                        if author_text:
                            logger.info(f"Checking author: {author_text}")
                            
                            # Check if this is the owner's comment
                            if owner_name.lower() in author_text.lower():
                                logger.info(f"Found owner comment by: {author_text}")
                                owner_comment = comment_div
                                break
                    except Exception as e:
                        logger.debug(f"Error checking comment: {e}")
                        continue
                
                if owner_comment:
                    break
            
            if not owner_comment:
                logger.error(f"Could not find any comment from owner: {owner_name}")
                await self._take_screenshot("error_no_owner_comment")
                return False
            
            # Scroll to the owner's comment
            await owner_comment.scroll_into_view_if_needed()
            await self.page.wait_for_timeout(1000)
            await self._take_screenshot("found_owner_comment")
            
            # Try to find reply button using JavaScript to click the exact element
            # Look for "ตอบกลับ" text within the owner's comment area
            try:
                # Use JavaScript to find and click the reply button - search more thoroughly
                result = await self.page.evaluate("""
                    (ownerName) => {
                        // Find all articles (comments)
                        const articles = Array.from(document.querySelectorAll('div[role="article"]'));
                        
                        for (const article of articles) {
                            // Check if this is the owner's comment
                            const authorLinks = article.querySelectorAll('a[role="link"]');
                            let isOwner = false;
                            for (const link of authorLinks) {
                                if (link.innerText.includes(ownerName)) {
                                    isOwner = true;
                                    break;
                                }
                            }
                            
                            if (isOwner) {
                                // Try to find clickable elements with "ตอบกลับ" text
                                const walker = document.createTreeWalker(
                                    article,
                                    NodeFilter.SHOW_ELEMENT,
                                    null
                                );
                                
                                const candidates = [];
                                let node;
                                while (node = walker.nextNode()) {
                                    const text = node.textContent.trim();
                                    if (text === 'ตอบกลับ' || text === 'Reply') {
                                        candidates.push({
                                            element: node,
                                            text: text,
                                            tag: node.tagName,
                                            visible: node.offsetParent !== null,
                                            role: node.getAttribute('role')
                                        });
                                    }
                                }
                                
                                // Try to click the first visible candidate
                                for (const candidate of candidates) {
                                    if (candidate.visible) {
                                        candidate.element.click();
                                        return { success: true, text: candidate.text, tag: candidate.tag };
                                    }
                                }
                                
                                return { success: false, candidates: candidates.length, details: candidates.map(c => ({tag: c.tag, text: c.text, visible: c.visible})) };
                            }
                        }
                        return { success: false, reason: 'owner not found' };
                    }
                """, owner_name)
                
                if result.get('success'):
                    logger.info(f"Clicked reply button via JavaScript: {result.get('text')}")
                    await self.page.wait_for_timeout(1500)
                    await self._take_screenshot("reply_clicked")
                else:
                    logger.error("Could not find reply button via JavaScript")
                    await self._take_screenshot("error_no_reply_button")
                    return False
                    
            except Exception as e:
                logger.error(f"Error clicking reply button: {e}")
                await self._take_screenshot("error_click_reply")
                return False
            
            # Find reply input box
            reply_box = None
            reply_box_selectors = [
                'div[aria-label*="Write a reply"]',
                'div[aria-label*="เขียนคำตอบ"]',
                'div[contenteditable="true"][role="textbox"]',
            ]
            
            for selector in reply_box_selectors:
                try:
                    # Get all textboxes and find the one that appeared after clicking reply
                    boxes = await self.page.query_selector_all(selector)
                    for box in boxes:
                        is_visible = await box.is_visible()
                        if is_visible:
                            reply_box = box
                            logger.info(f"Found reply box with selector: {selector}")
                            break
                    if reply_box:
                        break
                except:
                    continue
            
            if not reply_box:
                logger.error("Could not find reply input box")
                await self._take_screenshot("error_no_reply_box")
                return False
            
            # Type the reply
            await reply_box.click(force=True)
            await self.page.wait_for_timeout(500)
            await reply_box.type(message, delay=50)
            await self.page.wait_for_timeout(500)
            await self._take_screenshot("reply_typed")
            
            # Find and click submit button for reply
            submit_button = None
            submit_selectors = [
                'div[aria-label*="Comment"][role="button"]',
                'div[aria-label*="ความคิดเห็น"][role="button"]',
            ]
            
            for selector in submit_selectors:
                try:
                    buttons = await self.page.query_selector_all(selector)
                    for button in buttons:
                        is_visible = await button.is_visible()
                        if is_visible:
                            submit_button = button
                            logger.info(f"Found submit button with selector: {selector}")
                            break
                    if submit_button:
                        break
                except:
                    continue
            
            if not submit_button:
                logger.error("Could not find submit button")
                await self._take_screenshot("error_no_submit_button_reply")
                return False
            
            # Click submit
            await submit_button.click(force=True)
            await self.page.wait_for_timeout(2000)
            await self._take_screenshot("reply_posted")
            
            logger.info("Reply posted successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Error posting reply: {e}")
            await self._take_screenshot("error_post_reply")
            return False
    
    async def close(self) -> None:
        """Close browser and cleanup."""
        try:
            # Close with timeout to prevent hanging
            if self.page:
                try:
                    await asyncio.wait_for(self.page.close(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning("Page close timed out")
            
            if self.context:
                try:
                    await asyncio.wait_for(self.context.close(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning("Context close timed out")
            
            if self.browser:
                try:
                    await asyncio.wait_for(self.browser.close(), timeout=3.0)
                except asyncio.TimeoutError:
                    logger.warning("Browser close timed out")
            
            if self.playwright:
                try:
                    await asyncio.wait_for(self.playwright.stop(), timeout=3.0)
                except asyncio.TimeoutError:
                    logger.warning("Playwright stop timed out")
            
            logger.info("Browser closed")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
