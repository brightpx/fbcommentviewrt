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
            await self.page.wait_for_timeout(3000)
            
            # Scroll down to load comments
            logger.info("Scrolling to load all comments...")
            await self.page.evaluate("""
                async () => {
                    const scrollHeight = document.body.scrollHeight;
                    window.scrollTo(0, scrollHeight);
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    window.scrollTo(0, 0);
                }
            """)
            await self.page.wait_for_timeout(2000)
            
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
            await self.page.wait_for_timeout(1000)
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
    
    async def expand_all_comments(self) -> None:
        """Expand all comments and replies."""
        try:
            # Click "View more comments" buttons
            while True:
                try:
                    more_buttons = await self.page.query_selector_all(
                        'div[role="button"]:has-text("View more comments"), '
                        'div[role="button"]:has-text("ดูความคิดเห็นเพิ่มเติม")'
                    )
                    if not more_buttons:
                        break
                    
                    for button in more_buttons[:5]:  # Process in batches
                        try:
                            await button.scroll_into_view_if_needed()
                            await button.click()
                            await self.page.wait_for_timeout(500)
                        except:
                            pass
                    
                    if len(more_buttons) < 5:
                        break
                        
                except Exception:
                    break
            
            # Click "View more replies" buttons
            while True:
                try:
                    reply_buttons = await self.page.query_selector_all(
                        'div[role="button"]:has-text("replies"), '
                        'div[role="button"]:has-text("การตอบกลับ"), '
                        'div[role="button"]:has-text("View more replies"), '
                        'div[role="button"]:has-text("ดูการตอบกลับเพิ่มเติม")'
                    )
                    if not reply_buttons:
                        break
                    
                    for button in reply_buttons[:5]:
                        try:
                            await button.scroll_into_view_if_needed()
                            await button.click()
                            await self.page.wait_for_timeout(500)
                        except:
                            pass
                    
                    if len(reply_buttons) < 5:
                        break
                        
                except Exception:
                    break
                    
        except Exception as e:
            logger.error(f"Error expanding comments: {e}")
    
    async def get_raw_comments_html(self) -> str:
        """Get raw HTML of comments section."""
        try:
            # Scroll down multiple times to load more comments
            logger.info("Scrolling to load all comments...")
            for i in range(5):
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
