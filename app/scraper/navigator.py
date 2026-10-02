"""Post navigation, sorting and comment-expansion (split from facebook.py)."""
import logging
from typing import List, Optional


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Comment sort labels.
#
# Facebook ships two different comment-sort UIs and both are in the wild:
#
#  * LEGACY UI - a TEXT button above the comment list displays the currently
#    active mode ("เกี่ยวข้องมากที่สุด" / "Most relevant"). Clicking it opens a
#    menu whose items are plain text.
#
#  * NEW UI (observed 2026-10 on the group post dialog) - there is NO text
#    trigger at all. Sorting lives behind an icon/gear button that exposes the
#    modes as menu/radio items labelled "คอมเมนต์ล่าสุด" / "ล่าสุด" instead of
#    "ใหม่ล่าสุด". Some group post dialogs expose no sort control whatsoever.
#
# Both label sets are probed so a UI rollout does not silently disable
# newest-first ordering (which the whole ID-based detection path depends on).
# ---------------------------------------------------------------------------
SORT_LABELS: dict = {
    "most_recent": [
        "คอมเมนต์ล่าสุด",
        "ความคิดเห็นล่าสุด",
        "การตอบกลับล่าสุด",
        "ใหม่ล่าสุด",
        "ล่าสุด",
        "Most recent",
        "Latest",
        "Newest",
    ],
    "most_relevant": [
        "เกี่ยวข้องมากที่สุด",
        "ความเกี่ยวข้องมากที่สุด",
        "Most relevant",
        "Top comments",
    ],
    "all": [
        "ความคิดเห็นทั้งหมด",
        "การตอบกลับทั้งหมด",
        "คอมเมนต์ทั้งหมด",
        "All comments",
        "All replies",
    ],
    "oldest": ["เก่าที่สุด", "คอมเมนต์เก่าที่สุด", "Oldest"],
}

# Every label a sort TRIGGER may display, whichever mode is active. Used to
# locate the control before the active mode is known.
SORT_TRIGGER_LABELS: List[str] = sorted(
    {lbl for labels in SORT_LABELS.values() for lbl in labels}
)

# New-UI menu openers, matched on aria-label (the new UI has no visible text).
# Ordered most-specific first. Post-action menus are excluded at click time.
SORT_MENU_BUTTON_SELECTORS: List[str] = [
    '[aria-haspopup="menu"][aria-label*="การตั้งค่าความคิดเห็น"]',
    '[aria-haspopup="menu"][aria-label*="ตัวเลือกความคิดเห็น"]',
    '[aria-haspopup="menu"][aria-label*="Comment display settings"]',
    '[aria-haspopup="menu"][aria-label*="Comment settings"]',
    '[aria-haspopup="menu"][aria-label*="Comment sort"]',
    '[aria-haspopup="menu"][aria-label*="Sort comments"]',
    '[aria-haspopup="menu"][aria-label*="ความคิดเห็น"]',
    '[aria-haspopup="menu"][aria-label*="Comment"]',
    '[aria-haspopup="menu"][aria-label*="Sort"]',
]

# Post-action ("...") menus look similar but never contain sort options; any
# candidate whose aria-label matches this is skipped.
_SORT_MENU_SKIP_ARIA = ("การดำเนินการ", "Actions for", "หนังสือ", "จัดการกับโพสต์")


def find_sort_option_box_js() -> str:
    """JS that returns the centre coordinates of a sort option, or null.

    Deliberately NOT restricted to ``[role="menu"]``: the new UI renders its
    sort options inside a generic overlay (``[role="dialog"]`` /
    ``[role="listbox"]``) without a menu role.
    """
    return """
        (targetTexts) => {
            let best = null;
            for (const el of document.querySelectorAll(
                '[role="menu"] *, [role="dialog"] *, [role="listbox"] *')) {
                const text = (el.textContent || '').trim();
                if (!text || !targetTexts.includes(text)) continue;
                const r = el.getBoundingClientRect();
                if (r.width <= 0 || r.height <= 0) continue;
                const s = getComputedStyle(el);
                if (s.visibility === 'hidden' || s.display === 'none') continue;
                if (!best || r.width * r.height < best.area) {
                    best = {
                        x: r.x + r.width / 2,
                        y: r.y + r.height / 2,
                        area: r.width * r.height,
                    };
                }
            }
            return best;
        }
    """


class PostNavigatorMixin:
    """Navigate posts, switch sort modes, expand comments. Requires BrowserManager attrs."""

    config: dict
    page = None  # set by BrowserManager

    # Cached capability probe for the comment-sort UI.
    #   None -> not probed yet
    #   True -> a sort control exists and switching works
    #   False -> Facebook served a UI with no usable sort control
    # Cached because a miss costs ~6 scroll+poll retries and this is called
    # again after every safety-net reload.
    sort_ui_available: Optional[bool] = None

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

    # ------------------------------------------------------------------
    # sort UI helpers
    # ------------------------------------------------------------------

    async def _menu_is_open(self) -> bool:
        """True when any menu/listbox overlay is currently rendered."""
        return await self.page.evaluate(
            """() => {
                for (const sel of ['[role="menu"]', '[role="listbox"]']) {
                    for (const m of document.querySelectorAll(sel)) {
                        const r = m.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) return true;
                    }
                }
                return false;
            }"""
        )

    async def _close_open_menu(self) -> None:
        """Dismiss an open overlay.

        SAFETY: Escape is only sent while an overlay is actually open. With
        nothing open, Escape falls through to the post dialog and CLOSES THE
        POST entirely (observed in production).
        """
        if await self._menu_is_open():
            await self.page.keyboard.press('Escape')
            await self.page.wait_for_timeout(300)

    async def _find_sort_option_box(self, target_texts: List[str], attempts: int = 8):
        """Poll for a rendered sort option and return its centre coordinates."""
        js = find_sort_option_box_js()
        for _ in range(attempts):
            box = await self.page.evaluate(js, target_texts)
            if box:
                return box
            await self.page.wait_for_timeout(300)
        return None

    async def _try_new_ui_sort_menu(self, target_texts: List[str]) -> bool:
        """NEW-UI fallback: open the comment-sort menu via its icon/gear button.

        The 2026 Facebook UI has no text trigger - sorting lives inside a menu
        button identified only by aria-label, with the modes rendered as
        radio items. Returns True when the target mode was clicked.
        """
        for sel in SORT_MENU_BUTTON_SELECTORS:
            try:
                count = await self.page.locator(sel).count()
            except Exception:
                continue
            for i in range(min(count, 5)):
                btn = self.page.locator(sel).nth(i)
                try:
                    if not await btn.is_visible():
                        continue
                    aria = (await btn.get_attribute('aria-label')) or ''
                    # Never poke post-action ("...") menus: they look the same
                    # but never contain sort options, and clicking them can
                    # open destructive menus.
                    if any(skip in aria for skip in _SORT_MENU_SKIP_ARIA):
                        continue
                    await btn.click(timeout=2500)
                except Exception as click_err:
                    logger.debug(f"New-UI sort button click failed ({sel}): {click_err}")
                    continue

                box = await self._find_sort_option_box(target_texts, attempts=5)
                if box:
                    logger.info(
                        f"New-UI sort menu: clicking '{target_texts[0]}' at "
                        f"({box['x']:.0f}, {box['y']:.0f})"
                    )
                    await self.page.mouse.click(box['x'], box['y'])
                    await self.page.wait_for_timeout(
                        self.config['browser']['timings']['sorting_mode_switch']
                    )
                    return True
                await self._close_open_menu()
        return False

    async def switch_sorting_mode(self, mode: str = "most_recent") -> bool:
        """
        Switch comment sorting mode.

        Tries the legacy text-trigger UI first, then the new icon-menu UI.
        Sets ``sort_ui_available`` so a UI without any sort control is only
        diagnosed once instead of on every safety-net reload.

        Args:
            mode: "most_recent" (คอมเมนต์ล่าสุด), "most_relevant"
                  (เกี่ยวข้องมากที่สุด), "all" (ความคิดเห็นทั้งหมด),
                  "oldest" (เก่าที่สุด)
        """
        try:
            if mode not in SORT_LABELS:
                logger.warning(f"Unknown sorting mode: {mode}, defaulting to most_recent")
                mode = "most_recent"

            target_texts = SORT_LABELS[mode]

            # Already known that Facebook serves a UI without a sort control:
            # skip the expensive probe entirely.
            if self.sort_ui_available is False:
                logger.debug("Comment sort UI unavailable on this page (cached) - skipping switch")
                return False

            logger.info(f"Switching to '{mode}' comment view...")

            # ---- STEP 1: legacy UI - locate the TEXT trigger -----------------
            # The trigger shows the CURRENT sort mode (e.g. "เกี่ยวข้องมากที่สุด").
            # CSS :has-text() selectors miss it because Facebook renders the label
            # in deeply nested spans, so we match trimmed textContent instead and
            # mark the element for a trusted Playwright click.
            # RETRY: right after page load the comments section (and its sort
            # button) may not be rendered yet - poll for up to ~15s.
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
                            // Facebook renders hidden duplicates for other viewports -
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
                    SORT_TRIGGER_LABELS
                )
                if trigger_text:
                    break
                # LATENCY (2026-08-23): was 2500ms - right after a reload this
                # retry dominated recovery time (up to 6x2.5s=15s before the
                # feed was usable). 900ms still gives React time to render.
                logger.info(f"Sort trigger not rendered yet (attempt {attempt + 1}/6), scrolling and retrying...")
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.page.wait_for_timeout(900)

            if not trigger_text:
                # ---- STEP 2: new UI - icon/gear menu, no text trigger ---------
                logger.info("No text sort trigger - trying new Facebook comment-sort menu")
                if await self._try_new_ui_sort_menu(target_texts):
                    self.sort_ui_available = True
                    logger.info(f"OK New-UI sort menu switched to '{mode}'")
                    return True

                self.sort_ui_available = False
                logger.warning(
                    f"Comment sort UI not available (new Facebook UI): neither a text "
                    f"trigger nor a sort menu with '{mode}' was found. Newest comments "
                    f"cannot be pulled into view by sorting - relying on the full "
                    f"sweep + ID ordering instead."
                )
                await self._take_screenshot("02_no_sorting_control")
                return False

            self.sort_ui_available = True
            logger.info(f"Found sorting trigger showing: {trigger_text}")

            # STEP 2b: Open the menu. The trigger div is only ~10px tall and
            # elementHandle.click() times out on it, so we click its CENTER
            # COORDINATES with real mouse events. The post dialog has its own
            # internal scroll container, so the trigger can sit BELOW the
            # viewport - scrollIntoView() first or the click lands off-target.
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
                # option scan raced), do NOT click again - that would toggle
                # the menu closed. Just poll for the option below.
                menu_open = await self._menu_is_open()

                if not menu_open:
                    box = await self.page.evaluate(locate_trigger_js, SORT_TRIGGER_LABELS)
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

                # STEP 3: POLL for the target option inside the open menu
                # (up to ~3s) instead of a single fixed-wait check - the menu
                # may animate in slightly after the click.
                option_box = await self._find_sort_option_box(target_texts, attempts=8)
                if option_box:
                    break
                logger.info(f"Menu did not open or option missing (attempt {attempt + 1}/4)")
                await self._close_open_menu()

            if not option_box:
                logger.warning(f"Could not find '{mode}' option in menu")
                await self._take_screenshot("04_no_option")
                # Same Escape guard as above - never risk closing the post dialog.
                await self._close_open_menu()
                return False

            logger.info(f"Found '{mode}' option, clicking at ({option_box['x']:.0f}, {option_box['y']:.0f})")

            # STEP 4: Click the option via coordinates and verify the switch.
            await self.page.mouse.click(option_box['x'], option_box['y'])
            await self.page.wait_for_timeout(self.config['browser']['timings']['sorting_mode_switch'])
            await self._take_screenshot(f"05_switched_to_{mode}")

            # Verify the trigger now displays the target mode
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

