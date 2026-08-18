"""Comment change detector."""
import logging
import asyncio
from typing import List, Optional, Callable
from datetime import datetime
from ..models.comment import Comment, PostInfo
from ..scraper.facebook import FacebookScraper
from ..scraper.parser import FacebookParser
from ..database.db import CommentDatabase
from .cache import CommentCache


logger = logging.getLogger(__name__)


class CommentDetector:
    """Detect new and updated comments."""
    
    def __init__(
        self,
        scraper: FacebookScraper,
        database: CommentDatabase,
        config: dict
    ):
        self.scraper = scraper
        self.database = database
        self.config = config
        self.cache = CommentCache()
        self.max_tier = config.get('monitor', {}).get('max_tier', 999)
        self.max_comments = config.get('monitor', {}).get('max_comments', 0)
        self.display_limit = config.get('monitor', {}).get('display_limit', 10)
        self.parser = None  # Will be initialized with post_url in start_monitoring
        self.is_running = False
        self.post_info: Optional[PostInfo] = None
        self.first_refresh = True  # Track if this is the first refresh to skip page reload
        self.post_author_name: Optional[str] = None  # Will be extracted from post
        
        # Callbacks
        self.on_new_comment: Optional[Callable] = None
        self.on_new_reply: Optional[Callable] = None
        self.on_refresh: Optional[Callable] = None
    
    async def start_monitoring(self, post_url: str) -> bool:
        """Start monitoring a post."""
        try:
            # Initialize parser with post_url for filtering
            self.parser = FacebookParser(
                self.scraper.page, 
                max_tier=self.max_tier, 
                max_comments=self.max_comments,
                post_url=post_url
            )
            
            # Navigate to post
            if not await self.scraper.navigate_to_post(post_url):
                return False
            
            # Extract post author for auto-reply
            self.post_author_name = await self.scraper.get_post_author()
            if self.post_author_name:
                logger.info(f"Post author detected: {self.post_author_name}")
            else:
                logger.warning("Could not detect post author - auto reply may not work")
            
            # Get sorting mode from config
            sorting_mode = self.config.get('monitor', {}).get('sorting_mode', 'most_recent')
            
            # Switch to configured sorting view (skip if 'none')
            if sorting_mode and sorting_mode != "none":
                if sorting_mode == "most_recent":
                    await self.scraper.switch_to_most_recent()
                else:
                    await self.scraper.switch_sorting_mode(sorting_mode)
            else:
                logger.info("Skipping sorting mode change (sorting_mode='none')")
            
            # Get post info
            self.post_info = await self.database.get_post_info(post_url)
            if not self.post_info:
                self.post_info = PostInfo(url=post_url)
                await self.database.save_post_info(self.post_info)
            
            # Load existing comments from database
            existing_comments = await self.database.get_comments(post_url)
            if existing_comments:
                logger.info(f"Loaded {len(existing_comments)} existing comments from database")
                self.cache.update(existing_comments)
            
            self.is_running = True
            logger.info(f"Started monitoring post: {post_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            return False
    
    async def refresh_comments(self) -> List[Comment]:
        """Refresh and detect new comments."""
        try:
            if not self.is_running or not self.post_info:
                return []
            
            # Skip refresh on first run (page already loaded during startup)
            if self.first_refresh:
                logger.info("First refresh - skipping page reload (already loaded)")
                self.first_refresh = False
            else:
                # Check if force_refresh_mode is enabled
                force_refresh = self.config.get('monitor', {}).get('force_refresh_mode', False)
                if force_refresh:
                    logger.info("Force refresh mode enabled - toggling sorting to refresh")
                    await self.scraper.force_refresh_comments()
                    # Wait a bit and scroll to ensure comments are loaded
                    await self.scraper.page.wait_for_timeout(self.config['monitor']['timings']['force_refresh_scroll_wait'])
                    await self.scraper.page.evaluate("window.scrollBy(0, 200)")
                    await self.scraper.page.wait_for_timeout(self.config['monitor']['timings']['force_refresh_scroll_delay'])
                else:
                    # Use fast page refresh instead of full navigation
                    logger.info("Using fast page refresh")
                    await self.scraper.refresh_page()
            
            # ALWAYS expand comments to catch new hidden comments (regardless of first_refresh)
            logger.info("Expanding all comments to detect new ones...")
            await self.scraper.expand_all_comments(max_tier=self.max_tier)
            
            # Force scroll to ensure Facebook loads all comments (especially new ones)
            await self.scraper.page.evaluate("window.scrollTo(0, 0)")
            await self.scraper.page.wait_for_timeout(self.config['monitor']['timings']['page_refresh_scroll_wait'])
            await self.scraper.page.evaluate("window.scrollBy(0, 300)")
            await self.scraper.page.wait_for_timeout(self.config['monitor']['timings']['page_refresh_scroll_down'])
            
            # Parse comments
            comments = await self.parser.parse_comments()
            logger.info(f"[DEBUG] Parser returned {len(comments)} comments")
            for i, comment in enumerate(comments[:10]):  # Show first 10
                logger.info(f"[DEBUG] Comment {i+1}: {comment.message[:50]}... (tier={comment.tier})")
            
            # Detect changes
            new_comments, updated_comments = self.cache.update(comments)
            
            # Save to database
            all_flat_comments = self._flatten_comments(comments)
            await self.database.save_comments_batch(all_flat_comments, self.post_info.url)
            
            # Update last refresh time only (no statistics)
            self.post_info.last_refresh = datetime.now()
            
            logger.info(f"Calling on_refresh callback with {len(comments)} comments, {len(new_comments)} new, {len(updated_comments)} updated")
            logger.info(f"self.on_refresh = {self.on_refresh}")
            logger.info(f"self.on_new_comment = {self.on_new_comment}")
            logger.info(f"self.on_new_reply = {self.on_new_reply}")
            
            # Trigger callbacks
            for comment in new_comments:
                if comment.tier == 1 and self.on_new_comment:
                    await self.on_new_comment(comment)
                elif comment.tier > 1 and self.on_new_reply:
                    await self.on_new_reply(comment)
                
                # Auto reply if enabled and author matches
                await self._check_auto_reply(comment)
            
            if self.on_refresh:
                logger.info("Calling on_refresh callback now...")
                await self.on_refresh(comments, self.post_info)
                logger.info("on_refresh callback completed")
            else:
                logger.warning("on_refresh callback is None, cannot call!")
            
            return comments
            
        except Exception as e:
            logger.error(f"Error refreshing comments: {e}")
            return []
    
    async def monitor_loop(self, post_url: str) -> None:
        """Main monitoring loop."""
        if not await self.start_monitoring(post_url):
            logger.error("Failed to start monitoring")
            return
        
        # Convert milliseconds to seconds for asyncio.sleep
        refresh_interval_ms = self.config['monitor']['refresh_interval']
        refresh_interval = refresh_interval_ms / 1000.0
        
        while self.is_running:
            try:
                # Refresh comments and update display
                await self.refresh_comments()
                
                # Sleep for the configured interval before next refresh
                await asyncio.sleep(refresh_interval)
                
            except KeyboardInterrupt:
                # User pressed Ctrl+C - stop monitoring
                logger.info("Monitoring stopped by user")
                self.stop_monitoring()
                raise  # Re-raise to propagate to main()
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(self.config['monitor']['timings']['error_retry_delay'] / 1000.0)
    
    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self.is_running = False
        logger.info("Stopped monitoring")
    
    async def _check_auto_reply(self, comment: Comment) -> None:
        """Check if auto reply should be triggered for this comment."""
        try:
            # Check if auto_reply is enabled
            auto_reply_config = self.config.get('auto_reply', {})
            if not auto_reply_config.get('enabled', False):
                return
            
            # Use detected post author (from page) instead of config
            post_owner_name = self.post_author_name
            if not post_owner_name:
                logger.warning("Auto reply enabled but post author was not detected")
                return
            
            reply_message = auto_reply_config.get('reply_message', '').strip()
            if not reply_message:
                logger.warning("Auto reply enabled but reply_message is empty")
                return
            
            reply_tier = auto_reply_config.get('reply_tier', 2)
            
            # Check if this comment matches criteria
            # 1. Comment tier must be reply_tier - 1 (e.g., tier 1 for reply_tier 2)
            # 2. Author must be the post owner
            if comment.tier == reply_tier - 1 and post_owner_name.lower() in comment.author.lower():
                logger.info(f"Auto reply triggered for post owner's comment by {comment.author}")
                logger.info(f"Comment ID: {comment.id}")
                logger.info(f"Comment: {comment.message[:50]}...")
                
                # Post reply using the new reply_to_comment function
                success = await self.scraper.reply_to_comment(comment.id, reply_message)
                
                if success:
                    logger.info(f"Auto reply posted successfully to comment {comment.id}")
                else:
                    logger.error(f"Failed to post auto reply to comment {comment.id}")
                    
        except Exception as e:
            logger.error(f"Error in auto reply: {e}", exc_info=True)
    
    def _flatten_comments(self, comments: List[Comment]) -> List[Comment]:
        """Flatten nested comment tree."""
        result = []
        for comment in comments:
            result.append(comment)
            if comment.children:
                result.extend(self._flatten_comments(comment.children))
        return result
    
    def get_statistics(self) -> dict:
        """Get monitoring statistics."""
        stats = self.cache.get_statistics()
        if self.post_info:
            stats.update({
                'total_comments': self.post_info.total_comments,
                'total_replies': self.post_info.total_replies,
                'last_refresh': self.post_info.last_refresh
            })
        return stats
