"""Comment change detection and caching."""
import logging
from typing import Dict, Set, List, Tuple
from datetime import datetime
from ..models.comment import Comment


logger = logging.getLogger(__name__)


class CommentCache:
    """Cache for tracking comment changes."""
    
    def __init__(self):
        self.comment_ids: Set[str] = set()
        self.comment_map: Dict[str, Comment] = {}
        self.last_update = datetime.now()
    
    def update(self, comments: List[Comment]) -> Tuple[List[Comment], List[Comment]]:
        """
        Update cache with new comments.
        Returns: (new_comments, updated_comments)
        """
        new_comments = []
        updated_comments = []
        
        # Flatten comment tree
        all_comments = self._flatten_comments(comments)
        
        # Track current IDs
        current_ids = {comment.id for comment in all_comments}
        
        # Find new comments
        for comment in all_comments:
            if comment.id not in self.comment_ids:
                new_comments.append(comment)
                comment.is_new = True
            else:
                # Check if comment was updated
                old_comment = self.comment_map.get(comment.id)
                if old_comment and self._is_different(old_comment, comment):
                    updated_comments.append(comment)
        
        # Update cache
        self.comment_ids = current_ids
        self.comment_map = {comment.id: comment for comment in all_comments}
        self.last_update = datetime.now()
        
        return new_comments, updated_comments
    
    def _flatten_comments(self, comments: List[Comment]) -> List[Comment]:
        """Flatten nested comment tree into a list."""
        result = []
        for comment in comments:
            result.append(comment)
            if comment.children:
                result.extend(self._flatten_comments(comment.children))
        return result
    
    def _is_different(self, old: Comment, new: Comment) -> bool:
        """Check if two comments are different."""
        return (
            old.message != new.message or
            old.author != new.author or
            len(old.children) != len(new.children)
        )
    
    def get_statistics(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'total_comments': len(self.comment_ids),
            'tier_1': sum(1 for c in self.comment_map.values() if c.tier == 1),
            'tier_2': sum(1 for c in self.comment_map.values() if c.tier == 2),
            'tier_3': sum(1 for c in self.comment_map.values() if c.tier == 3),
            'tier_4plus': sum(1 for c in self.comment_map.values() if c.tier >= 4),
        }
    
    def clear(self) -> None:
        """Clear the cache."""
        self.comment_ids.clear()
        self.comment_map.clear()
        self.last_update = datetime.now()
