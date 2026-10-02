"""Browser lifecycle, session and login management (split from facebook.py)."""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext


logger = logging.getLogger(__name__)


class BrowserManager:
    """Owns Playwright browser/context/page lifecycle and session."""

    def __init__(self, config: dict):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.session_file = config['session']['file']
        self.block_media: bool = bool(config.get('browser', {}).get('block_images', True))

    def __init__(self, config: dict):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.session_file = config['session']['file']
        self.block_media: bool = bool(config.get('browser', {}).get('block_images', True))

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
        """Perform Facebook login.

        Handles three cases:
        1. Already logged in (feed renders) -> success immediately.
        2. One-tap profile page ("ดำเนินการต่อ"/"Continue") -> clicks
           through automatically (required for headless, no window).
        3. Real login form -> waits up to 5 min for manual login
           (headful mode only).
        """
        try:
            logger.info("Opening Facebook login page...")
            await self.page.goto("https://www.facebook.com", wait_until="domcontentloaded")

            logged_in_sel = '[data-visualcompletion="ignore-dynamic"], [aria-label="Account"], [aria-label="บัญชี"]'
            deadline = asyncio.get_event_loop().time() + 300
            clicked_at = 0.0

            while asyncio.get_event_loop().time() < deadline:
                try:
                    await self.page.wait_for_selector(logged_in_sel, timeout=5000)
                    logger.info("Login successful!")
                    await self.save_session()
                    return True
                except Exception:
                    pass

                # One-tap profile page? Click "ดำเนินการต่อ"/"Continue".
                # After a click, allow up to 60s for the feed to load
                # before concluding manual login is needed.
                now = asyncio.get_event_loop().time()
                if clicked_at and now - clicked_at < 60:
                    await self.page.wait_for_timeout(3000)
                    continue

                clicked = False
                try:
                    # FB's div[role=button] ignores synthetic JS .click() -
                    # must use trusted mouse events at real coordinates.
                    pt = await self.page.evaluate(
                        """() => {
                            const wants = ['ดำเนินการต่อ', 'Continue'];
                            let best = null;
                            for (const el of document.querySelectorAll(
                                'div[role="button"], button, span[role="button"], a[role="button"]')) {
                                const text = (el.textContent || '').trim();
                                if (!wants.includes(text)) continue;
                                const r = el.getBoundingClientRect();
                                if (r.width <= 0 || r.height <= 0) continue;
                                if (!best || r.width * r.height < best.area) {
                                    best = {el, area: r.width * r.height};
                                }
                            }
                            if (!best) return null;
                            best.el.scrollIntoView({block: 'center'});
                            const r = best.el.getBoundingClientRect();
                            return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                        }"""
                    )
                    if pt:
                        await self.page.mouse.click(pt['x'], pt['y'])
                        clicked = True
                except Exception as e:
                    logger.debug(f"One-tap click failed: {e}")
                if clicked:
                    logger.info("Clicked one-tap continue - waiting for feed...")
                    clicked_at = asyncio.get_event_loop().time()
                    await self.page.wait_for_timeout(4000)
                    continue

                if clicked_at:
                    # Clicked but feed never appeared (e.g. checkpoint) -
                    # fall through to manual wait below.
                    break
                await self.page.wait_for_timeout(2000)

            # Manual fallback (headful): wait for the user to finish login.
            logger.info("Please login to Facebook in the browser window...")
            await self.page.wait_for_selector(logged_in_sel, timeout=300000)

            logger.info("Login successful!")
            await self.save_session()
            return True

        except Exception as e:
            logger.error(f"Login failed: {e}")
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

