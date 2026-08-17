"""
Pytest configuration and shared fixtures
"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, MagicMock

# Import models
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.comment import Comment, PostInfo


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_comment():
    """Create a sample comment for testing"""
    now = datetime.now(timezone.utc)
    return Comment(
        id="123456",
        author="Test User",
        message="This is a test comment",
        created_time=now,
        last_seen=now,
        tier=1,
        parent_id=None,
        is_new=True
    )


@pytest.fixture
def sample_comment_tree():
    """Create a sample comment tree with replies"""
    now = datetime.now(timezone.utc)
    root = Comment(
        id="root",
        author="Root User",
        message="Root comment",
        created_time=now,
        last_seen=now,
        tier=1,
        parent_id=None,
        is_new=False
    )
    
    reply1 = Comment(
        id="reply1",
        author="Reply User 1",
        message="First reply",
        created_time=now,
        last_seen=now,
        tier=2,
        parent_id="root",
        is_new=False
    )
    
    reply2 = Comment(
        id="reply2",
        author="Reply User 2",
        message="Second reply",
        created_time=now,
        last_seen=now,
        tier=3,
        parent_id="reply1",
        is_new=True
    )
    
    root.add_child(reply1)
    reply1.add_child(reply2)
    
    return root


@pytest.fixture
def sample_post_info():
    """Create sample post information"""
    return PostInfo(
        url="https://facebook.com/groups/test/posts/123",
        group_name="Test Group",
        post_id="123",
        author="Post Author",
        content="Test post content"
    )


@pytest.fixture
def mock_playwright_page():
    """Create a mock Playwright page object"""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.evaluate = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.press = AsyncMock()
    page.screenshot = AsyncMock()
    page.content = AsyncMock(return_value="<html></html>")
    page.url = "https://facebook.com"
    
    # Mock context for session storage
    context = AsyncMock()
    context.storage_state = AsyncMock(return_value={"cookies": [], "origins": []})
    context.close = AsyncMock()
    page.context = context
    
    return page


@pytest.fixture
def mock_playwright_browser():
    """Create a mock Playwright browser object"""
    browser = AsyncMock()
    context = AsyncMock()
    page = AsyncMock()
    
    context.new_page = AsyncMock(return_value=page)
    context.storage_state = AsyncMock(return_value={"cookies": [], "origins": []})
    context.close = AsyncMock()
    
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()
    
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.context = context
    page.url = "https://facebook.com"
    
    return browser, context, page


@pytest.fixture
def mock_config():
    """Create mock configuration"""
    return {
        "browser": {
            "headless": True,
            "timeout": 30000,
            "slow_mo": 0,
            "user_agent": "Mozilla/5.0"
        },
        "monitor": {
            "refresh_interval": 0.5,
            "max_comments": 1000,
            "enable_notifications": True
        },
        "display": {
            "colors": {
                "tier1": "green",
                "tier2": "cyan",
                "tier3": "yellow",
                "tier4": "red"
            },
            "max_message_length": 200,
            "show_relative_time": True
        },
        "database": {
            "path": "test_comments.db",
            "auto_backup": False
        },
        "logging": {
            "level": "INFO",
            "file": "test_app.log"
        }
    }


@pytest.fixture
def sample_html_comment():
    """Sample HTML for a Facebook comment"""
    return """
    <div class="comment-element" data-comment-id="123">
        <div class="author-name">Test User</div>
        <div class="comment-text">This is a test comment</div>
        <div class="comment-time">5 min</div>
    </div>
    """


@pytest.fixture
def sample_html_nested_comments():
    """Sample HTML for nested Facebook comments"""
    return """
    <div class="comment-element" data-comment-id="root">
        <div class="author-name">Root User</div>
        <div class="comment-text">Root comment</div>
        <div class="comment-time">1 hr</div>
        <div class="replies">
            <div class="comment-element" data-comment-id="reply1">
                <div class="author-name">Reply User</div>
                <div class="comment-text">Reply to root</div>
                <div class="comment-time">30 min</div>
            </div>
        </div>
    </div>
    """
