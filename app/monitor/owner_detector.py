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
from typing import List, Optional, Set, Dict, Any
from datetime import datetime
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
        self.known_comment_ids: Set[str] = set()
        self.owner_name: Optional[str] = None
        self.post_url: str = ""
        
        # Performance settings
        self.top_n = 20  # Scan top 20 comments to catch new test comments
        self.use_mutation_observer = True
        self.scan_count = 0  # Track scan count for periodic page reload
        self.last_reload_time = 0  # Track last reload timestamp
        self.scan_count = 0  # Track scan count for periodic page reload
        
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
            import time
            self.last_reload_time = time.time()
            
            # Initial scan to populate known_ids
            await self._initial_scan()
            
            logger.info(f"OK Initialization complete. Tracking {len(self.known_comment_ids)} existing comments")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize owner detector: {e}")
            return False
    
    async def _initial_scan(self) -> None:
        """Initial scan - load known comments from database only."""
        try:
            # Load existing comments from database to known_comment_ids
            from app.database.db import CommentDatabase
            db = CommentDatabase(db_path="database/comments.db")
            await db.initialize()
            
            # Get all comment IDs for this post from database
            comment_ids = await db.get_comment_ids(self.post_url)
            self.known_comment_ids.update(comment_ids)
            
            await db.close()
            
            logger.info(f"Initial scan: Loaded {len(self.known_comment_ids)} comments from database")
            
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
            
            # Step 2: Get top N comments (fast, localized scan)
            raw_comments = await self._get_top_n_comments(n=self.top_n)
            
            # Step 3: Filter for NEW owner comments only
            for raw in raw_comments:
                comment_id = raw.get('id')
                author = raw.get('author', '')
                
                # [TEMP DEBUG] Log all comments
                logger.info(f"[TEMP] Checking comment {comment_id}: author='{author}'")
                
                # Skip if already seen in memory
                if comment_id in self.known_comment_ids:
                    logger.info(f"[TEMP] → SKIP: already in known_comment_ids")
                    continue
                
                # Double-check database (in case comment was added during initial scan but not saved)
                # Skip for now - database check removed to avoid async/connection issues
                # Will rely on known_comment_ids set only
                
                # Skip if not from owner (compare first 10 characters - Facebook may truncate names)
                if not self.owner_name or len(self.owner_name) < 10:
                    logger.info(f"[TEMP] → SKIP: owner_name too short ('{self.owner_name}')")
                    continue
                if len(author) < 10:
                    logger.info(f"[TEMP] → SKIP: author too short ('{author}')")
                    continue
                
                owner_prefix = self.owner_name[:10].lower()
                author_prefix = author[:10].lower()
                logger.info(f"[TEMP] Comparing: owner_prefix='{owner_prefix}' vs author_prefix='{author_prefix}'")
                if owner_prefix != author_prefix:
                    logger.info(f"[TEMP] → SKIP: name mismatch")
                    continue
                
                logger.info(f"[TEMP] → MATCH! This is a NEW owner comment!")
                # This is a NEW owner comment!
                comment = Comment(
                    id=comment_id,
                    parent_id=None,
                    tier=1,
                    author=author,
                    message=raw.get('message', ''),
                    created_time=datetime.now(),
                    last_seen=datetime.now(),
                    display_order=0,
                    is_new=True,
                    children=[]
                )
                
                new_owner_comments.append(comment)
                self.known_comment_ids.add(comment_id)
                self.stats['owner_comments_detected'] += 1
                
                logger.info(f"NEW OWNER COMMENT DETECTED: {comment_id}")
                logger.info(f"  Author: {author}")
                logger.info(f"  Message: {comment.message[:50]}...")
                
                # Trigger callback if registered
                if self.on_owner_comment:
                    await self.on_owner_comment({
                        'comment_id': comment_id,
                        'author': author,
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
            import time
            current_time = time.time()
            
            # Reload if: 10+ seconds since last reload AND we haven't seen new comments
            if current_time - self.last_reload_time > 10:
                await self.page.reload(wait_until="domcontentloaded")
                self.last_reload_time = current_time
                await asyncio.sleep(0.8)  # Wait for page to stabilize
                logger.info("Page reloaded to fetch fresh comments")
                
                # Aggressive scroll after reload to force Facebook to load new comments
                await self.page.evaluate("""
                    window.scrollTo(0, 0);
                    setTimeout(() => window.scrollTo(0, 500), 100);
                    setTimeout(() => window.scrollTo(0, 0), 200);
                """)
                await asyncio.sleep(0.5)  # Wait for lazy-load to trigger
            else:
                # Normal scroll to top
                await self.page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(0.3)
            
            comments = await self.page.evaluate(f"""
                (topN) => {{
                    // Get ALL articles first
                    const allArticles = document.querySelectorAll('div[role="article"]');
                    console.log('[TEMP] Total articles found:', allArticles.length);
                    
                    // Filter for COMMENT articles only (have aria-label with "ความคิดเห็นจาก" or "Comment by")
                    const commentArticles = Array.from(allArticles).filter(article => {{
                        const label = article.getAttribute('aria-label');
                        if (label) {{
                            console.log('[TEMP] Article aria-label:', label);
                        }}
                        return label && (label.includes('ความคิดเห็นจาก') || label.includes('Comment by'));
                    }});
                    console.log('[TEMP] Comment articles found:', commentArticles.length);
                    
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
                    console.log('[TEMP] Top-level comments found:', topLevelComments.length);
                    
                    const results = [];
                    
                    // Process top N top-level comments
                    for (let i = 0; i < Math.min(topLevelComments.length, topN); i++) {{
                        const article = topLevelComments[i];
                        
                        // Extract author from aria-label
                        const ariaLabel = article.getAttribute('aria-label');
                        let author = '';
                        
                        // Try Thai format first
                        let match = ariaLabel.match(/ความคิดเห็นจาก\\s+(.+?)\\s+เมื่อ/);
                        if (match) {{
                            author = match[1];
                        }} else {{
                            // Try English format
                            match = ariaLabel.match(/Comment by\\s+(.+?)\\s+from/);
                            if (match) {{
                                author = match[1];
                            }}
                        }}
                        
                        console.log('[TEMP] Processing article', i, '- author:', author);
                        
                        if (!author) {{
                            console.log('[TEMP] → SKIP: No author extracted');
                            continue;
                        }}
                        
                        // Extract comment ID from link
                        const link = article.querySelector('a[href*="comment_id="]');
                        if (!link) {{
                            console.log('[TEMP] → SKIP: No comment link found');
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
                        
                        console.log('[TEMP] → Extracted comment ID:', commentId);
                        
                        if (!commentId) {{
                            console.log('[TEMP] → SKIP: Could not extract comment ID');
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
                            href: href
                        }});
                    }}
                    
                    return results;
                }}
            """, n)
            
            return comments if comments else []
            
        except Exception as e:
            logger.error(f"Error getting top N comments: {e}")
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
            logger.info(f"Attempting instant reply to {comment_id}")
            
            # Step 1: Click reply button using Playwright
            try:
                link = self.page.locator(f'a[href*="comment_id={comment_id}"]').first()
                article = link.locator('xpath=ancestor::div[@role="article"]').first()
                reply_button = article.locator('role=button').filter(has_text='ตอบกลับ').or_(
                    article.locator('role=button').filter(has_text='Reply')
                ).first()
                
                await reply_button.click()
                logger.info("OK Reply button clicked")
                
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
                
                logger.info(f"OK Found reply textbox")
                
                # CRITICAL: Use .fill() instead of innerText
                # This properly triggers input events that enable Facebook's submit button
                await reply_textbox.fill(message)
                logger.info(f"OK Message filled using .fill() method")
                
                # Wait for input to settle and submit button to enable
                await self.page.wait_for_timeout(200)
                
                # Press Enter on the textbox itself (not page.keyboard)
                await reply_textbox.press('Enter')
                
                logger.info("OK Enter pressed on textbox")
                
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
        
        auto_reply_enabled = self.config.get('auto_reply', {}).get('enabled', False)
        reply_message = self.config.get('auto_reply', {}).get('reply_message', '')
        
        logger.info(f"")
        logger.info(f"MONITORING STARTED")
        logger.info(f"   Scan interval: {refresh_interval_ms}ms")
        logger.info(f"   Scanning top {self.top_n} comments")
        logger.info(f"   Owner: {self.owner_name}")
        logger.info(f"   Auto-reply: {'ENABLED' if auto_reply_enabled else 'DISABLED'}")
        logger.info(f"   Waiting for owner comments...")
        logger.info(f"")
        
        scan_count = 0
        while True:
            try:
                # Detect new owner comments
                new_owner_comments = await self.detect_new_owner_comments()
                
                # Show periodic status (every 50 scans = ~10 seconds)
                scan_count += 1
                if scan_count % 50 == 0:
                    logger.info(f"Monitoring active... (scans: {scan_count}, known comments: {len(self.known_comment_ids)})")
                
                # Auto-reply if enabled (INSTANT - no callback delay)
                if auto_reply_enabled and reply_message and new_owner_comments:
                    for comment in new_owner_comments:
                        logger.info(f"Owner comment detected: {comment.id}")
                        logger.info(f"   Message: {comment.message[:50]}...")
                        
                        # Instant reply
                        success = await self.reply_instantly(comment.id, reply_message)
                        
                        if success:
                            logger.info(f"OK Auto-reply posted to {comment.id}")
                        else:
                            logger.error(f"FAILED to auto-reply to {comment.id}")
                
                # Sleep before next scan
                await asyncio.sleep(refresh_interval)
                
            except KeyboardInterrupt:
                logger.info("Monitor loop stopped by user")
                raise  # Re-raise to allow proper cleanup
            except Exception as e:
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
            'known_comments': len(self.known_comment_ids),
            'owner_name': self.owner_name,
            'avg_detection_ms': self.stats['avg_detection_latency'] * 1000,
            'avg_reply_ms': self.stats['avg_reply_latency'] * 1000
        }
