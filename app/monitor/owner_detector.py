"""Owner Comment Detector - Optimized for T1 Owner Detection → T2 Reply Only
 
This module replaces the full comment monitor with a focused, high-performance
detector that ONLY tracks owner comments and replies instantly.

Key Optimizations:
- No BeautifulSoup parsing
- No tree building
- Incremental detection with known_ids
- Top-N comments only (not full scan)
- MutationObserver for real-time detection
- Direct DOM manipulation for instant replies
"""

import asyncio
import logging
import time
from typing import List, Optional, Set, Dict, Any, Callable
from datetime import datetime, timedelta
from playwright.async_api import Page

from ..models.comment import Comment
from ..scraper.facebook import FacebookScraper


logger = logging.getLogger(__name__)


class OwnerCommentDetector:
    """Ultra-fast owner comment detector focused on T1→T2 workflow only."""
    
    def __init__(self, scraper: FacebookScraper, config: dict):
        self.scraper = scraper
        self.config = config
        self.page: Page = scraper.page
        
        # Incremental detection state
        self.owner_name: Optional[str] = None
        self.post_url: str = ""
        self.monitoring_start_time: Optional[datetime] = None  # Track when monitoring started
        self.replied_comment_ids: Set[str] = set()  # Track comments we've already replied to
        self.bot_reply_texts: Set[str] = set()  # Track bot reply texts to prevent self-reply loop
        
        # Performance settings
        self.use_mutation_observer = True
        self.scan_count = 0  # Track scan count for periodic page reload
        self.last_reload_time = 0  # Track last reload timestamp
        # MEASURED (2026-08-22): passive push delivers new comments ~2.4s after
        # posting, so periodic reload is only a safety-net now. Default 120s
        # (was 10s hard reload - the source of V5's ~10s detection latency).
        # TUNED DOWN to 45s (2026-08-23, production log): FB only pushes live
        # comments for roughly the first minute after a page load — after that
        # new comments NEVER enter the DOM until a reload (top comment ID was
        # frozen for 74s at 12:57-12:58). A 120s safety-net therefore meant
        # up to ~2 minutes of blindness; 45s caps worst-case latency while
        # keeping reload churn low.
        self.reload_interval_s = int(
            self.config.get('monitor', {}).get('reload_interval_s', 45)
        )
        
        # Callbacks
        self.on_owner_comment = None
        
        # Stats
        self.stats = {
            'total_scans': 0,
            'owner_comments_detected': 0,
            'replies_posted': 0,
            'avg_detection_latency': 0.0,
            'avg_reply_latency': 0.0
        }
    
    async def initialize(self, post_url: str) -> bool:
        """Initialize detector for a specific post.
        
        Args:
            post_url: Facebook post URL to monitor
            
        Returns:
            True if initialization succeeded
        """
        try:
            self.post_url = post_url
            
            # Navigate to post
            logger.info(f"Initializing owner detector for: {post_url}")
            if not await self.scraper.navigate_to_post(post_url):
                logger.error("Failed to navigate to post")
                return False
            
            # Extract owner name (once, cached)
            self.owner_name = await self.scraper.get_post_author()
            if not self.owner_name:
                logger.error("Failed to detect post owner name")
                return False
            
            logger.info(f"OK Post owner detected: {self.owner_name}")
            
            # Switch to most recent view (if configured)
            sorting_mode = self.config.get('monitor', {}).get('sorting_mode', 'most_recent')
            if sorting_mode and sorting_mode != 'none':
                await self.scraper.switch_to_most_recent()
            
            # Install MutationObserver for real-time detection
            if self.use_mutation_observer:
                await self._install_mutation_observer()
                logger.info("OK MutationObserver installed for real-time detection")
            
            # Initialize last reload time
            self.last_reload_time = time.time()
            
            # Seed bot_reply_texts with the configured reply message so the bot
            # never treats its OWN past replies (which appear as owner comments
            # with the NEWEST IDs) as new comments to reply to — this prevents
            # the self-reply loop when the monitor restarts.
            reply_message = self.config.get('auto_reply', {}).get('reply_message', '')
            if reply_message:
                self.add_bot_reply_text(reply_message)
            
            # Record monitoring start time (BEFORE initial scan)
            self.monitoring_start_time = datetime.now()
            logger.info(f"Monitoring start time: {self.monitoring_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Initial scan (no ID tracking needed)
            await self._initial_scan()
            
            logger.info(f"OK Initialization complete. Using timestamp filtering (start: {self.monitoring_start_time.strftime('%H:%M:%S')})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize owner detector: {e}")
            return False
    
    async def _initial_scan(self) -> None:
        """Initial scan - just wait a moment for page to stabilize.
        
        No need to track comment IDs - timestamp filtering handles everything.
        Called once during initialization.
        """
        try:
            logger.info("Initial scan: Using timestamp-based detection (no ID tracking needed)")
            
            # FORCE HARD RELOAD after initial scan to clear Facebook cache
            # This ensures we see fresh DOM with any new comments
            logger.info("Forcing hard reload to clear cache...")
            await self.page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(0.5)
            self.last_reload_time = time.time()
            
            # CRITICAL (2026-08-22): Facebook resets comment sorting back to
            # its default ("ความคิดเห็นทั้งหมด") on EVERY reload, undoing the
            # switch_to_most_recent() done earlier in initialize(). Re-apply
            # it BEFORE reinstalling the observer (the switch churns the DOM
            # and would otherwise flood the fresh observer with noise).
            await self._reapply_sort_mode_after_reload()
            
            # CRITICAL: Reload wipes the JS context, so the MutationObserver
            # installed in initialize() is gone. Reinstall it now.
            if self.use_mutation_observer:
                await self._install_mutation_observer()
                logger.info("MutationObserver reinstalled after initial reload")
            
            logger.info("Hard reload complete - ready for fresh comments")
            
        except Exception as e:
            logger.warning(f"Initial scan failed: {e}")
    
    async def _reapply_sort_mode_after_reload(self) -> None:
        """Re-apply the configured comment sorting mode after a page reload.
        
        MEASURED (2026-08-22, production log): Facebook resets comment sorting
        to its default ("ความคิดเห็นทั้งหมด" / All comments) on EVERY reload.
        Without this call the page silently falls back to "All comments" after
        the initial hard reload and after every periodic safety-net reload,
        hiding the newest comments from BOTH the user's visible screen AND the
        DOM scan (newest-first ordering is required for top-N detection).
        """
        sorting_mode = self.config.get('monitor', {}).get('sorting_mode', 'most_recent')
        if not sorting_mode or sorting_mode == 'none':
            return
        try:
            switched = await self.scraper.switch_sorting_mode(sorting_mode)
            if switched:
                logger.info(f"OK Re-applied '{sorting_mode}' sorting after reload")
            else:
                # Non-fatal: switch_sorting_mode already retried ~6x; the next
                # safety-net reload will try again.
                logger.warning(
                    f"Could not re-apply '{sorting_mode}' sorting after reload "
                    f"(will retry at next safety-net reload)"
                )
        except Exception as e:
            logger.warning(f"Error re-applying sort mode after reload: {e}")
    
    async def _install_mutation_observer(self) -> None:
        """Install MutationObserver to detect new comments in real-time.
        
        MEASURED FACT (2026-08-22, measure_refresh.py, n=4): Facebook delivers
        remote comments passively ~2.4s after posting, but inserts them as a
        PLAIN DIV wrapper + characterData fill - it does NOT append
        div[role=article] or comment_id links as new nodes. The old observer
        (article/comment_id-only) therefore NEVER fired and the bot fell back
        to its 10s reload policy. This observer watches ALL node additions +
        text changes near the comment feed instead.
        """
        try:
            await self.page.evaluate("""
                () => {
                    if (window.__ownerDetectorObserver) {
                        window.__ownerDetectorObserver.disconnect();
                    }
                    
                    window.__newCommentIds = window.__newCommentIds || [];
                    window.__feedActivity = 0;
                    
                    const observer = new MutationObserver((mutations) => {
                        for (const mutation of mutations) {
                            // Track text changes anywhere (FB fills the new
                            // comment's content via characterData updates).
                            if (mutation.type === 'characterData') {
                                window.__feedActivity++;
                                continue;
                            }
                            
                            for (const node of mutation.addedNodes) {
                                if (node.nodeType !== 1) continue;
                                window.__feedActivity++;
                                
                                // Path A: a real article node appeared (some FB
                                // surfaces still do this) - extract its ID.
                                let articles = [];
                                if (node.getAttribute && node.getAttribute('role') === 'article') {
                                    articles.push(node);
                                }
                                if (node.querySelectorAll) {
                                    articles = articles.concat(Array.from(node.querySelectorAll('[role="article"]')));
                                }
                                for (const article of articles) {
                                    const link = article.querySelector('a[href*="comment_id="]');
                                    if (!link) continue;
                                    const match = link.href.match(/comment_id=(\\d+)/);
                                    if (match && !window.__newCommentIds.includes(match[1])) {
                                        window.__newCommentIds.push(match[1]);
                                        console.log('[OwnerDetector] New article detected:', match[1]);
                                    }
                                }
                            }
                        }
                    });
                    
                    const target = document.querySelector('body');
                    if (target) {
                        observer.observe(target, { 
                            childList: true, 
                            subtree: true,
                            characterData: true 
                        });
                        window.__ownerDetectorObserver = observer;
                        console.log('[OwnerDetector] Broad MutationObserver installed');
                    }
                }
            """)
            
        except Exception as e:
            logger.warning(f"Failed to install MutationObserver: {e}")
    
    async def detect_new_owner_comments(self) -> List[Comment]:
        """Detect new owner comments (T1 only) using incremental approach.
        
        This is the core detection method - called in the monitoring loop.
        Only returns NEW comments from the OWNER.
        
        Returns:
            List of new owner Comment objects (empty if none found)
        """
        detect_start = datetime.now()
        new_owner_comments = []
        
        try:
            self.stats['total_scans'] += 1
            
            # Step 1: Check MutationObserver for instant detection
            mutation_ids = await self._get_mutation_observer_comments()
            if mutation_ids:
                logger.info(f"MutationObserver detected {len(mutation_ids)} new comment(s)")
            
            # Step 2: Get TOP 30 newest comments to check for new ones.
            # MEASURED (2026-08-22): FB passively delivers new comments into the
            # open page ~2.4s after posting (plain DIV + text fill), so a plain
            # DOM scan is enough - NO reload, NO sort-mode toggle needed.
            # The reload below is only a periodic safety-net for missed events.
            # 30 (was 20, 2026-08-23): headroom so an owner comment is not
            # pushed out of the scan window when many OTHER people's comments
            # interleave between scans (non-owner comments are filtered later
            # by the author check, but they still occupy window slots).
            raw_comments = await self._get_top_n_comments(n=30)
            
            # [DEBUG] Log what we see with timestamp info
            if raw_comments:
                logger.debug(f"Found {len(raw_comments)} comments in scan")
                for i, comment in enumerate(raw_comments[:5], 1):
                    logger.debug(f"  [{i}] ID={comment.get('id')}, Author={comment.get('author')[:20]}..., Timestamp={comment.get('timestamp')}")
            
            # Step 3: Filter for NEW owner comments using timestamp + author matching
            skipped_old = 0
            candidate_comments = []  # Collect all matching comments, then pick the NEWEST
            
            for raw in raw_comments:
                comment_id = raw.get('id')
                author = raw.get('author', '')
                timestamp_str = raw.get('timestamp', '')
                
                # Parse timestamp to check if comment is NEW (after monitoring started)
                if self.monitoring_start_time and timestamp_str:
                    comment_age_minutes = self._parse_facebook_timestamp(timestamp_str)
                    if comment_age_minutes is not None:
                        # Calculate when comment was posted
                        comment_posted_time = datetime.now() - timedelta(minutes=comment_age_minutes)
                        
                        # Skip if comment is OLDER than monitoring start time
                        if comment_posted_time < self.monitoring_start_time:
                            skipped_old += 1
                            continue
                    else:
                        # Could not parse timestamp - skip to be safe
                        continue
                else:
                    # No timestamp available - skip to be safe
                    continue
                
                # Check if from owner (compare first 10 characters - Facebook may truncate names)
                if not self.owner_name or len(self.owner_name) < 10:
                    continue
                if len(author) < 10:
                    continue
                
                owner_prefix = self.owner_name[:10].lower()
                author_prefix = author[:10].lower()
                if owner_prefix != author_prefix:
                    continue
                
                # Skip if we've already replied to this comment
                if comment_id in self.replied_comment_ids:
                    continue
                
                # Skip if comment text matches bot's own reply message (prevent self-reply loop)
                comment_message = raw.get('message', '')
                if comment_message in self.bot_reply_texts:
                    logger.debug(f"Skipping bot reply comment {comment_id}: '{comment_message[:40]}...'")
                    continue
                    
                # This is a NEW owner comment! Add as candidate
                candidate_comments.append({
                    'comment_id': comment_id,
                    'author': author,
                    'message': raw.get('message', ''),
                    'timestamp_str': timestamp_str,
                    'comment_age_minutes': comment_age_minutes
                })
            
            # Sort candidates by newest first.
            # Facebook timestamps are coarse ("X hours ago"), so age alone can't
            # order comments within the same hour. Facebook comment IDs are assigned
            # chronologically (monotonic snowflake IDs), so a HIGHER id is ALWAYS a
            # NEWER comment. Use comment ID (descending) as the primary sort key —
            # this is far more precise than the coarse relative timestamp.
            candidate_comments.sort(key=lambda c: -int(c['comment_id']))
            
            for cand in candidate_comments:
                comment_id = cand['comment_id']
                comment = Comment(
                    id=comment_id,
                    parent_id=None,
                    tier=1,
                    author=cand['author'],
                    message=cand['message'],
                    created_time=datetime.now(),
                    last_seen=datetime.now(),
                    display_order=0,
                    is_new=True,
                    children=[]
                )
                
                new_owner_comments.append(comment)
                self.stats['owner_comments_detected'] += 1
                
                logger.info(f"✅ NEW OWNER COMMENT DETECTED: {comment_id}")
                logger.info(f"  Author: {cand['author']}")
                logger.info(f"  Timestamp: {cand['timestamp_str']}")
                logger.info(f"  Message: {comment.message[:50]}...")
                
                # Trigger callback if registered
                if self.on_owner_comment:
                    await self.on_owner_comment({
                        'comment_id': comment_id,
                        'author': cand['author'],
                        'text': comment.message
                    })
                
                # IMPORTANT: Reply to ONLY the newest comment, then stop
                break
            
            # Update detection latency stats
            detection_time = (datetime.now() - detect_start).total_seconds()
            self._update_avg_latency('detection', detection_time)
            
            if new_owner_comments:
                logger.info(f"⚡ Detection latency: {detection_time*1000:.1f}ms")
            
            return new_owner_comments
            
        except Exception as e:
            logger.error(f"Error in detect_new_owner_comments: {e}")
            return []
    
    async def _get_mutation_observer_comments(self) -> List[str]:
        """Get comment IDs detected by MutationObserver."""
        try:
            comment_ids = await self.page.evaluate("""
                () => {
                    const ids = window.__newCommentIds || [];
                    window.__newCommentIds = [];  // Clear after reading
                    return ids;
                }
            """)
            return comment_ids if comment_ids else []
        except:
            return []
    
    async def _get_feed_activity(self) -> int:
        """Read and reset the broad DOM-activity counter from the observer.
        
        Any node addition or text change in the page bumps this counter.
        A non-zero delta means Facebook changed the feed since we last looked,
        so a fresh scan is worthwhile WITHOUT reloading the page.
        """
        try:
            return await self.page.evaluate(
                "() => { const n = window.__feedActivity || 0; "
                "window.__feedActivity = 0; return n; }"
            )
        except:
            return 0
    
    async def _get_top_n_comments(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get top N comments using direct DOM query (NO BeautifulSoup).
        
        This is 10-20x faster than BeautifulSoup parsing.
        
        Args:
            n: Number of recent comments to retrieve
            
        Returns:
            List of raw comment dictionaries
        """
        try:
            # MEASURED (2026-08-22): Facebook passively delivers new comments
            # into the open page ~2.4s after posting, so reloading on a fixed
            # timer is unnecessary and only adds ~7-10s of render downtime.
            # New policy:
            #   - Reload ONLY as a periodic safety-net (default 120s) in case
            #     the observer missed an event or the feed went stale.
            #   - Between safety-nets: cheap scroll-to-top + DOM scan; the
            #     broad observer flags activity so scans stay meaningful.
            current_time = time.time()
            
            if current_time - self.last_reload_time > self.reload_interval_s:
                logger.info(
                    f"Safety-net reload triggered "
                    f"({self.reload_interval_s}s since last reload)"
                )
                await self.page.reload(wait_until="domcontentloaded")
                self.last_reload_time = current_time
                await asyncio.sleep(0.3)  # Reduced wait time
                
                # CRITICAL: Facebook resets comment sorting to its default
                # ("ความคิดเห็นทั้งหมด") on every reload - re-apply the
                # configured mode BEFORE scanning, otherwise the feed shows
                # "All comments" and newest comments fall out of top-N.
                await self._reapply_sort_mode_after_reload()
                
                # Reload wipes the JS context - reinstall MutationObserver
                if self.use_mutation_observer:
                    await self._install_mutation_observer()
                
                # Aggressive scroll after reload to force Facebook to load new comments
                await self.page.evaluate("""
                    window.scrollTo(0, 0);
                    setTimeout(() => window.scrollTo(0, 500), 100);
                    setTimeout(() => window.scrollTo(0, 0), 200);
                """)
                await asyncio.sleep(0.2)  # Reduced wait time
            else:
                # Normal scroll to top
                await self.page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(0.1)
            
            comments = await self.page.evaluate(f"""
                (topN) => {{
                    // Get ALL articles first
                    const allArticles = document.querySelectorAll('div[role="article"]');
                    
                    // Filter for COMMENT articles only (have aria-label with "ความคิดเห็นจาก" or "Comment by")
                    const commentArticles = Array.from(allArticles).filter(article => {{
                        const label = article.getAttribute('aria-label');
                        return label && (label.includes('ความคิดเห็นจาก') || label.includes('Comment by'));
                    }});
                    
                    // MEASURED (2026-08-22): Facebook renders every T1 comment TWICE -
                    // once NESTED inside the post's own article and once STANDALONE.
                    // A passively-pushed new comment exists ONLY as the nested copy
                    // until the next full render, so nesting must NOT be used to
                    // decide T1 vs T2 (the old nesting filter silently dropped every
                    // freshly-delivered comment until a reload re-rendered it).
                    // T2 replies are identified SOLELY by reply_comment_id in the
                    // permalink href; duplicate renders are removed by comment ID.
                    const seenIds = new Set();
                    
                    const results = [];
                    
                    // Process comment articles in DOM order (newest first)
                    for (let i = 0; i < commentArticles.length && results.length < topN; i++) {{
                        const article = commentArticles[i];
                        
                        // Extract author from aria-label.
                        // FIX (2026-08-23): FB sometimes embeds newline chars
                        // inside the aria-label between the author/timestamp
                        // parts. The old single-line regexes then failed ->
                        // author empty -> the freshly-pushed comment was
                        // SILENTLY DROPPED from the scan until the next
                        // reload. Collapse all whitespace before matching.
                        const ariaLabel = (article.getAttribute('aria-label') || '').replace(/\s+/g, ' ');
                        let author = '';
                        
                        // Extract author and timestamp from aria-label
                        // Thai format: "ความคิดเห็นจาก [Author] เมื่อ [Timestamp]"
                        // English format: "Comment by [Author] from [Timestamp]"
                        let match = ariaLabel.match(/ความคิดเห็นจาก\\s+(.+?)\\s+เมื่อ\\s+(.+)/);
                        let timestamp = null;
                        if (match) {{
                            author = match[1];
                            timestamp = match[2]; // e.g., "5 นาที", "2 ชั่วโมง", "1 วัน"
                        }} else {{
                            // Try English format
                            match = ariaLabel.match(/Comment by\\s+(.+?)\\s+from\\s+(.+)/);
                            if (match) {{
                                author = match[1];
                                timestamp = match[2]; // e.g., "5 minutes ago", "2 hours ago"
                            }}
                        }}
                        
                        if (!author) {{
                            continue;
                        }}
                        
                        // Extract comment ID from link
                        const link = article.querySelector('a[href*="comment_id="]');
                        if (!link) {{
                            continue;
                        }}
                        
                        const href = link.href;
                        let commentId = null;
                        
                        // Check for reply first
                        const replyMatch = href.match(/reply_comment_id=(\\d+)/);
                        if (replyMatch) {{
                            // T2 reply - skip (detector handles T1 only)
                            continue;
                        }} else {{
                            const commentMatch = href.match(/comment_id=(\\d+)/);
                            if (commentMatch) {{
                                commentId = commentMatch[1];
                            }}
                        }}
                        
                        if (!commentId) {{
                            continue;
                        }}
                        
                        // Dedupe: same comment rendered twice (nested + standalone)
                        if (seenIds.has(commentId)) {{
                            continue;
                        }}
                        seenIds.add(commentId);
                        
                        // Extract message (first dir=auto div with content)
                        let message = '';
                        const messageDivs = article.querySelectorAll('div[dir="auto"]');
                        for (const div of messageDivs) {{
                            const text = div.innerText.trim();
                            if (text && text !== author && text.length > 2) {{
                                message = text;
                                break;
                            }}
                        }}
                        
                        results.push({{
                            id: commentId,
                            author: author,
                            message: message,
                            href: href,
                            timestamp: timestamp
                        }});
                    }}
                    
                    return results;
                }}
            """, n)
            
            return comments if comments else []
            
        except Exception as e:
            logger.error(f"Error getting top N comments: {e}")
            # Do not swallow closed-browser errors: monitor_loop must see them
            # so it can exit and trigger cleanup instead of spinning forever.
            if 'has been closed' in str(e) or 'Target closed' in str(e):
                raise
            return []
    
    async def reply_instantly(self, comment_id: str, message: str) -> bool:
        """Reply to owner comment instantly using direct DOM manipulation + real keyboard events.
        
        This is 5-10x faster than Playwright's type() method.
        CRITICAL: Must use page.keyboard.press() for Enter, not JavaScript dispatchEvent()
        because Facebook requires trusted keyboard events.
        
        Args:
            comment_id: Comment ID to reply to
            message: Reply message text
            
        Returns:
            True if reply posted successfully
        """
        reply_start = datetime.now()
        
        try:
            logger.debug(f"Replying to comment {comment_id}")
            
            # Step 1: Click reply button using Playwright
            try:
                link = self.page.locator(f'a[href*="comment_id={comment_id}"]').first()
                article = link.locator('xpath=ancestor::div[@role="article"]').first()
                reply_button = article.locator('role=button').filter(has_text='ตอบกลับ').or_(
                    article.locator('role=button').filter(has_text='Reply')
                ).first()
                
                await reply_button.click()
                logger.debug("Reply button clicked")
                
            except Exception as e:
                logger.error(f"Failed to click reply button: {e}")
                return False
            
            # Wait for reply box to appear
            await self.page.wait_for_timeout(400)
            
            # Step 2: Use Playwright's .fill() method instead of innerText
            # .fill() properly triggers input events that enable the submit button
            try:
                # Wait a bit for reply box to be fully rendered
                await self.page.wait_for_timeout(300)
                
                # Find reply textbox specifically (aria-label contains "ตอบกลับ" or "Reply")
                # This is more reliable than using all textboxes
                reply_textbox = self.page.locator(
                    '[contenteditable="true"][role="textbox"][aria-label*="ตอบกลับ"]'
                ).or_(
                    self.page.locator('[contenteditable="true"][role="textbox"][aria-label*="Reply"]')
                ).last()
                
                # Check if reply textbox exists
                textbox_count = await reply_textbox.count()
                if textbox_count == 0:
                    logger.error("No reply textbox found (aria-label filter)")
                    return False
                
                logger.debug("Reply textbox found")
                
                # CRITICAL: Use .fill() instead of innerText
                # This properly triggers input events that enable Facebook's submit button
                await reply_textbox.fill(message)
                logger.debug("Message filled in reply box")
                
                # Wait for input to settle and submit button to enable
                await self.page.wait_for_timeout(200)
                
                # Press Enter on the textbox itself (not page.keyboard)
                await reply_textbox.press('Enter')
                
                logger.debug("Enter pressed on textbox")
                
            except Exception as e:
                logger.error(f"Failed to fill/press Enter: {e}")
                return False
            
            # Step 3: Wait for Facebook to process submission
            await self.page.wait_for_timeout(1500)
            
            # Step 4: CRITICAL VERIFICATION - Check if reply actually exists in DOM
            verification = await self.page.evaluate("""
                ([commentId, replyMessage]) => {
                    try {
                        // Find the original comment
                        const link = document.querySelector(`a[href*="comment_id=${commentId}"]`);
                        if (!link) return { success: false, error: 'comment_not_found', nestedCount: 0 };
                        
                        const article = link.closest('[role="article"]');
                        if (!article) return { success: false, error: 'article_not_found', nestedCount: 0 };
                        
                        // Count nested articles (replies are nested articles)
                        const nestedArticles = article.querySelectorAll('[role="article"]');
                        const nestedCount = nestedArticles.length;
                        
                        // Check if our reply message exists in the DOM
                        const articleText = article.innerText;
                        const hasReplyText = articleText.includes(replyMessage.substring(0, 20));
                        
                        // Check for our specific reply message in nested articles
                        let foundReply = false;
                        for (const nested of nestedArticles) {
                            if (nested.innerText.includes(replyMessage.substring(0, 20))) {
                                foundReply = true;
                                break;
                            }
                        }
                        
                        return {
                            success: nestedCount > 0 && foundReply,
                            nestedCount: nestedCount,
                            hasReplyText: hasReplyText,
                            foundReply: foundReply,
                            error: null
                        };
                    } catch (e) {
                        return { success: false, error: e.toString(), nestedCount: 0 };
                    }
                }
            """, [comment_id, message])
            
            # Check verification result
            if not verification.get('success'):
                logger.error(f"REPLY VERIFICATION FAILED!")
                logger.error(f"   Nested articles: {verification.get('nestedCount', 0)}")
                logger.error(f"   Found reply text: {verification.get('foundReply', False)}")
                logger.error(f"   Error: {verification.get('error', 'unknown')}")
                logger.error(f"   -> Reply did NOT post to Facebook!")
                return False
            
            # Success - reply verified in DOM!
            reply_time = (datetime.now() - reply_start).total_seconds()
            self.stats['replies_posted'] += 1
            self._update_avg_latency('reply', reply_time)
            
            logger.info(f"OK REPLY VERIFIED IN DOM!")
            logger.info(f"   Nested articles: {verification.get('nestedCount', 0)}")
            logger.info(f"   Found reply: {verification.get('foundReply', False)}")
            logger.info(f"Total latency: {reply_time*1000:.1f}ms")
            
            return True
                
        except Exception as e:
            logger.error(f"Error in reply_instantly: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def monitor_loop(self) -> None:
        """Main monitoring loop - lightweight and fast.
        
        This replaces the heavy detector.refresh_comments() loop.
        """
        refresh_interval_ms = self.config.get('monitor', {}).get('refresh_interval', 200)
        refresh_interval = refresh_interval_ms / 1000.0
        
        logger.info("MONITORING STARTED")
        auto_reply_enabled = self.config.get('auto_reply', {}).get('enabled', False)
        logger.info(f"   Scan interval: {refresh_interval_ms}ms | Owner: {self.owner_name} | Auto-reply: {'ON' if auto_reply_enabled else 'OFF'}")
        
        scan_count = 0
        while True:
            try:
                # Detect new owner comments
                new_owner_comments = await self.detect_new_owner_comments()
                
                # Show periodic status every 300 scans (~60 seconds at 200ms intervals)
                scan_count += 1
                if scan_count % 300 == 0:
                    logger.debug(f"Monitoring active... (scans: {scan_count})")
                
                # Sleep before next scan
                await asyncio.sleep(refresh_interval)
                
            except KeyboardInterrupt:
                logger.info("Monitor loop stopped by user")
                raise  # Re-raise to allow proper cleanup
            except Exception as e:
                # If the browser/page is gone, the loop can never recover —
                # exit so cleanup() runs instead of spinning error forever.
                if 'has been closed' in str(e) or 'Target closed' in str(e):
                    logger.error("Browser/page closed - stopping monitor loop")
                    raise
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(1.0)
    
    def _update_avg_latency(self, metric: str, value: float) -> None:
        """Update rolling average latency."""
        key = f'avg_{metric}_latency'
        count_key = f'{metric}_count'
        
        if count_key not in self.stats:
            self.stats[count_key] = 0
        
        count = self.stats[count_key]
        current_avg = self.stats[key]
        
        # Rolling average
        new_avg = (current_avg * count + value) / (count + 1)
        self.stats[key] = new_avg
        self.stats[count_key] = count + 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            **self.stats,
            'owner_name': self.owner_name,
            'monitoring_start': self.monitoring_start_time.strftime('%H:%M:%S') if self.monitoring_start_time else None,
            'avg_detection_ms': self.stats['avg_detection_latency'] * 1000,
            'avg_reply_ms': self.stats['avg_reply_latency'] * 1000
        }
    
    def add_bot_reply_text(self, text: str) -> None:
        """Register bot reply text to prevent self-reply loop.
        
        When the bot posts a reply, Facebook may show it as a new comment
        from the owner. By registering the reply text here, the detector
        will skip comments that match known bot reply messages.
        
        Args:
            text: The reply message text that the bot posted
        """
        self.bot_reply_texts.add(text)
        logger.debug(f"Registered bot reply text: '{text[:40]}...' (total: {len(self.bot_reply_texts)})")
    
    def _parse_facebook_timestamp(self, timestamp_str: str) -> Optional[int]:
        """Parse Facebook timestamp string to minutes ago.
        
        Supports both Thai and English formats:
        - Thai: "5 นาที", "2 ชั่วโมง", "1 วัน", "15 ชั่วโมงที่แล้ว", "สักครู่"
        - English: "5 minutes ago", "2 hours ago", "1 day ago", "just now"
        
        Args:
            timestamp_str: Timestamp string from aria-label
            
        Returns:
            Number of minutes ago, or None if parsing failed
        """
        if not timestamp_str:
            return None
        
        timestamp_str = timestamp_str.strip().lower()
        
        # Handle "just now" / "สักครู่" / "ไม่กี่วินาทีที่แล้ว" (a few seconds ago)
        if timestamp_str in ['just now', 'สักครู่', 'a moment ago', 'ไม่กี่วินาทีที่แล้ว', 'a few seconds ago']:
            return 0
        
        import re
        
        # Try Thai format: "5 นาที", "2 ชั่วโมง", "1 วัน", "15 ชั่วโมงที่แล้ว"
        # Also handles "ประมาณ 5 นาทีที่แล้ว" (approximate format)
        # Also handles "หนึ่งวันที่แล้ว" (Thai word for 1)
        # Match patterns with optional "ประมาณ" prefix and optional "ที่แล้ว" suffix
        
        # Map Thai number words to digits
        thai_num_map = {
            'หนึ่ง': '1', 'สอง': '2', 'สาม': '3', 'สี่': '4', 'ห้า': '5',
            'หก': '6', 'เจ็ด': '7', 'แปด': '8', 'เก้า': '9', 'สิบ': '10'
        }
        
        # Try with Thai number words first
        match = re.match(r'(?:ประมาณ\s*)?(หนึ่ง|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|สิบ)\s*(นาที|ชั่วโมง|วัน)(?:ที่แล้ว)?', timestamp_str)
        if match:
            value = int(thai_num_map[match.group(1)])
            unit = match.group(2)
            
            if unit == 'นาที':
                return value
            elif unit == 'ชั่วโมง':
                return value * 60
            elif unit == 'วัน':
                return value * 60 * 24
        
        # Try with numeric digits
        match = re.match(r'(?:ประมาณ\s*)?(\d+)\s*(นาที|ชั่วโมง|วัน)(?:ที่แล้ว)?', timestamp_str)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            if unit == 'นาที':
                return value
            elif unit == 'ชั่วโมง':
                return value * 60
            elif unit == 'วัน':
                return value * 60 * 24
        
        # Try English format: "5 minutes ago", "2 hours ago", "1 day ago"
        match = re.match(r'(\d+)\s*(minute|hour|day)s?\s*ago', timestamp_str)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            if unit == 'minute':
                return value
            elif unit == 'hour':
                return value * 60
            elif unit == 'day':
                return value * 60 * 24
        
        logger.warning(f"Failed to parse timestamp: {timestamp_str}")
        return None
