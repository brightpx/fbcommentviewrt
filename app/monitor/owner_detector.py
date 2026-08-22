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
            
            # CRITICAL: Reload wipes the JS context, so the MutationObserver
            # installed in initialize() is gone. Reinstall it now.
            if self.use_mutation_observer:
                await self._install_mutation_observer()
                logger.info("MutationObserver reinstalled after initial reload")
            
            logger.info("Hard reload complete - ready for fresh comments")
            
        except Exception as e:
            logger.warning(f"Initial scan failed: {e}")
    
    async def _install_mutation_observer(self) -> None:
        """Install MutationObserver to detect new comments in real-time."""
        try:
            await self.page.evaluate("""
                () => {
                    if (window.__ownerDetectorObserver) {
                        window.__ownerDetectorObserver.disconnect();
                    }
                    
                    window.__newCommentIds = window.__newCommentIds || [];
                    
                    const observer = new MutationObserver((mutations) => {
                        for (const mutation of mutations) {
                            for (const node of mutation.addedNodes) {
                                if (node.nodeType === 1) {
                                    // Check if this is a comment article
                                    if (node.getAttribute && node.getAttribute('role') === 'article') {
                                        const link = node.querySelector('a[href*="comment_id="]');
                                        if (link) {
                                            const match = link.href.match(/comment_id=(\\d+)/);
                                            if (match && !window.__newCommentIds.includes(match[1])) {
                                                window.__newCommentIds.push(match[1]);
                                                console.log('[OwnerDetector] New comment detected:', match[1]);
                                            }
                                        }
                                    }
                                    
                                    // Also check children
                                    if (node.querySelectorAll) {
                                        const articles = node.querySelectorAll('[role="article"]');
                                        articles.forEach(article => {
                                            const link = article.querySelector('a[href*="comment_id="]');
                                            if (link) {
                                                const match = link.href.match(/comment_id=(\\d+)/);
                                                if (match && !window.__newCommentIds.includes(match[1])) {
                                                    window.__newCommentIds.push(match[1]);
                                                    console.log('[OwnerDetector] New comment detected (child):', match[1]);
                                                }
                                            }
                                        });
                                    }
                                }
                            }
                        }
                    });
                    
                    const target = document.querySelector('body');
                    if (target) {
                        observer.observe(target, { 
                            childList: true, 
                            subtree: true 
                        });
                        window.__ownerDetectorObserver = observer;
                        console.log('[OwnerDetector] MutationObserver installed');
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
            
            # Step 2: Get TOP 20 newest comments to check for new ones
            raw_comments = await self._get_top_n_comments(n=20)
            
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
    
    async def _get_top_n_comments(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get top N comments using direct DOM query (NO BeautifulSoup).
        
        This is 10-20x faster than BeautifulSoup parsing.
        
        Args:
            n: Number of recent comments to retrieve
            
        Returns:
            List of raw comment dictionaries
        """
        try:
            # Smart reload: Only when MutationObserver detects changes but scan finds nothing new
            # This means Facebook has new comments but they're not in DOM yet
            current_time = time.time()
            
            # Reload if: 10+ seconds since last reload AND we haven't seen new comments
            if current_time - self.last_reload_time > 10:
                await self.page.reload(wait_until="domcontentloaded")
                self.last_reload_time = current_time
                await asyncio.sleep(0.3)  # Reduced wait time
                
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
                    
                    // Further filter for TOP-LEVEL comments only (T1) - exclude nested articles (T2 replies)
                    const topLevelComments = commentArticles.filter(article => {{
                        // Check if this article is nested inside another article
                        let parent = article.parentElement;
                        while (parent) {{
                            if (parent !== article && parent.getAttribute('role') === 'article') {{
                                return false; // This is a nested article (T2), skip it
                            }}
                            parent = parent.parentElement;
                        }}
                        return true; // This is a top-level comment (T1)
                    }});
                    
                    const results = [];
                    
                    // Process top N top-level comments
                    for (let i = 0; i < Math.min(topLevelComments.length, topN); i++) {{
                        const article = topLevelComments[i];
                        
                        // Extract author from aria-label
                        const ariaLabel = article.getAttribute('aria-label');
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
                            commentId = replyMatch[1];
                        }} else {{
                            const commentMatch = href.match(/comment_id=(\\d+)/);
                            if (commentMatch) {{
                                commentId = commentMatch[1];
                            }}
                        }}
                        
                        if (!commentId) {{
                            continue;
                        }}
                        
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
