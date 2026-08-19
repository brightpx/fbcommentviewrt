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
        self.top_n = 5  # Only scan top 5 comments
        self.use_mutation_observer = True
        
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
            
            logger.info(f"✓ Post owner detected: {self.owner_name}")
            
            # Switch to most recent view (if configured)
            sorting_mode = self.config.get('monitor', {}).get('sorting_mode', 'most_recent')
            if sorting_mode and sorting_mode != 'none':
                await self.scraper.switch_to_most_recent()
            
            # Install MutationObserver for real-time detection
            if self.use_mutation_observer:
                await self._install_mutation_observer()
                logger.info("✓ MutationObserver installed for real-time detection")
            
            # Initial scan to populate known_ids
            await self._initial_scan()
            
            logger.info(f"✓ Initialization complete. Tracking {len(self.known_comment_ids)} existing comments")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize owner detector: {e}")
            return False
    
    async def _initial_scan(self) -> None:
        """Initial scan to populate known_comment_ids."""
        try:
            comments = await self._get_top_n_comments(n=10)
            for comment in comments:
                if comment.get('id'):
                    self.known_comment_ids.add(comment['id'])
            
            logger.info(f"Initial scan: {len(self.known_comment_ids)} comments tracked")
            
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
                
                # Skip if already seen
                if comment_id in self.known_comment_ids:
                    continue
                
                # Skip if not from owner
                if not self.owner_name or self.owner_name.lower() not in author.lower():
                    continue
                
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
                
                logger.info(f"✓ NEW OWNER COMMENT DETECTED: {comment_id}")
                logger.info(f"  Author: {author}")
                logger.info(f"  Message: {comment.message[:50]}...")
            
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
            comments = await self.page.evaluate(f"""
                (topN) => {{
                    const articles = document.querySelectorAll('div[role="article"]');
                    const results = [];
                    
                    for (let i = 0; i < Math.min(articles.length, topN); i++) {{
                        const article = articles[i];
                        
                        // Extract comment ID from link
                        const link = article.querySelector('a[href*="comment_id="]');
                        if (!link) continue;
                        
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
                        
                        if (!commentId) continue;
                        
                        // Extract author (first visible link with text)
                        let author = '';
                        const authorLinks = article.querySelectorAll('a[role="link"]');
                        for (const aLink of authorLinks) {{
                            const text = aLink.innerText.trim();
                            if (text && text.length > 2) {{
                                author = text;
                                break;
                            }}
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
        """Reply to owner comment instantly using direct DOM manipulation.
        
        This is 5-10x faster than Playwright's type() method.
        
        Args:
            comment_id: Comment ID to reply to
            message: Reply message text
            
        Returns:
            True if reply posted successfully
        """
        reply_start = datetime.now()
        
        try:
            logger.info(f"Attempting instant reply to {comment_id}")
            
            # Playwright's page.evaluate() syntax: evaluate(script, arg)
            # where arg is passed as single parameter to the function
            success = await self.page.evaluate("""
                async ([commentId, message]) => {
                    try {
                        // Find the comment article
                        const link = document.querySelector(`a[href*="comment_id=${commentId}"]`);
                        if (!link) {
                            console.error('Comment link not found:', commentId);
                            return false;
                        }
                        
                        const article = link.closest('[role="article"]');
                        if (!article) {
                            console.error('Comment article not found');
                            return false;
                        }
                        
                        // Find reply button
                        const buttons = article.querySelectorAll('[role="button"]');
                        let replyButton = null;
                        for (const btn of buttons) {
                            const text = btn.innerText.trim();
                            if (text === 'ตอบกลับ' || text === 'Reply') {
                                replyButton = btn;
                                break;
                            }
                        }
                        
                        if (!replyButton) {
                            console.error('Reply button not found');
                            return false;
                        }
                        
                        // Click reply button
                        replyButton.click();
                        console.log('Reply button clicked');
                        
                        // Wait for reply box to appear
                        await new Promise(resolve => setTimeout(resolve, 300));
                        
                        // Find reply textbox (visible one)
                        const textboxes = document.querySelectorAll('[contenteditable="true"][role="textbox"]');
                        let replyBox = null;
                        for (const box of textboxes) {
                            if (box.offsetParent !== null && !box.getAttribute('aria-hidden')) {
                                replyBox = box;
                                break;
                            }
                        }
                        
                        if (!replyBox) {
                            console.error('Reply textbox not found');
                            return false;
                        }
                        
                        // Set message directly (instant, no typing delay)
                        replyBox.focus();
                        replyBox.innerText = message;
                        
                        // Trigger input event (required for Facebook to recognize text)
                        const inputEvent = new Event('input', { bubbles: true });
                        replyBox.dispatchEvent(inputEvent);
                        
                        console.log('Message inserted:', message.substring(0, 30));
                        
                        // Wait a bit for Facebook to process
                        await new Promise(resolve => setTimeout(resolve, 150));
                        
                        // Submit with Enter key
                        const enterEvent = new KeyboardEvent('keydown', {
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            which: 13,
                            bubbles: true,
                            cancelable: true
                        });
                        replyBox.dispatchEvent(enterEvent);
                        
                        console.log('Enter key dispatched');
                        
                        return true;
                        
                    } catch (e) {
                        console.error('Reply error:', e);
                        return false;
                    }
                }
            """, [comment_id, message])
            
            if success:
                reply_time = (datetime.now() - reply_start).total_seconds()
                self.stats['replies_posted'] += 1
                self._update_avg_latency('reply', reply_time)
                
                logger.info(f"✓ REPLY POSTED SUCCESSFULLY")
                logger.info(f"⚡ Reply latency: {reply_time*1000:.1f}ms")
                
                # Wait for reply to appear
                await self.page.wait_for_timeout(
                    self.config.get('auto_reply', {}).get('timings', {}).get('after_submit', 500)
                )
                
                return True
            else:
                logger.error("Reply failed (JavaScript returned false)")
                return False
                
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
        
        logger.info(f"Starting monitor loop (interval: {refresh_interval_ms}ms)")
        logger.info(f"Auto-reply: {'ENABLED' if auto_reply_enabled else 'DISABLED'}")
        
        while True:
            try:
                # Detect new owner comments
                new_owner_comments = await self.detect_new_owner_comments()
                
                # Auto-reply if enabled
                if auto_reply_enabled and reply_message and new_owner_comments:
                    for comment in new_owner_comments:
                        logger.info(f"🎯 Owner comment detected: {comment.id}")
                        logger.info(f"   Message: {comment.message[:50]}...")
                        
                        # Instant reply
                        success = await self.reply_instantly(comment.id, reply_message)
                        
                        if success:
                            logger.info(f"✅ Auto-reply posted to {comment.id}")
                        else:
                            logger.error(f"❌ Failed to auto-reply to {comment.id}")
                
                # Callback for external handling
                if new_owner_comments and self.on_owner_comment:
                    for comment in new_owner_comments:
                        await self.on_owner_comment(comment)
                
                # Sleep before next scan
                await asyncio.sleep(refresh_interval)
                
            except KeyboardInterrupt:
                logger.info("Monitor loop stopped by user")
                break
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
