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
        # Speed (2026-08-23): trim background work we never use.
        self.browser = await self.playwright.chromium.launch(
            headless=browser_config['headless'],
            slow_mo=browser_config['slow_mo'],
            args=[
                '--disable-dev-shm-usage',
                '--disable-background-networking',
                '--disable-component-update',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-sync',
                '--disable-translate',
                '--mute-audio',
                '--no-first-run',
                '--no-default-browser-check',
            ],
        )
        # Media blocking toggle (config browser.block_images, default true)
        self.block_media = bool(browser_config.get('block_images', True))
        
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
    
    async def _install_speed_routes(self) -> None:
        """Block heavy resources (images / video / fonts) to speed up loads.

        Login / checkpoint / captcha URLs are EXEMPTED so a manual re-login
        with CAPTCHA still renders correctly (this was why blanket image
        blocking was removed before).
        """
        if not getattr(self, 'block_media', True):
            return

        exempt_markers = ('login', 'checkpoint', 'captcha', 'recaptcha')

        async def _speed_route(route):
            try:
                req = route.request
                url_l = req.url.lower()
                if any(m in url_l for m in exempt_markers):
                    await route.continue_()
                    return
                if req.resource_type in ('image', 'media', 'font'):
                    await route.abort()
                else:
                    await route.continue_()
            except Exception:
                try:
                    await route.continue_()
                except Exception:
                    pass

        await self.context.route('**/*', _speed_route)
        logger.info("Speed mode: blocking images/media/fonts (login pages exempt)")

    async def _create_new_context(self) -> None:
        """Create new browser context."""
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        await self._install_speed_routes()

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

        await self._install_speed_routes()

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
    
    async def keep_alive(self) -> None:
        """Keep browser active to prevent Facebook throttling."""
        if not self.page:
            return
        
        try:
            # Mouse movement simulation
            await self.page.mouse.move(100, 100)
            await asyncio.sleep(0.05)
            await self.page.mouse.move(200, 200)
            
            # Micro scroll (10px down, 10px up)
            await self.page.evaluate("window.scrollBy(0, 10)")
            await asyncio.sleep(0.05)
            await self.page.evaluate("window.scrollBy(0, -10)")
            
            # Ensure page is focused
            await self.page.bring_to_front()
            
            logger.debug("Keep-alive: browser activity simulated")
            
        except Exception as e:
            logger.warning(f"Keep-alive action failed: {e}")
    
    async def is_logged_in(self) -> bool:
        """Check if user is logged in to Facebook."""
        try:
            await self.page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=10000)
            await self.page.wait_for_timeout(self.config['browser']['timings']['after_login_check'])
            
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
            wait_time = self.config['browser']['timings']['scroll_wait']
            
            await self.page.wait_for_timeout(self.config['browser']['timings']['after_navigation'])
            
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
            await self.page.wait_for_timeout(self.config['browser']['timings']['after_scroll'])
            
            # Take screenshot after initial load
            await self._take_screenshot("01_after_navigation")
            
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to post: {e}")
            return False
    
    async def get_post_author(self) -> Optional[str]:
        """Extract the post author's name from the current page.
        
        Returns:
            Post author name, or None if not found
        """
        try:
            logger.info("Extracting post author name...")
            
            # Scroll to top to ensure post author is visible
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(self.config['browser']['timings']['post_author_wait'])
            
            # Strategy 1: Extract from Facebook's embedded JSON data (owning_profile)
            try:
                author_name = await self.page.evaluate("""
                    () => {
                        // Find all script tags containing JSON data
                        const scripts = document.querySelectorAll('script[type="application/json"]');
                        for (const script of scripts) {
                            try {
                                const text = script.textContent;
                                if (text && text.includes('owning_profile')) {
                                    // Try to find owning_profile pattern
                                    const match = text.match(/"owning_profile":\\{[^}]*"name":"([^"]+)"/);
                                    if (match && match[1]) {
                                        return match[1];
                                    }
                                }
                            } catch (e) {}
                        }
                        return null;
                    }
                """)
                if author_name:
                    logger.info(f"Found post author from owning_profile: {author_name}")
                    return author_name
            except Exception as e:
                logger.debug(f"owning_profile strategy failed: {e}")
            
            # Strategy 2: Try og:title meta tag
            try:
                title_element = await self.page.query_selector('meta[property="og:title"]')
                if title_element:
                    title_content = await title_element.get_attribute('content')
                    if title_content and ' - ' in title_content:
                        author_text = title_content.split(' - ')[0].strip()
                        if author_text and len(author_text) > 2:
                            logger.info(f"Found post author from og:title: {author_text}")
                            return author_text
            except Exception as e:
                logger.debug(f"og:title strategy failed: {e}")
            
            # Strategy 3: Find header strong tag
            try:
                author_element = await self.page.query_selector('div[role="article"] h2 strong, div[role="article"] h3 strong, div[role="article"] h4 strong')
                if author_element:
                    author_text = await author_element.inner_text()
                    author_text = author_text.strip()
                    if author_text and len(author_text) > 2:
                        logger.info(f"Found post author from header: {author_text}")
                        return author_text
            except Exception as e:
                logger.debug(f"Header strategy failed: {e}")
            
            logger.warning("Could not extract post author name")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting post author: {e}")
            return None
    
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
            
            # STEP 1: Find the dropdown TRIGGER via JavaScript text matching.
            # The trigger shows the CURRENT sort mode (e.g. "เกี่ยวข้องมากที่สุด").
            # CSS :has-text() selectors miss it because Facebook renders the label
            # in deeply nested spans, so we match trimmed textContent instead and
            # mark the element for a trusted Playwright click.
            # RETRY: right after page load the comments section (and its sort
            # button) may not be rendered yet — poll for up to ~15s.
            trigger_text = None
            for attempt in range(6):
                trigger_text = await self.page.evaluate(
                    """
                    (labels) => {
                        const candidates = document.querySelectorAll(
                            'div[role="button"], span[role="button"], [aria-haspopup="menu"]'
                        );
                        let best = null;
                        for (const el of candidates) {
                            const text = (el.textContent || '').trim();
                            if (!text || text.length > 60) continue;
                            if (!labels.some(l => text === l || text.endsWith(' ' + l))) continue;
                            // Facebook renders hidden duplicates for other viewports —
                            // only accept elements that are actually rendered.
                            const r = el.getBoundingClientRect();
                            if (r.height <= 0 || r.width <= 0) continue;
                            const style = getComputedStyle(el);
                            if (style.visibility === 'hidden' || style.display === 'none') continue;
                            // Prefer the INNERMOST matching element (smallest text)
                            if (!best || text.length < (best.textContent || '').trim().length) {
                                best = el;
                            }
                        }
                        if (!best) return null;
                        best.setAttribute('data-sort-trigger', '1');
                        return (best.textContent || '').trim();
                    }
                    """,
                    ["เกี่ยวข้องมากที่สุด", "ความเกี่ยวข้องมากที่สุด", "Most relevant",
                     "ใหม่ล่าสุด", "Most recent", "ความคิดเห็นทั้งหมด", "All comments"]
                )
                if trigger_text:
                    break
                # LATENCY (2026-08-23): was 2500ms — right after a reload this
                # retry dominated recovery time (up to 6x2.5s=15s before the
                # feed was usable). 900ms still gives React time to render.
                logger.info(f"Sort trigger not rendered yet (attempt {attempt + 1}/6), scrolling and retrying...")
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.page.wait_for_timeout(900)
            
            if not trigger_text:
                logger.warning("Could not find sorting dropdown button")
                await self._take_screenshot("02_no_sorting_button")
                return False
            
            logger.info(f"Found sorting trigger showing: {trigger_text}")
            
            # STEP 1b: Open the menu. The trigger div is only ~10px tall and
            # elementHandle.click() times out on it, so we click its CENTER
            # COORDINATES with real mouse events. The post dialog has its own
            # internal scroll container, so the trigger can sit BELOW the
            # viewport — scrollIntoView() first or the click lands off-target.
            # Coordinates are RE-COMPUTED every attempt because React may
            # re-render the node (dropping our marker) or shift the layout.
            locate_trigger_js = """(labels) => {
                const candidates = document.querySelectorAll(
                    'div[role="button"], span[role="button"], [aria-haspopup="menu"]'
                );
                let best = null;
                for (const el of candidates) {
                    const text = (el.textContent || '').trim();
                    if (!text || text.length > 60) continue;
                    if (!labels.some(l => text === l || text.endsWith(' ' + l))) continue;
                    const r = el.getBoundingClientRect();
                    if (r.height <= 0 || r.width <= 0) continue;
                    const s = getComputedStyle(el);
                    if (s.visibility === 'hidden' || s.display === 'none') continue;
                    if (!best || text.length < (best.textContent || '').trim().length) {
                        best = el;
                    }
                }
                if (!best) return null;
                best.scrollIntoView({ block: 'center', behavior: 'instant' });
                best.setAttribute('data-sort-trigger', '1');
                const r = best.getBoundingClientRect();
                return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
            }"""
            
            option_box = None
            for attempt in range(4):
                # If a menu is ALREADY open (e.g. previous click worked but the
                # option scan raced), do NOT click again — that would toggle
                # the menu closed. Just poll for the option below.
                menu_open = await self.page.evaluate(
                    """() => {
                        for (const m of document.querySelectorAll('[role="menu"]')) {
                            const r = m.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) return true;
                        }
                        return false;
                    }"""
                )
                
                if not menu_open:
                    box = await self.page.evaluate(locate_trigger_js,
                        ["เกี่ยวข้องมากที่สุด", "ความเกี่ยวข้องมากที่สุด", "Most relevant",
                         "ใหม่ล่าสุด", "Most recent", "ความคิดเห็นทั้งหมด", "All comments"])
                    if not box:
                        logger.warning(f"Sorting trigger disappeared (attempt {attempt + 1}/4)")
                        await self.page.wait_for_timeout(600)
                        continue
                    await self.page.wait_for_timeout(150)
                    
                    # Escalating click strategies: plain coordinate click usually
                    # works; force-click handles overlay interference; keyboard
                    # activation is the last resort for stubborn renders.
                    try:
                        if attempt <= 1:
                            await self.page.mouse.click(box['x'], box['y'])
                        elif attempt == 2:
                            trigger_el = await self.page.query_selector('[data-sort-trigger="1"]')
                            if trigger_el:
                                await trigger_el.click(force=True, timeout=3000)
                            else:
                                await self.page.mouse.click(box['x'], box['y'])
                        else:
                            await self.page.evaluate(
                                """() => {
                                    const el = document.querySelector('[data-sort-trigger="1"]');
                                    if (el) { el.focus(); }
                                }"""
                            )
                            await self.page.keyboard.press('Enter')
                            await self.page.wait_for_timeout(400)
                            await self.page.keyboard.press(' ')
                    except Exception as click_err:
                        logger.warning(f"Trigger click attempt {attempt + 1} failed: {click_err}")
                
                # STEP 2: POLL for the target option inside the open menu
                # (up to ~3s) instead of a single fixed-wait check — the menu
                # may animate in slightly after the click.
                # Menu leaves may carry no ARIA role at all, so we simply look
                # for the innermost visible element whose text matches exactly
                # and return its center coordinates for a coordinate click.
                find_option_js = """
                    (targetTexts) => {
                        let best = null;
                        for (const menu of document.querySelectorAll('[role="menu"]')) {
                            for (const el of menu.querySelectorAll('*')) {
                                const text = (el.textContent || '').trim();
                                if (!targetTexts.includes(text)) continue;
                                const r = el.getBoundingClientRect();
                                if (r.width <= 0 || r.height <= 0) continue;
                                const s = getComputedStyle(el);
                                if (s.visibility === 'hidden' || s.display === 'none') continue;
                                if (!best || r.width * r.height < best.area) {
                                    best = {
                                        x: r.x + r.width / 2,
                                        y: r.y + r.height / 2,
                                        area: r.width * r.height
                                    };
                                }
                            }
                        }
                        return best;
                    }
                """
                for _ in range(8):
                    option_box = await self.page.evaluate(find_option_js, target_texts)
                    if option_box:
                        break
                    await self.page.wait_for_timeout(300)
                if option_box:
                    break
                logger.info(f"Menu did not open or option missing (attempt {attempt + 1}/4)")
                # SAFETY: only press Escape when a menu is ACTUALLY open.
                # With no menu open, Escape falls through to the post dialog
                # and CLOSES THE POST entirely (observed in production).
                menu_open = await self.page.evaluate(
                    """() => {
                        for (const m of document.querySelectorAll('[role="menu"]')) {
                            const r = m.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) return true;
                        }
                        return false;
                    }"""
                )
                if menu_open:
                    await self.page.keyboard.press('Escape')
                    await self.page.wait_for_timeout(300)
                else:
                    await self.page.wait_for_timeout(300)
            
            if not option_box:
                logger.warning(f"Could not find '{mode}' option in menu")
                await self._take_screenshot("04_no_option")
                # Same Escape guard as above — never risk closing the post dialog.
                menu_open = await self.page.evaluate(
                    """() => {
                        for (const m of document.querySelectorAll('[role="menu"]')) {
                            const r = m.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) return true;
                        }
                        return false;
                    }"""
                )
                if menu_open:
                    await self.page.keyboard.press('Escape')
                return False
            
            logger.info(f"Found '{mode}' option, clicking at ({option_box['x']:.0f}, {option_box['y']:.0f})")
            
            # STEP 3: Click the option via coordinates and verify the switch.
            await self.page.mouse.click(option_box['x'], option_box['y'])
            await self.page.wait_for_timeout(self.config['browser']['timings']['sorting_mode_switch'])
            await self._take_screenshot(f"05_switched_to_{mode}")
            
            # STEP 3: Verify the trigger now displays the target mode
            now_showing = await self.page.evaluate(
                """
                (targetTexts) => {
                    const candidates = document.querySelectorAll(
                        'div[role="button"], span[role="button"], [aria-haspopup="menu"]'
                    );
                    for (const el of candidates) {
                        const text = (el.textContent || '').trim();
                        if (text && text.length <= 60 && targetTexts.some(t => text === t || text.endsWith(' ' + t))) {
                            return text;
                        }
                    }
                    return null;
                }
                """,
                target_texts
            )
            
            if now_showing:
                logger.info(f"Successfully switched to '{mode}' view (trigger shows: {now_showing})")
                return True
            
            logger.warning(f"Clicked option but trigger does not show target mode yet")
            return False
            
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
            await self.page.wait_for_timeout(self.config['browser']['timings']['page_refresh'])
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
            
            await self.page.wait_for_timeout(self.config['browser']['timings']['force_refresh_toggle'])
            
            # Scroll slightly to trigger content load
            await self.page.evaluate("window.scrollBy(0, 100)")
            await self.page.wait_for_timeout(self.config['browser']['timings']['force_refresh_scroll'])
            
            # Switch back to "most recent" mode
            await self.switch_sorting_mode("most_recent")
            await self.page.wait_for_timeout(self.config['browser']['timings']['force_refresh_toggle'])
            
            # Scroll slightly again to trigger content load
            await self.page.evaluate("window.scrollBy(0, 100)")
            await self.page.wait_for_timeout(self.config['browser']['timings']['force_refresh_scroll'])
            
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
            await self.page.wait_for_timeout(self.config['browser']['timings']['expand_scroll'])
            
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
                            await self.page.wait_for_timeout(self.config['browser']['timings']['expand_button_click'])
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
                            await self.page.wait_for_timeout(self.config['browser']['timings']['expand_button_click'])
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
                await self.page.wait_for_timeout(self.config['browser']['timings']['click_button_wait'])
            
            # Take screenshot after scrolling
            await self._take_screenshot("07_after_scrolling")
            
            # Scroll back to top
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(self.config['browser']['timings']['after_scroll'])
            
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
    
    async def post_comment_separate_session(self, message: str, post_url: str) -> bool:
        """
        Post a comment using a separate browser session.
        This does not interfere with the monitoring session.
        
        Args:
            message: The comment text to post
            post_url: The Facebook post URL to comment on
            
        Returns:
            True if comment was posted successfully, False otherwise
        """
        temp_playwright = None
        temp_browser = None
        temp_context = None
        temp_page = None
        
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[DEBUG] post_comment_separate_session() called")
            logger.info(f"[{timestamp}] Starting separate session for manual comment")
            
            # Create new playwright instance
            temp_playwright = await async_playwright().start()
            
            # Launch new browser with same config
            browser_config = self.config['browser']
            temp_browser = await temp_playwright.chromium.launch(
                headless=browser_config['headless'],
                slow_mo=browser_config['slow_mo']
            )
            
            # Load session from file
            if Path(self.session_file).exists():
                with open(self.session_file, 'r') as f:
                    session_data = json.load(f)
                
                temp_context = await temp_browser.new_context(
                    storage_state=session_data,
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
            else:
                logger.error("No session file found - cannot post comment")
                return False
            
            temp_page = await temp_context.new_page()
            temp_page.set_default_timeout(self.config['browser']['timeout'])
            
            # Navigate to post
            print(f"[DEBUG] Navigating to: {post_url}")
            logger.info(f"Navigating to post: {post_url}")
            await temp_page.goto(post_url, wait_until="domcontentloaded")
            await temp_page.wait_for_timeout(3000)  # Longer wait for page load
            
            # Scroll down multiple times to ensure everything loads
            print("[DEBUG] Scrolling to load comments...")
            for i in range(3):
                await temp_page.evaluate("window.scrollBy(0, 800)")
                await temp_page.wait_for_timeout(800)
            
            # Scroll to bottom where comment box should be
            await temp_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await temp_page.wait_for_timeout(2000)
            
            # Find comment box with longer timeout
            print("[DEBUG] Finding comment box...")
            comment_box = None
            selectors = [
                'div[contenteditable="true"][role="textbox"]',
                'div[aria-label*="Write a comment"]',
                'div[aria-label*="เขียนความคิดเห็น"]',
            ]
            
            for selector in selectors:
                try:
                    comment_box = await temp_page.wait_for_selector(selector, timeout=10000, state="attached")
                    if comment_box:
                        print(f"[DEBUG] Found comment box with: {selector}")
                        logger.info(f"Found comment box with: {selector}")
                        break
                except Exception as e:
                    print(f"[DEBUG] Selector {selector} failed: {e}")
                    continue
            
            if not comment_box:
                print("[DEBUG] ERROR: Could not find comment box")
                logger.error("Could not find comment box")
                return False
            
            # Use JavaScript to focus and type
            print("[DEBUG] Using JavaScript to interact with comment box...")
            await temp_page.evaluate("""
                (selector) => {
                    const box = document.querySelector(selector);
                    if (box) {
                        box.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        box.focus();
                        box.click();
                    }
                }
            """, selectors[0])
            await temp_page.wait_for_timeout(1000)
            
            print(f"[DEBUG] Typing: {message}")
            await temp_page.keyboard.type(message, delay=50)
            await temp_page.wait_for_timeout(1000)
            
            print("[DEBUG] Pressing Enter...")
            await temp_page.keyboard.press('Enter')
            await temp_page.wait_for_timeout(3000)
            
            print("[DEBUG] Comment posted!")
            logger.info(f"[{timestamp}] Manual comment posted successfully in separate session")
            return True
            
        except Exception as e:
            print(f"[DEBUG] EXCEPTION in post_comment_separate_session: {e}")
            logger.error(f"Error posting comment in separate session: {e}")
            import traceback
            print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
        finally:
            # Clean up separate session
            try:
                if temp_page:
                    await temp_page.close()
                if temp_context:
                    await temp_context.close()
                if temp_browser:
                    await temp_browser.close()
                if temp_playwright:
                    await temp_playwright.stop()
                logger.info("Separate browser session closed")
            except Exception as e:
                logger.debug(f"Error closing separate session: {e}")
    
    async def _find_visible_comment_box(self, max_wait_ms: int = 10000):
        """Find the visible comment input box, preferring the one inside the post dialog.
        
        FB renders the post twice (dialog + background feed copy). A plain
        query_selector can return a hidden/offscreen duplicate, so filter by
        visibility, prefer in-dialog matches, and poll until timeout (the box
        may not exist yet right after login/navigation while React hydrates).
        """
        find_js = """
        () => {
            const sels = [
                'div[aria-label*="Write a comment"]',
                'div[aria-label*="เขียนความคิดเห็น"]',
                'div[aria-label*="ความคิดเห็น"]',
                'div[contenteditable="true"][role="textbox"]',
                'div[data-lexical-editor="true"]',
            ];
            const isVisible = (el) => {
                const rect = el.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) return false;
                return el.offsetParent !== null || el.getClientRects().length > 0;
            };
            const candidates = [];
            for (const sel of sels) {
                for (const el of document.querySelectorAll(sel)) {
                    if (!isVisible(el)) continue;
                    const ce = el.getAttribute('contenteditable');
                    const role = el.getAttribute('role');
                    if (ce !== 'true' && role !== 'textbox') continue;
                    const rect = el.getBoundingClientRect();
                    candidates.push({
                        el,
                        inDialog: !!el.closest('div[role="dialog"]'),
                        area: rect.width * rect.height,
                    });
                }
            }
            if (candidates.length === 0) return false;
            candidates.sort((a, b) => (b.inDialog - a.inDialog) || (a.area - b.area));
            const best = candidates[0].el;
            best.setAttribute('data-comment-box-marker', '1');
            best.scrollIntoView({block: 'center', behavior: 'instant'});
            return true;
        }
        """
        elapsed = 0
        interval = 400
        while elapsed < max_wait_ms:
            try:
                marked = await self.page.evaluate(find_js)
                if marked:
                    handle = await self.page.query_selector('[data-comment-box-marker="1"]')
                    if handle:
                        try:
                            await self.page.evaluate(
                                "document.querySelector('[data-comment-box-marker=\"1\"]')?.removeAttribute('data-comment-box-marker')"
                            )
                        except Exception:
                            pass
                        return handle
            except Exception as e:
                logger.debug(f"Comment box finder attempt failed: {e}")
            await self.page.wait_for_timeout(interval)
            elapsed += interval
        return None
    
    async def post_comment(self, message: str) -> bool:
        """
        Post a comment on the current Facebook post using the monitoring session.
        
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
            await self.page.wait_for_timeout(self.config['browser']['timings']['scroll_to_comment_box'])
            
            # Find comment input box - poll for a VISIBLE box (FB renders the post
            # twice: dialog + background feed; hidden duplicates break first-match)
            print("[DEBUG] Finding comment box...")
            comment_box = await self._find_visible_comment_box(max_wait_ms=10000)
            
            if not comment_box:
                print("[DEBUG] ERROR: Could not find comment input box")
                logger.error("Could not find comment input box")
                await self._take_screenshot("error_no_comment_box")
                return False
            
            logger.info("Found visible comment box")
            
            # Click to focus with force=True
            print("[DEBUG] Clicking comment box...")
            await comment_box.scroll_into_view_if_needed()
            await comment_box.click(force=True)
            await self.page.wait_for_timeout(self.config['browser']['timings']['after_scroll'])
            
            # Type the message
            print(f"[DEBUG] Typing message: {message}")
            await comment_box.type(message, delay=self.config['auto_reply']['timings']['type_delay'])
            await self.page.wait_for_timeout(self.config['browser']['timings']['after_scroll'])
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
                print(f"[DEBUG] WARNING Page redirected! Current: {current_url}")
                print(f"[DEBUG] Expected: {expected_url}")
                print("[DEBUG] Navigating back to post immediately...")
                logger.warning(f"Page redirected after posting comment. Current: {current_url}, Expected: {expected_url}")
                await self.page.goto(expected_url, wait_until="domcontentloaded")
                await self.page.wait_for_timeout(self.config['browser']['timings']['sorting_mode_switch'])
                print("[DEBUG] OK Navigated back to post")
                logger.info("Successfully navigated back to post page")
            
            # Now wait to ensure comment appears
            print("[DEBUG] Waiting 3 seconds for comment to appear...")
            await self.page.wait_for_timeout(self.config['browser']['timings']['after_comment_post'])
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
            await self.page.wait_for_timeout(self.config['browser']['timings']['click_button_wait'])
            
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
            await self.page.wait_for_timeout(self.config['browser']['timings']['click_button_wait'])
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
                    await self.page.wait_for_timeout(self.config['auto_reply']['timings']['after_click_reply'])
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
            await self.page.wait_for_timeout(self.config['auto_reply']['timings']['before_type'])
            await reply_box.type(message, delay=self.config['auto_reply']['timings']['type_delay'])
            await self.page.wait_for_timeout(self.config['auto_reply']['timings']['after_type'])
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
            await self.page.wait_for_timeout(self.config['auto_reply']['timings']['after_submit'])
            await self._take_screenshot("reply_posted")
            
            logger.info("Reply posted successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Error posting reply: {e}")
            await self._take_screenshot("error_post_reply")
            return False
    
    async def reply_to_comment(self, comment_id: str, message: str) -> bool:
        """Reply to a specific comment by ID.
        
        Args:
            comment_id: The Facebook comment ID to reply to
            message: The reply message text
            
        Returns:
            True if reply posted successfully, False otherwise
        """
        try:
            logger.info(f"Attempting to reply to comment {comment_id}")
            logger.info(f"Reply message: {message[:50]}...")
            
            # IMPORTANT: DO NOT close any dialogs here. On Facebook, the post we're
            # viewing IS a popup dialog (div[role="dialog"] ~700px wide). Closing
            # "stale" popups closes the post page we're working on!
            # We only need to make sure we pick the RIGHT textbox after clicking reply.
            
            # Try to expand "View more comments" if present.
            # FIX (2026-08-23): Playwright's click() defaults to a 30s timeout.
            # When Facebook re-renders the feed mid-click the button detaches
            # and the click blocks for the FULL 30s PER SELECTOR — the log
            # showed two matching selectors stalling 2x30s (=60s) while the
            # whole monitor loop was frozen. Expansion is best-effort: use a
            # short explicit timeout and move on; the retry loop below already
            # handles a comment that is still loading.
            try:
                expand_selectors = [
                    'div[role="button"]:has-text("View more comments")',
                    'div[role="button"]:has-text("ดูความคิดเห็นเพิ่มเติม")',
                    'span:has-text("View more comments")',
                    'span:has-text("ดูความคิดเห็นเพิ่มเติม")'
                ]
                for selector in expand_selectors:
                    try:
                        expand_btn = await self.page.query_selector(selector)
                        if expand_btn and await expand_btn.is_visible():
                            logger.info("Found 'View more comments' button, clicking to expand...")
                            await expand_btn.click(timeout=3000)
                            await self.page.wait_for_timeout(self.config['auto_reply']['timings']['expand_comments'])
                            break
                    except Exception as click_err:
                        logger.debug(f"Expand click failed ({selector}): {click_err}")
                        continue
            except Exception as e:
                logger.debug(f"No expand button found or error expanding: {e}")
            
            # Use JavaScript to find the visible comment link, click reply, type, and submit.
            # Everything in one evaluate call to avoid stale references.
            logger.info("Finding comment and clicking reply button...")
            
            # Retry loop: Facebook may take a moment to load/expand the comment.
            reply_clicked = None
            for attempt in range(3):
                reply_clicked = await self.page.evaluate(
                    """(commentId) => {
                        // Find ALL links for this comment — pick the VISIBLE one.
                        // Only require height > 0 (not y > 0, because the comment may
                        // be scrolled above the viewport with negative y).
                        // NEVER fall back to a hidden clone — that leads to 'no-article'.
                        const allLinks = document.querySelectorAll('a[href*="comment_id="][href*="' + commentId + '"]');
                        let link = null;
                        for (const l of allLinks) {
                            const r = l.getBoundingClientRect();
                            if (r.height > 0) {
                                link = l;
                                break;
                            }
                        }
                        if (!link) return 'no-visible-link';
                        
                        // Find the target article by iterating articles in REVERSE order.
                        // The innermost article (last in DOM) wraps only THIS comment.
                        const allArticles = document.querySelectorAll('div[role="article"]');
                        let targetArticle = null;
                        
                        for (let i = allArticles.length - 1; i >= 0; i--) {
                            const art = allArticles[i];
                            const r = art.getBoundingClientRect();
                            if (r.height === 0) continue;
                            if (art.contains(link)) {
                                targetArticle = art;
                                break;
                            }
                        }
                        
                        if (!targetArticle) return 'no-article';
                        
                        // Scroll into view
                        targetArticle.scrollIntoView({ behavior: 'instant', block: 'center' });
                        
                        // Find and click the reply button within this article
                        const btns = targetArticle.querySelectorAll('div[role="button"], button');
                        for (const btn of btns) {
                            const text = (btn.textContent || '').trim();
                            if (text === 'ตอบกลับ' || text === 'Reply' || text.includes('ตอบกลับ') || text.includes('Reply')) {
                                btn.click();
                                return 'clicked';
                            }
                        }
                        
                        return 'no-reply-btn';
                    }""",
                    comment_id
                )
                if reply_clicked == 'clicked':
                    break
                logger.info(f"Reply click attempt {attempt+1} failed ({reply_clicked}), retrying...")
                await self.page.wait_for_timeout(1000)
            
            if reply_clicked != 'clicked':
                logger.warning(f"Could not click reply button (result: {reply_clicked}), continuing anyway...")
            
            await self.page.wait_for_timeout(self.config['auto_reply']['timings']['after_click_reply'])
            
            # Now find the reply input box.
            # After clicking reply, Facebook opens a popup dialog (div[role="dialog"])
            # containing the reply textbox. The full-screen post dialog is also a
            # div[role="dialog"] — we need to find the SMALLER popup dialog.
            logger.info("Looking for reply input box in popup dialog...")
            reply_box = None
            
            for attempt in range(3):
                reply_box = await self.page.evaluate_handle("""
                    () => {
                        // Find the SMALLER popup dialog (not the full-screen post dialog)
                        const dialogs = document.querySelectorAll('div[role="dialog"]');
                        let popupDialog = null;
                        for (const d of dialogs) {
                            const r = d.getBoundingClientRect();
                            if (r.width < 1200 && r.height > 0 && d.offsetParent !== null) {
                                popupDialog = d;
                                break;
                            }
                        }
                        if (!popupDialog) {
                            // Fallback: any visible dialog with a textbox
                            for (const d of dialogs) {
                                if (d.offsetParent !== null) {
                                    const box = d.querySelector('div[contenteditable="true"][role="textbox"]');
                                    if (box) { popupDialog = d; break; }
                                }
                            }
                        }
                        if (!popupDialog) return null;
                        const box = popupDialog.querySelector('div[contenteditable="true"][role="textbox"]');
                        return box || null;
                    }
                """)
                if reply_box and reply_box.as_element():
                    logger.info("Found reply input box in popup dialog")
                    reply_box = reply_box.as_element()
                    break
                reply_box = None
                logger.info(f"Reply box attempt {attempt+1} failed, retrying...")
                await self.page.wait_for_timeout(1000)
            
            if not reply_box:
                # Do NOT assume success. Verify whether the reply actually
                # exists in the DOM before reporting the result.
                logger.warning("Could not find reply input box - verifying DOM instead...")
                verified = await self._verify_reply_in_dom(comment_id, message)
                if verified:
                    logger.info(f"Reply to comment {comment_id} verified in DOM (without textbox)")
                    return True
                logger.error(f"Reply box not found and reply NOT found in DOM for comment {comment_id}")
                await self._take_screenshot("error_reply_box_not_found")
                return False
            
            # Type the reply message
            await reply_box.click(force=True)
            await self.page.wait_for_timeout(self.config['auto_reply']['timings']['before_type'])
            await reply_box.type(message, delay=self.config['auto_reply']['timings']['type_delay'])
            await self.page.wait_for_timeout(self.config['auto_reply']['timings']['after_type'])
            
            # BASELINE (2026-08-23): snapshot how many visible non-editable
            # nodes already contain the reply text BEFORE submitting. Very
            # short messages ("f") cannot be confirmed by presence alone, so
            # _verify_reply_in_dom compares the post-submit count against this
            # baseline instead.
            try:
                baseline_matches = await self._count_reply_matches(message)
            except Exception as baseline_err:
                logger.debug(f"Reply baseline count failed: {baseline_err}")
                baseline_matches = None
            
            # Facebook reply dialog: submit via the Post button.
            # The button is a div[role="button"] with aria-label only (no text content):
            #   - Thai: aria-label="โพสต์ความคิดเห็น" (Post comment)
            #   - English: aria-label="Post"
            # It only appears AFTER text is typed (initially disabled/hidden).
            logger.info("Looking for the Post/โพสต์ความคิดเห็น submit button...")
            submit_clicked = await self.page.evaluate("""
                () => {
                    // Find the popup dialog (smaller one, not full-screen post)
                    const dialogs = document.querySelectorAll('div[role="dialog"]');
                    let popup = null;
                    for (const d of dialogs) {
                        const r = d.getBoundingClientRect();
                        if (r.width < 1200 && r.height > 0 && d.offsetParent !== null) {
                            popup = d;
                            break;
                        }
                    }
                    // Fallback: any dialog with a textbox
                    if (!popup) {
                        for (const d of dialogs) {
                            if (d.offsetParent !== null && d.querySelector('div[contenteditable="true"][role="textbox"]')) {
                                popup = d;
                                break;
                            }
                        }
                    }
                    if (!popup) return 'no-dialog';
                    
                    // Find the submit button by aria-label
                    const candidates = [
                        'div[role="button"][aria-label="โพสต์ความคิดเห็น"]',
                        'div[role="button"][aria-label="Post"]',
                        'div[role="button"][aria-label^="โพสต์"]'
                    ];
                    for (const sel of candidates) {
                        const btn = popup.querySelector(sel);
                        if (!btn) continue;
                        const ariaDisabled = btn.getAttribute('aria-disabled');
                        if (ariaDisabled === 'true') continue;
                        btn.click();
                        return 'clicked';
                    }
                    return 'not-found';
                }
            """)
            logger.info(f"Submit button result: {submit_clicked}")
            
            if submit_clicked == 'not-found':
                logger.warning("Post button not found, falling back to Enter key...")
                await self.page.keyboard.press('Enter')
            
            await self.page.wait_for_timeout(self.config['auto_reply']['timings']['after_submit'])
            
            # NEW (2026-08-23): Facebook can hold the submit button in its
            # "กำลังโพส.." (Posting...) state for several seconds. Starting
            # the verification countdown inside that window burns most of the
            # polling budget before FB even finishes, so first wait (max +5s)
            # until the button leaves the posting state, THEN start verifying.
            try:
                posting_waited_ms = 0
                while posting_waited_ms < 5000:
                    btn_state = await self.page.evaluate("""
                        () => {
                            const dialogs = document.querySelectorAll('div[role="dialog"]');
                            let popup = null;
                            for (const d of dialogs) {
                                const r = d.getBoundingClientRect();
                                if (r.width < 1200 && r.height > 0 && d.offsetParent !== null) {
                                    popup = d;
                                    break;
                                }
                            }
                            // Dialog gone means the submission finished and the
                            // popup was dismissed (normal success path)
                            if (!popup) return 'dialog-closed';
                            const candidates = [
                                'div[role="button"][aria-label="โพสต์ความคิดเห็น"]',
                                'div[role="button"][aria-label="Post"]',
                                'div[role="button"][aria-label^="โพสต์"]'
                            ];
                            for (const sel of candidates) {
                                const btn = popup.querySelector(sel);
                                if (!btn) continue;
                                const label = btn.getAttribute('aria-label') || '';
                                if (label.indexOf('กำลังโพส') !== -1 || /posting/i.test(label)) {
                                    return 'posting';
                                }
                                return 'idle';
                            }
                            return 'no-button';
                        }
                    """)
                    if btn_state != 'posting':
                        if posting_waited_ms > 0:
                            logger.info(f"'กำลังโพส..' state finished after +{posting_waited_ms}ms")
                        break
                    await self.page.wait_for_timeout(250)
                    posting_waited_ms += 250
                else:
                    logger.warning(
                        "Submit button still in 'กำลังโพส..' state after +5000ms "
                        "- proceeding to DOM verification anyway"
                    )
            except Exception as posting_wait_err:
                logger.debug(f"Posting-state wait skipped: {posting_wait_err}")
            
            # CRITICAL: Verify the reply actually appears in the DOM before
            # reporting success. A false "success" causes the caller to mark
            # the comment as replied and never retry it.
            verified = await self._verify_reply_in_dom(
                comment_id, message, baseline_count=baseline_matches
            )
            if not verified:
                logger.error(
                    f"Reply to comment {comment_id} NOT CONFIRMED in DOM after submit "
                    f"(it may still have been posted - check manually)"
                )
                await self._take_screenshot("error_reply_not_verified")
                return False
            
            logger.info(f"Reply posted and verified in DOM for comment {comment_id}")
            return True
            
        except Exception as e:
            logger.error(f"Exception while replying to comment {comment_id}: {e}")
            # Even on exception, verify before deciding the outcome
            try:
                verified = await self._verify_reply_in_dom(comment_id, message)
                if verified:
                    logger.info(f"Reply verified in DOM despite exception for comment {comment_id}")
                    return True
            except Exception as verify_error:
                logger.error(f"DOM verification also failed: {verify_error}")
            return False
    
    async def _count_reply_matches(self, message: str) -> int:
        """Count visible, non-editable DOM nodes currently containing the reply text.

        Used as a BASELINE right before submitting a reply. Verification then
        succeeds when the count INCREASES — the only reliable signal for very
        short messages (e.g. "f") whose mere presence proves nothing, and for
        replies Facebook renders inside the reply popup dialog WITHOUT any
        role=article wrapper (production-proven false-negative source).
        """
        result = await self.page.evaluate(
            """(replyMessage) => {
                try {
                    const needle = replyMessage.substring(0, 20);
                    const vis = (el) => {
                        const r = el.getBoundingClientRect();
                        return r.height > 0 && r.width > 0;
                    };
                    let total = 0;
                    for (const el of document.querySelectorAll('div, span')) {
                        if (el.childElementCount !== 0) continue;
                        if (!vis(el)) continue;
                        if (el.isContentEditable || el.closest('[contenteditable="true"]')) continue;
                        const txt = el.innerText || '';
                        if (txt.includes(needle)) total++;
                    }
                    return total;
                } catch (e) {
                    return -1;
                }
            }""",
            message
        )
        return int(result) if isinstance(result, int) else -1
    
    async def _verify_reply_in_dom(self, comment_id: str, message: str, max_wait_ms: int = 12000, baseline_count: Optional[int] = None) -> bool:
        """Verify that a reply actually exists in the DOM under the target comment.
        
        Polls the DOM for up to max_wait_ms because Facebook updates the
        comment thread asynchronously after submit — a single immediate check
        races against the re-render and produces false negatives.
        
        Args:
            comment_id: The Facebook comment ID that was replied to
            message: The reply message text that should appear
            max_wait_ms: Total time to keep polling before giving up
            
        Returns:
            True if the reply text is found in a visible, non-editable node
            inside an article (strongest when the article is nested within
            another article, i.e. a reply under its parent)
        """
        poll_interval_ms = 500
        elapsed_ms = 0
        last_error = 'unknown'
        
        while True:
            try:
                result = await self.page.evaluate(
                    """([commentId, replyMessage]) => {
                    try {
                        const needle = replyMessage.substring(0, 20);
                        // On group permalink pages Facebook often renders NO
                        // comment_id links at all (probe confirmed linksTotal=0),
                        // so anchoring on the parent comment is unreliable.
                        // Instead look for the reply TEXT itself in visible,
                        // non-editable nodes:
                        //   - best evidence: inside an article nested within
                        //     another article (a reply under its parent)
                        //   - acceptable: inside any article (flat rendering)
                        // Text still sitting in the contenteditable input is
                        // explicitly ignored to avoid false positives.
                        const vis = (el) => {
                            const r = el.getBoundingClientRect();
                            return r.height > 0 && r.width > 0;
                        };
                        const leaves = document.querySelectorAll('div, span');
                        let nestedHit = false;
                        let articleHit = 0;
                        let total = 0;
                        for (const el of leaves) {
                            if (el.childElementCount !== 0) continue;
                            if (!vis(el)) continue;
                            if (el.isContentEditable || el.closest('[contenteditable="true"]')) continue;
                            const txt = el.innerText || '';
                            if (!txt.includes(needle)) continue;
                            total++;
                            const art = el.closest('div[role="article"]');
                            if (!art) continue;
                            articleHit++;
                            let p = art.parentElement;
                            while (p) {
                                if (p.getAttribute && p.getAttribute('role') === 'article' && vis(p)) {
                                    nestedHit = true;
                                    break;
                                }
                                p = p.parentElement;
                            }
                            if (nestedHit) break;
                        }
                        return { total: total, articleHit: articleHit, nestedHit: nestedHit };
                    } catch (e) {
                        return { success: false, error: e.toString() };
                    }
                }""", [comment_id, message]
                )
                
                article_hit = result.get('articleHit', 0) > 0
                nested_hit = bool(result.get('nestedHit'))
                count_now = result.get('total', -1)
                if nested_hit or article_hit:
                    logger.debug(
                        f"DOM verification passed after {elapsed_ms}ms: "
                        f"mode={'nested_article' if nested_hit else 'article_text'}"
                    )
                    return True
                if baseline_count is not None and count_now > baseline_count:
                    # A NEW node containing the reply text appeared after
                    # submit — proof of posting even when Facebook renders the
                    # reply outside any role=article wrapper (e.g. inside the
                    # still-open reply popup dialog).
                    logger.debug(
                        f"DOM verification passed after {elapsed_ms}ms: "
                        f"match count {baseline_count} -> {count_now}"
                    )
                    return True
                last_error = (
                    f'reply_text_not_found (total={count_now}, '
                    f'baseline={baseline_count})'
                )
                
            except Exception as e:
                # Page/browser closing — do not spin until the timeout
                logger.error(f"Error verifying reply in DOM: {e}")
                return False
            
            if elapsed_ms >= max_wait_ms:
                break
            
            await asyncio.sleep(poll_interval_ms / 1000.0)
            elapsed_ms += poll_interval_ms
        
        logger.debug(f"DOM verification failed after {max_wait_ms}ms: {last_error}")
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
