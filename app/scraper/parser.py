"""HTML parser for Facebook comments."""
import re
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from playwright.async_api import Page, ElementHandle
from ..models.comment import Comment


logger = logging.getLogger(__name__)


class FacebookParser:
    """Parse Facebook comments from page."""
    
    def __init__(self, page: Page):
        self.page = page
    
    async def parse_comments(self) -> List[Comment]:
        """Parse all comments from the current page."""
        try:
            now = datetime.now()
            
            # Get page content
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Debug: Save full page HTML
            from pathlib import Path
            debug_file = Path("debug_full_page.html")
            debug_file.write_text(content, encoding='utf-8')
            logger.info(f"Saved full page HTML to {debug_file}")
            
            # Find all comment containers by looking for links with comment_id
            comment_links = soup.find_all('a', href=lambda x: x and 'comment_id=' in x)
            logger.info(f"Found {len(comment_links)} potential comment elements")
            
            # Debug: Print first few hrefs
            for i, link in enumerate(comment_links[:5]):
                href = link.get('href', '')
                logger.info(f"Comment link {i}: {href[:100]}")
            
            # Build a map of comments
            comment_map: Dict[str, Comment] = {}
            
            for display_order, comment_link in enumerate(comment_links):
                try:
                    # Extract comment ID from link
                    match = re.search(r'comment_id=(\d+)', comment_link.get('href', ''))
                    if not match:
                        continue
                    
                    comment_id = match.group(1)
                    logger.debug(f"Processing comment ID: {comment_id} (order: {display_order})")
                    
                    # Find the comment container (traverse up to find containing div)
                    container = self._find_comment_container(comment_link)
                    if not container:
                        logger.debug(f"No container found for comment {comment_id}")
                        continue
                    
                    # Extract comment data with display order
                    comment_data = self._parse_comment_from_soup(container, comment_id, comment_link, now, display_order)
                    if comment_data:
                        comment_map[comment_id] = comment_data
                        logger.info(f"Parsed comment {comment_id} (order {display_order}): {comment_data.author} - {comment_data.message[:50]}")
                    else:
                        logger.debug(f"Failed to parse comment data for {comment_id}")
                        
                except Exception as e:
                    logger.debug(f"Failed to parse comment: {e}")
                    continue
            
            # Build tree structure (for now, all are root comments)
            root_comments = list(comment_map.values())
            
            logger.info(f"Parsed {len(root_comments)} comments")
            return root_comments
            
        except Exception as e:
            logger.error(f"Error parsing comments: {e}")
            return []
    
    def _find_comment_container(self, element):
        """Find the smallest container with author, message, and timestamp."""
        current = element.parent
        max_depth = 15
        depth = 0
        
        while current and depth < max_depth:
            if current.name == 'div':
                # Check if this container has both author and message
                author_links = current.find_all('a', href=lambda x: x and '/user/' in x)
                message_divs = current.find_all('div', dir='auto')
                
                # Found a container with both author and message
                if author_links and message_divs:
                    text_len = len(current.get_text())
                    # Make sure it's not too large (not the whole page)
                    if text_len < 2000:
                        return current
                        
            current = current.parent
            depth += 1
        
        return None
    
    def _parse_comment_from_soup(self, container, comment_id: str, time_link, now: datetime, display_order: int = 0) -> Optional[Comment]:
        """Parse comment data from BeautifulSoup element."""
        try:
            # Extract author - find link with /user/ that's not a status indicator
            author = None
            author_links = container.find_all('a', href=lambda x: x and '/user/' in x)
            logger.debug(f"Comment {comment_id}: Found {len(author_links)} author links")
            
            for link in author_links:
                text = link.get_text().strip()
                logger.debug(f"Comment {comment_id}: Author link text: '{text}'")
                if text and len(text) > 2 and 'ตัวบ่งชี้' not in text and 'สถานะ' not in text:
                    author = text
                    break
            
            if not author:
                logger.debug(f"Comment {comment_id}: No author found")
                return None
            
            logger.info(f"Comment {comment_id}: Author = {author}")
            
            # Extract message - find div with dir="auto" that's not author name or timestamp
            message = None
            message_divs = container.find_all('div', dir='auto')
            logger.debug(f"Comment {comment_id}: Found {len(message_divs)} div[dir=auto]")
            
            for div in message_divs:
                text = div.get_text().strip()
                logger.debug(f"Comment {comment_id}: Checking message div: '{text[:50]}'")
                if text and text != author and 'ชั่วโมง' not in text and 'นาที' not in text and 'วินาที' not in text:
                    message = text
                    break
            
            if not message:
                logger.debug(f"Comment {comment_id}: No message found")
                return None
            
            logger.info(f"Comment {comment_id}: Message = {message[:50]}")
            
            # Extract timestamp
            time_text = time_link.get_text().strip()
            created_time = self._parse_relative_time(time_text, now) or now
            
            return Comment(
                id=comment_id,
                parent_id=None,
                tier=1,
                author=author,
                message=message,
                created_time=created_time,
                last_seen=now,
                display_order=display_order,
                is_new=False,
                children=[]
            )
            
        except Exception as e:
            logger.debug(f"Error parsing comment from soup: {e}")
            return None
    
    def _parse_relative_time(self, text: str, now: datetime) -> Optional[datetime]:
        """Parse relative time strings like '5m', '2h', '1d'."""
        try:
            text = text.lower().strip()
            
            # Just now
            if 'just now' in text or 'เมื่อสักครู่' in text:
                return now
            
            # Seconds ago
            if 's' in text or 'sec' in text or 'วินาที' in text:
                match = re.search(r'(\d+)', text)
                if match:
                    seconds = int(match.group(1))
                    return now - timedelta(seconds=seconds)
            
            # Minutes ago
            if 'm' in text or 'min' in text or 'นาที' in text:
                match = re.search(r'(\d+)', text)
                if match:
                    minutes = int(match.group(1))
                    return now - timedelta(minutes=minutes)
            
            # Hours ago
            if 'h' in text or 'hr' in text or 'ชั่วโมง' in text:
                match = re.search(r'(\d+)', text)
                if match:
                    hours = int(match.group(1))
                    return now - timedelta(hours=hours)
            
            # Days ago
            if 'd' in text or 'day' in text or 'วัน' in text:
                match = re.search(r'(\d+)', text)
                if match:
                    days = int(match.group(1))
                    return now - timedelta(days=days)
            
            # Weeks ago
            if 'w' in text or 'week' in text or 'สัปดาห์' in text:
                match = re.search(r'(\d+)', text)
                if match:
                    weeks = int(match.group(1))
                    return now - timedelta(weeks=weeks)
            
            return now
            
        except Exception as e:
            logger.debug(f"Error parsing relative time: {e}")
            return now
