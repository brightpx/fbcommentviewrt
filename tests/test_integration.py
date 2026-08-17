"""
Integration tests for the full monitoring workflow
"""
import pytest
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.comment import Comment, PostInfo
from app.monitor.cache import CommentCache
from app.database.db import CommentDatabase


class TestIntegration:
    """Integration tests for complete workflows"""
    
    @pytest.mark.asyncio
    async def test_cache_and_database_integration(self, temp_dir, sample_comment):
        """Test cache and database working together"""
        # Setup
        db_path = temp_dir / "test.db"
        db = CommentDatabase(str(db_path))
        await db.initialize()
        
        cache = CommentCache()
        
        # First update - should detect as new
        comments = [sample_comment]
        new_comments, _ = cache.update(comments)
        
        assert len(new_comments) == 1
        
        # Save to database
        post_url = "https://facebook.com/groups/test/posts/123"
        await db.save_comments_batch(new_comments, post_url)
        
        # Retrieve from database
        saved = await db.get_comments(post_url)
        assert len(saved) == 1
        assert saved[0].id == sample_comment.id
        
        # Second update - should not detect as new
        new_comments, _ = cache.update(comments)
        assert len(new_comments) == 0
        
        await db.close()
    
    @pytest.mark.asyncio
    async def test_comment_tree_persistence(self, temp_dir, sample_comment_tree):
        """Test saving and restoring comment tree structure"""
        db_path = temp_dir / "test.db"
        db = CommentDatabase(str(db_path))
        await db.initialize()
        
        # Flatten and save tree
        all_comments = [sample_comment_tree]
        all_comments.extend(sample_comment_tree.get_all_descendants())
        
        post_url = "https://facebook.com/groups/test/posts/123"
        await db.save_comments_batch(all_comments, post_url)
        
        # Retrieve
        saved = await db.get_comments(post_url)
        
        # Should have all comments
        assert len(saved) >= 3
        
        # Verify hierarchy is preserved
        root_comments = [c for c in saved if c.parent_id is None]
        assert len(root_comments) >= 1
        
        replies = [c for c in saved if c.parent_id is not None]
        assert len(replies) >= 2
        
        await db.close()
    
    @pytest.mark.asyncio
    async def test_multiple_posts(self, temp_dir):
        """Test handling multiple posts"""
        db_path = temp_dir / "test.db"
        db = CommentDatabase(str(db_path))
        await db.initialize()
        
        now = datetime.now(timezone.utc)
        # Create comments for different posts
        post1_comment = Comment(
            id="post1_c1",
            author="User1",
            message="Comment on post 1",
            created_time=now,
            last_seen=now,
            tier=1,
            parent_id=None,
            is_new=False
        )
        
        post2_comment = Comment(
            id="post2_c1",
            author="User2",
            message="Comment on post 2",
            created_time=now,
            last_seen=now,
            tier=1,
            parent_id=None,
            is_new=False
        )
        
        await db.save_comment(post1_comment, "https://facebook.com/post1")
        await db.save_comment(post2_comment, "https://facebook.com/post2")
        
        # Retrieve separately
        post1_comments = await db.get_comments("https://facebook.com/post1")
        post2_comments = await db.get_comments("https://facebook.com/post2")
        
        assert len(post1_comments) == 1
        assert len(post2_comments) == 1
        assert post1_comments[0].id == "post1_c1"
        assert post2_comments[0].id == "post2_c1"
        
        await db.close()
    
    @pytest.mark.asyncio
    async def test_cache_statistics(self, sample_comment_tree):
        """Test cache statistics with complex tree"""
        cache = CommentCache()
        
        # Create multiple trees
        trees = [sample_comment_tree]
        
        # Add more comments
        now = datetime.now(timezone.utc)
        for i in range(5):
            comment = Comment(
                id=f"extra_{i}",
                author=f"User {i}",
                message=f"Message {i}",
                created_time=now,
                last_seen=now,
                tier=1,
                parent_id=None,
                is_new=False
            )
            trees.append(comment)
        
        cache.update(trees)
        stats = cache.get_statistics()
        
        assert stats["total_comments"] >= 6
        assert "tier_1" in stats
