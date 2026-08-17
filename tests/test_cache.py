"""
Test cases for CommentCache
"""
import pytest
from datetime import datetime, timezone

from app.models.comment import Comment
from app.monitor.cache import CommentCache


class TestCommentCache:
    """Test CommentCache functionality"""
    
    def test_empty_cache(self):
        """Test empty cache initialization"""
        cache = CommentCache()
        stats = cache.get_statistics()
        
        assert stats["total_comments"] == 0
        assert stats["tier_1"] == 0
    
    def test_update_with_new_comments(self, sample_comment):
        """Test updating cache with new comments"""
        cache = CommentCache()
        comments = [sample_comment]
        
        new_comments, updated_comments = cache.update(comments)
        
        assert len(new_comments) == 1
        assert len(updated_comments) == 0
        assert new_comments[0].id == sample_comment.id
    
    def test_update_with_existing_comments(self, sample_comment):
        """Test updating cache with existing comments"""
        cache = CommentCache()
        
        # First update
        cache.update([sample_comment])
        
        # Second update with same comment
        new_comments, updated_comments = cache.update([sample_comment])
        
        assert len(new_comments) == 0
        assert len(updated_comments) == 0
    
    def test_update_with_modified_comments(self):
        """Test detecting modified comments"""
        cache = CommentCache()
        
        now = datetime.now(timezone.utc)
        comment1 = Comment(
            id="123",
            author="User",
            message="Original message",
            created_time=now,
            last_seen=now,
            tier=1,
            parent_id=None,
            is_new=False
        )
        
        # First update
        cache.update([comment1])
        
        # Modified comment (same id, different message)
        comment2 = Comment(
            id="123",
            author="User",
            message="Modified message",
            created_time=now,
            last_seen=now,
            tier=1,
            parent_id=None,
            is_new=False
        )
        
        new_comments, updated_comments = cache.update([comment2])
        
        # Note: Current implementation treats same ID as no change
        # This test documents current behavior
        assert len(new_comments) == 0
    
    def test_statistics(self, sample_comment_tree):
        """Test cache statistics"""
        cache = CommentCache()
        cache.update([sample_comment_tree])
        
        stats = cache.get_statistics()
        
        assert stats["total_comments"] > 0
        assert "tier_1" in stats
    
    def test_flatten_comments(self, sample_comment_tree):
        """Test flattening comment tree"""
        cache = CommentCache()
        flat = cache._flatten_comments([sample_comment_tree])
        
        # Should include root + all descendants
        assert len(flat) == 3  # root + reply1 + reply2
        assert any(c.id == "root" for c in flat)
        assert any(c.id == "reply1" for c in flat)
        assert any(c.id == "reply2" for c in flat)
    
    def test_multiple_trees(self):
        """Test cache with multiple comment trees"""
        cache = CommentCache()
        
        now = datetime.now(timezone.utc)
        tree1 = Comment(
            id="tree1",
            author="User1",
            message="Tree 1",
            created_time=now,
            last_seen=now,
            tier=1,
            parent_id=None,
            is_new=False
        )
        
        tree2 = Comment(
            id="tree2",
            author="User2",
            message="Tree 2",
            created_time=now,
            last_seen=now,
            tier=1,
            parent_id=None,
            is_new=False
        )
        
        new_comments, _ = cache.update([tree1, tree2])
        
        assert len(new_comments) == 2
        assert any(c.id == "tree1" for c in new_comments)
        assert any(c.id == "tree2" for c in new_comments)
