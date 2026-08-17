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
        self.parser = FacebookParser(scraper.page)
        self.is_running = False
        self.post_info: Optional[PostInfo] = None
        
        # Callbacks
        self.on_new_comment: Optional[Callable] = None
        self.on_new_reply: Optional[Callable] = None
        self.on_refresh: Optional[Callable] = None
    
    async def start_monitoring(self, post_url: str) -> bool:
        """Start monitoring a post."""
        try:
            # Navigate to post
            if not await self.scraper.navigate_to_post(post_url):
                return False
            
            # Switch to "Most Recent" view to see latest comments
            await self.scraper.switch_to_most_recent()
            
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
            
            # Expand all comments
            await self.scraper.expand_all_comments()
            
            # Parse comments
            comments = await self.parser.parse_comments()
            
            # Detect changes
            new_comments, updated_comments = self.cache.update(comments)
            
            # Save to database
            all_flat_comments = self._flatten_comments(comments)
            await self.database.save_comments_batch(all_flat_comments, self.post_info.url)
            
            # Update statistics
            total_comments, total_replies = await self.database.get_statistics(self.post_info.url)
            self.post_info.total_comments = total_comments
            self.post_info.total_replies = total_replies
            self.post_info.last_refresh = datetime.now()
            
            # Trigger callbacks
            for comment in new_comments:
                if comment.tier == 1 and self.on_new_comment:
                    await self.on_new_comment(comment)
                elif comment.tier > 1 and self.on_new_reply:
                    await self.on_new_reply(comment)
            
            if self.on_refresh:
                await self.on_refresh(comments, len(new_comments), len(updated_comments))
            
            return comments
            
        except Exception as e:
            logger.error(f"Error refreshing comments: {e}")
            return []
    
    async def monitor_loop(self, post_url: str) -> None:
        """Main monitoring loop."""
        if not await self.start_monitoring(post_url):
            logger.error("Failed to start monitoring")
            return
        
        refresh_interval = self.config['monitor']['refresh_interval']
        
        while self.is_running:
            try:
                await self.refresh_comments()
                await asyncio.sleep(refresh_interval)
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(refresh_interval)
    
    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self.is_running = False
        logger.info("Stopped monitoring")
    
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
