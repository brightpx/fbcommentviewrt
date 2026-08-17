"""Comment data models."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class Comment:
    """Represents a Facebook comment or reply."""
    
    id: str
    parent_id: Optional[str]
    tier: int
    author: str
    message: str
    created_time: datetime
    last_seen: datetime
    display_order: int = 0  # Order on Facebook page (0 = most recent)
    is_new: bool = False
    is_deleted: bool = False
    children: List['Comment'] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert comment to dictionary."""
        return {
            'id': self.id,
            'parent_id': self.parent_id,
            'tier': self.tier,
            'author': self.author,
            'message': self.message,
            'created_time': self.created_time.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'display_order': self.display_order,
            'is_new': self.is_new,
            'is_deleted': self.is_deleted,
            'children': [child.to_dict() for child in self.children]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Comment':
        """Create comment from dictionary."""
        children_data = data.pop('children', [])
        comment = cls(
            id=data['id'],
            parent_id=data.get('parent_id'),
            tier=data['tier'],
            author=data['author'],
            message=data['message'],
            created_time=datetime.fromisoformat(data['created_time']),
            last_seen=datetime.fromisoformat(data['last_seen']),
            display_order=data.get('display_order', 0),
            is_new=data.get('is_new', False),
            is_deleted=data.get('is_deleted', False),
            children=[]
        )
        comment.children = [cls.from_dict(child) for child in children_data]
        return comment
    
    def add_child(self, child: 'Comment') -> None:
        """Add a child comment."""
        if child not in self.children:
            self.children.append(child)
    
    def find_comment(self, comment_id: str) -> Optional['Comment']:
        """Recursively find a comment by ID."""
        if self.id == comment_id:
            return self
        for child in self.children:
            found = child.find_comment(comment_id)
            if found:
                return found
        return None
    
    def get_all_descendants(self) -> List['Comment']:
        """Get all descendant comments."""
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_all_descendants())
        return descendants
    
    def count_total(self) -> int:
        """Count total comments including children."""
        return 1 + sum(child.count_total() for child in self.children)


@dataclass
class PostInfo:
    """Information about the monitored post."""
    
    url: str
    group_name: str = ""
    post_id: str = ""
    author: str = ""
    content: str = ""
    total_comments: int = 0
    total_replies: int = 0
    last_refresh: Optional[datetime] = None
    
    def update_counts(self, comments: List[Comment]) -> None:
        """Update comment and reply counts."""
        self.total_comments = len(comments)
        self.total_replies = sum(
            len(comment.get_all_descendants()) 
            for comment in comments
        )
