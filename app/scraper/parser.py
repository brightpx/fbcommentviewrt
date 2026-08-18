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
    
    def __init__(self, page: Page, max_tier: int = 999, max_comments: int = 0, post_url: str = ""):
        self.page = page
        self.max_tier = max_tier
        self.max_comments = max_comments
        self.post_url = post_url
        self._container_cache: Dict[int, Any] = {}  # Cache container lookups by element id
    
    async def parse_comments(self) -> List[Comment]:
        """Parse all comments from the current page."""
        try:
            now = datetime.now()
            
            # Clear cache for new parse
            self._container_cache.clear()

            # Get page content
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Each comment timestamp link has:
            #   - Top-level:  ?comment_id=XXX
            #   - Reply:      ?comment_id=PARENT_ID&reply_comment_id=REPLY_ID
            all_comment_links = soup.find_all('a', href=lambda x: x and 'comment_id=' in x)
            logger.info(f"Found {len(all_comment_links)} total comment links")
            
            # Filter to only comments from the target post URL
            # Extract post ID from post_url (e.g., /posts/2972275236267806/)
            post_id_match = re.search(r'/posts/(\d+)/', self.post_url) or re.search(r'permalink/(\d+)', self.post_url)
            if post_id_match:
                post_id = post_id_match.group(1)
                # Filter comment links that have proper post path structure
                # Must match: /posts/{post_id}/?comment_id= or permalink/{post_id}?comment_id=
                post_path_pattern = f'(/posts/{post_id}/|permalink/{post_id})\\?comment_id='
                comment_links = [
                    link for link in all_comment_links 
                    if re.search(post_path_pattern, link.get('href', ''))
                ]
                logger.info(f"Filtered to {len(comment_links)} comments from target post (ID: {post_id})")
            else:
                comment_links = all_comment_links
                logger.warning(f"Could not extract post ID from URL: {self.post_url}")

            # FALLBACK: Find comment containers without links by searching for role="article" divs
            # This catches newly posted comments that Facebook hasn't rendered links for yet
            all_articles = soup.find_all('div', attrs={'role': 'article'})
            logger.info(f"Found {len(all_articles)} article containers (potential comments without links)")
            
            # Build a set of comment IDs we already have from links
            linked_comment_ids = set()
            for link in comment_links:
                href = link.get('href', '')
                if match := re.search(r'comment_id=(\d+)', href):
                    linked_comment_ids.add(match.group(1))
            
            # Try to extract comment IDs from articles that don't have links yet
            unlisted_containers = []
            for article in all_articles:
                # Look for comment_id in any nested links within this article
                nested_links = article.find_all('a', href=lambda x: x and 'comment_id=' in x)
                if not nested_links:
                    # No comment links in this article - might be a fresh comment
                    unlisted_containers.append(article)
                    continue
                    
                # Check if this article has comment IDs we don't already know about
                for nested_link in nested_links:
                    href = nested_link.get('href', '')
                    if match := re.search(r'comment_id=(\d+)', href):
                        cid = match.group(1)
                        if cid not in linked_comment_ids:
                            # Found a comment ID in article that wasn't in our main link list
                            comment_links.append(nested_link)
                            linked_comment_ids.add(cid)
            
            if unlisted_containers:
                logger.info(f"Found {len(unlisted_containers)} article containers without comment links (likely fresh comments)")
            
            comment_map: Dict[str, Comment] = {}
            display_order = 0
            t1_count = 0

            for comment_link in comment_links:
                # Check limit BEFORE processing - stop when we have enough T1 comments
                if self.max_comments > 0 and t1_count >= self.max_comments:
                    logger.info(f"Reached max_comments limit ({self.max_comments}), stopping parse")
                    break
                
                try:
                    href = comment_link.get('href', '')
                    reply_match = re.search(r'reply_comment_id=(\d+)', href)
                    parent_match = re.search(r'comment_id=(\d+)', href)

                    if reply_match:
                        # This is a reply — use reply_comment_id as the real ID
                        comment_id = reply_match.group(1)
                        parent_id = parent_match.group(1) if parent_match else None
                        tier = 2
                    elif parent_match:
                        comment_id = parent_match.group(1)
                        parent_id = None
                        tier = 1
                    else:
                        logger.debug(f"[SKIP] No comment_id found in href: {href[:100]}")
                        continue

                    # Skip comments beyond max_tier
                    if tier > self.max_tier:
                        logger.debug(f"[SKIP] Comment {comment_id} tier={tier} > max_tier={self.max_tier}")
                        continue

                    if comment_id in comment_map:
                        logger.debug(f"[SKIP] Comment {comment_id} already parsed (duplicate)")
                        continue  # already parsed

                    container = self._find_comment_container(comment_link)
                    if not container:
                        logger.warning(f"No container found for comment {comment_id} (tier={tier}, href={href[:100]})")
                        continue

                    comment_data = self._parse_comment_from_soup(
                        container, comment_id, comment_link, now, display_order, parent_id, tier
                    )
                    if comment_data:
                        comment_map[comment_id] = comment_data
                        display_order += 1
                        if tier == 1:
                            t1_count += 1
                        logger.info(
                            f"Parsed T{tier} {comment_id} (parent={parent_id}): "
                            f"{comment_data.author} - {comment_data.message[:50]}"
                        )
                    else:
                        logger.warning(f"[SKIP] _parse_comment_from_soup returned None for comment {comment_id}")

                except Exception as e:
                    logger.debug(f"Failed to parse comment: {e}")
                    continue

            # Build tree: attach replies to their parent comments
            root_comments: List[Comment] = []
            for comment in comment_map.values():
                if comment.parent_id and comment.parent_id in comment_map:
                    comment_map[comment.parent_id].children.append(comment)
                else:
                    root_comments.append(comment)

            logger.info(f"Parsed {len(root_comments)} top-level comments, "
                        f"{len(comment_map) - len(root_comments)} replies")
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
            # Check cache first
            element_id = id(current)
            if element_id in self._container_cache:
                cached_result = self._container_cache[element_id]
                return cached_result if cached_result is not False else None
            if current.name == 'div':
                # Check if this container has both author and message
                author_links = current.find_all('a', href=lambda x: x and '/user/' in x)
                message_divs = current.find_all('div', dir='auto')
                
                # Found a container with both author and message
                if author_links and message_divs:
                    text_len = len(current.get_text())
                    # Make sure it's not too large (not the whole page)
                    if text_len < 2000:
                        # CRITICAL: This container must contain EXACTLY ONE comment
                        # Count unique comment_id values (excluding reply_comment_id)
                        nested_links = current.find_all('a', href=lambda x: x and 'comment_id=' in x)
                        unique_comment_ids = set()
                        for link in nested_links:
                            href = link.get('href', '')
                            # Extract the main comment_id (not reply_comment_id)
                            if 'reply_comment_id=' in href:
                                match = re.search(r'reply_comment_id=(\d+)', href)
                            else:
                                match = re.search(r'comment_id=(\d+)', href)
                            if match:
                                unique_comment_ids.add(match.group(1))
                        
                        # Accept only if this container has exactly ONE comment ID
                        if len(unique_comment_ids) == 1:
                            # Cache this successful result
                            self._container_cache[element_id] = current
                            return current
                        
            current = current.parent
            depth += 1
        
        # Cache negative result (not found)
        if element.parent:
            self._container_cache[id(element.parent)] = False
        return None
    
    def _parse_comment_from_soup(
        self,
        container,
        comment_id: str,
        time_link,
        now: datetime,
        display_order: int = 0,
        parent_id: Optional[str] = None,
        tier: int = 1,
    ) -> Optional[Comment]:
        """Parse comment data from BeautifulSoup element."""
        try:
            # Extract author — first /user/ link with meaningful text
            author = None
            for link in container.find_all('a', href=lambda x: x and '/user/' in x):
                text = link.get_text().strip()
                if text and len(text) > 2 and 'ตัวบ่งชี้' not in text and 'สถานะ' not in text:
                    author = text
                    break

            if not author:
                logger.debug(f"Comment {comment_id}: No author found")
                return None

            # Extract message — first dir=auto div whose text is not the author name
            # and not a pure timestamp word
            message = None
            time_words = re.compile(r'^(\d+\s*)?(ชั่วโมง|นาที|วินาที|วัน|สัปดาห์|just now|เมื่อสักครู่)$|^(\d+\s*[smhdw])\b', re.IGNORECASE)
            
            auto_divs = container.find_all('div', dir='auto')
            for div in auto_divs:
                text = div.get_text().strip()
                if text and text != author and not time_words.match(text):
                    message = text
                    break

            if not message:
                logger.debug(f"Comment {comment_id}: No message found")
                return None

            logger.info(f"Comment {comment_id} T{tier}: {author} — {message[:60]}")

            time_text = time_link.get_text().strip()
            logger.debug(f"Comment {comment_id}: time_text = '{time_text}'")
            created_time = self._parse_relative_time(time_text, now) or now
            logger.debug(f"Comment {comment_id}: parsed created_time = {created_time}")

            return Comment(
                id=comment_id,
                parent_id=parent_id,
                tier=tier,
                author=author,
                message=message,
                created_time=created_time,
                last_seen=now,
                display_order=display_order,
                is_new=False,
                children=[],
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
