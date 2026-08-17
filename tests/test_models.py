"""
Test cases for data models (Comment, PostInfo)
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.models.comment import Comment, PostInfo


class TestComment:
    """Test Comment model"""
    
    def test_comment_creation(self):
        """Test basic comment creation"""
        now = datetime.now(timezone.utc)
        comment = Comment(
            id="123",
            author="Test User",
            message="Test message",
            created_time=now,
            last_seen=now,
            tier=1,
            parent_id=None,
            is_new=True
        )
        
        assert comment.id == "123"
        assert comment.author == "Test User"
        assert comment.message == "Test message"
        assert comment.tier == 1
        assert comment.parent_id is None
        assert comment.is_new is True
        assert len(comment.children) == 0
    
    def test_add_child(self, sample_comment):
        """Test adding child comments"""
        parent = sample_comment
        
        now = datetime.now(timezone.utc)
        child = Comment(
            id="child1",
            author="Child User",
            message="Reply",
            created_time=now,
            last_seen=now,
            tier=2,
            parent_id=parent.id,
            is_new=False
        )
        
        parent.add_child(child)
        
        assert len(parent.children) == 1
        assert parent.children[0].id == "child1"
        assert parent.children[0].tier == 2
    
    def test_find_comment(self, sample_comment_tree):
        """Test finding a comment in the tree"""
        root = sample_comment_tree
        
        # Find root
        found = root.find_comment("root")
        assert found is not None
        assert found.id == "root"
        
        # Find reply
        found = root.find_comment("reply1")
        assert found is not None
        assert found.id == "reply1"
        assert found.tier == 2
        
        # Find nested reply
        found = root.find_comment("reply2")
        assert found is not None
        assert found.id == "reply2"
        assert found.tier == 3
        
        # Not found
        found = root.find_comment("nonexistent")
        assert found is None
    
    def test_get_all_descendants(self, sample_comment_tree):
        """Test getting all descendants"""
        root = sample_comment_tree
        descendants = root.get_all_descendants()
        
        assert len(descendants) == 2  # reply1 and reply2
        assert any(c.id == "reply1" for c in descendants)
        assert any(c.id == "reply2" for c in descendants)
    
    def test_comment_hierarchy(self):
        """Test comment tier hierarchy"""
        now = datetime.now(timezone.utc)
        root = Comment(
            id="root",
            author="Root",
            message="Root",
            created_time=now,
            last_seen=now,
            tier=1,
            parent_id=None,
            is_new=False
        )
        
        tier2 = Comment(
            id="tier2",
            author="Tier2",
            message="Tier2",
            created_time=now,
            last_seen=now,
            tier=2,
            parent_id="root",
            is_new=False
        )
        
        tier3 = Comment(
            id="tier3",
            author="Tier3",
            message="Tier3",
            created_time=now,
            last_seen=now,
            tier=3,
            parent_id="tier2",
            is_new=False
        )
        
        root.add_child(tier2)
        tier2.add_child(tier3)
        
        assert root.tier == 1
        assert tier2.tier == 2
        assert tier3.tier == 3
        assert len(root.get_all_descendants()) == 2


class TestPostInfo:
    """Test PostInfo model"""
    
    def test_post_info_creation(self):
        """Test basic PostInfo creation"""
        post = PostInfo(
            url="https://facebook.com/groups/123/posts/456",
            group_name="Test Group",
            post_id="456",
            author="Author",
            content="Post content"
        )
        
        assert post.url == "https://facebook.com/groups/123/posts/456"
        assert post.group_name == "Test Group"
        assert post.post_id == "456"
        assert post.author == "Author"
        assert post.content == "Post content"
    
    def test_post_info_optional_fields(self):
        """Test PostInfo with optional fields"""
        post = PostInfo(
            url="https://facebook.com/test",
            group_name="Group"
        )
        
        assert post.url == "https://facebook.com/test"
        assert post.group_name == "Group"
        assert post.post_id == ""
        assert post.author == ""
        assert post.content == ""
