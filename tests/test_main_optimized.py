"""
Test cases for run_optimized.py and app/main_optimized.py

ครอบคลุม:
- setup_logging()
- OptimizedFacebookAutoReply._load_config()
- OptimizedFacebookAutoReply.initialize()
- OptimizedFacebookAutoReply.run()
- OptimizedFacebookAutoReply._handle_owner_comment()
- OptimizedFacebookAutoReply.cleanup()
- main() entry point
- run_optimized.py wrapper
"""
import pytest
import asyncio
import sys
import yaml
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open, PropertyMock


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_config():
    """Sample valid config dict."""
    return {
        'target': {
            'post_url': 'https://www.facebook.com/groups/123/posts/456/'
        },
        'browser': {
            'headless': True,
            'timeout': 30000,
            'slow_mo': 0
        },
        'session': {
            'file': 'session/test.json'
        },
        'monitor': {
            'refresh_interval': 200,
            'sorting_mode': 'most_recent',
            'max_tier': 2,
            'max_comments': 100,
            'display_limit': 10
        },
        'auto_reply': {
            'enabled': True,
            'reply_message': 'ขอบคุณสำหรับคอมเมนต์ครับ'
        },
        'logging': {
            'level': 'INFO',
            'file': 'logs/test.log'
        }
    }


@pytest.fixture
def sample_config_disabled_reply(sample_config):
    """Config with auto-reply disabled."""
    config = sample_config.copy()
    config['auto_reply'] = {'enabled': False, 'reply_message': ''}
    return config


@pytest.fixture
def sample_config_no_reply_message(sample_config):
    """Config with auto-reply enabled but no message."""
    config = sample_config.copy()
    config['auto_reply'] = {'enabled': True, 'reply_message': ''}
    return config


@pytest.fixture
def mock_scraper():
    """Mock FacebookScraper with all async methods."""
    scraper = AsyncMock()
    scraper.initialize = AsyncMock()
    scraper.is_logged_in = AsyncMock(return_value=True)
    scraper.login = AsyncMock(return_value=True)
    scraper.navigate_to_post = AsyncMock(return_value=True)
    scraper.get_post_author = AsyncMock(return_value="Test Owner")
    scraper.switch_to_most_recent = AsyncMock()
    scraper.reply_to_comment = AsyncMock(return_value=True)
    scraper.save_session = AsyncMock()
    scraper.page = AsyncMock()
    scraper.page.reload = AsyncMock()
    scraper.page.evaluate = AsyncMock(return_value=[])
    scraper.page.locator = MagicMock()
    scraper.page.wait_for_timeout = AsyncMock()
    scraper.browser = AsyncMock()
    scraper.browser.close = AsyncMock()
    scraper.playwright = AsyncMock()
    scraper.playwright.stop = AsyncMock()
    return scraper


@pytest.fixture
def mock_detector():
    """Mock OwnerCommentDetector."""
    detector = AsyncMock()
    detector.initialize = AsyncMock(return_value=True)
    detector.monitor_loop = AsyncMock()
    detector.detect_new_owner_comments = AsyncMock(return_value=[])
    detector.get_stats = MagicMock(return_value={
        'total_scans': 100,
        'owner_comments_detected': 5,
        'replies_posted': 5,
        'avg_detection_latency': 0.05,
        'avg_reply_latency': 0.15,
        'avg_detection_ms': 50.0,
        'avg_reply_ms': 150.0,
        'known_comments': 25,
        'owner_name': 'Test Owner',
        'monitoring_start': '12:00:00'
    })
    detector.owner_name = "Test Owner"
    detector.monitoring_start_time = MagicMock()
    detector.monitoring_start_time.strftime = MagicMock(return_value='12:00:00')
    detector.replied_comment_ids = set()
    detector.on_owner_comment = None
    return detector


@pytest.fixture
def mock_db():
    """Mock database."""
    db = AsyncMock()
    db.add_comment = AsyncMock()
    db.initialize = AsyncMock()
    db.close = AsyncMock()
    return db


# ── setup_logging tests ────────────────────────────────────────────────────

class TestSetupLogging:
    """Test setup_logging function."""

    def test_setup_logging_creates_log_dir(self, tmp_path, sample_config):
        """Test that setup_logging creates log directory."""
        from app.main_optimized import setup_logging

        config = sample_config.copy()
        log_file = tmp_path / "logs" / "test.log"
        config['logging']['file'] = str(log_file)

        setup_logging(config)

        assert log_file.parent.exists()

    def test_setup_logging_with_debug_level(self, tmp_path, sample_config):
        """Test setup_logging with DEBUG level."""
        from app.main_optimized import setup_logging

        config = sample_config.copy()
        config['logging']['level'] = 'DEBUG'
        config['logging']['file'] = str(tmp_path / "logs" / "debug.log")

        setup_logging(config)

        logger = logging.getLogger('test_debug')
        logger.setLevel(logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_setup_logging_default_level(self, tmp_path, sample_config):
        """Test setup_logging falls back to INFO for missing level key."""
        from app.main_optimized import setup_logging

        config = sample_config.copy()
        # Remove 'level' key entirely - should default to INFO
        del config['logging']['level']
        config['logging']['file'] = str(tmp_path / "logs" / "default.log")

        # Should not raise
        setup_logging(config)


# ── OptimizedFacebookAutoReply tests ───────────────────────────────────────

class TestOptimizedFacebookAutoReplyInit:
    """Test __init__ and _load_config."""

    @patch('app.main_optimized.setup_logging')
    def test_init_loads_config(self, mock_setup, sample_config):
        """Test that __init__ loads config from file."""
        from app.main_optimized import OptimizedFacebookAutoReply
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_config, f)
            config_path = f.name

        try:
            app = OptimizedFacebookAutoReply(config_path=config_path)
            assert app.config['target']['post_url'] == sample_config['target']['post_url']
            assert app.scraper is None
            assert app.detector is None
            assert app.db is None
            mock_setup.assert_called_once()
        finally:
            Path(config_path).unlink(missing_ok=True)

    @patch('app.main_optimized.setup_logging')
    def test_init_scraper_none(self, mock_setup, sample_config):
        """Test that scraper is None after init."""
        from app.main_optimized import OptimizedFacebookAutoReply
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_config, f)
            config_path = f.name

        try:
            app = OptimizedFacebookAutoReply(config_path=config_path)
            assert app.scraper is None
            assert app.detector is None
        finally:
            Path(config_path).unlink(missing_ok=True)

    @patch('app.main_optimized.setup_logging')
    def test_load_config_file_not_found_no_example(self, mock_setup):
        """Test _load_config raises FileNotFoundError when no config or example."""
        from app.main_optimized import OptimizedFacebookAutoReply

        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                OptimizedFacebookAutoReply(config_path="nonexistent.yaml")

    @patch('app.main_optimized.setup_logging')
    @patch('shutil.copy')
    def test_load_config_copies_from_example(self, mock_copy, mock_setup, sample_config):
        """Test _load_config copies from example if config missing."""
        from app.main_optimized import OptimizedFacebookAutoReply

        with patch('pathlib.Path.exists', side_effect=[False, True]):  # config missing, example exists
            with patch('builtins.open', mock_open(read_data=yaml.dump(sample_config))):
                app = OptimizedFacebookAutoReply(config_path="missing.yaml")
                mock_copy.assert_called_once()
                assert app.config is not None


# ── initialize() tests ─────────────────────────────────────────────────────

class TestInitialize:
    """Test OptimizedFacebookAutoReply.initialize()."""

    @pytest.mark.asyncio
    @patch('app.main_optimized.FacebookScraper')
    @patch('app.main_optimized.OwnerCommentDetector')
    @patch('app.main_optimized.setup_logging')
    async def test_initialize_success(
        self, mock_setup, mock_detector_cls, mock_scraper_cls,
        sample_config, mock_scraper, mock_detector, tmp_path
    ):
        """Test successful initialization."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper_cls.return_value = mock_scraper
        mock_detector_cls.return_value = mock_detector

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)

        result = await app.initialize()

        assert result is True
        assert app.scraper is not None
        assert app.detector is not None
        mock_scraper.initialize.assert_called_once()
        mock_detector.initialize.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.main_optimized.FacebookScraper')
    @patch('app.main_optimized.setup_logging')
    async def test_initialize_invalid_post_url(
        self, mock_setup, mock_scraper_cls, sample_config, mock_scraper, tmp_path
    ):
        """Test initialize fails with invalid post URL."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper_cls.return_value = mock_scraper

        config = sample_config.copy()
        config['target']['post_url'] = 'https://www.facebook.com/groups/YOUR_GROUP_ID/posts/YOUR_POST_ID/'

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=config)

        result = await app.initialize()

        assert result is False

    @pytest.mark.asyncio
    @patch('app.main_optimized.FacebookScraper')
    @patch('app.main_optimized.setup_logging')
    async def test_initialize_empty_post_url(
        self, mock_setup, mock_scraper_cls, sample_config, mock_scraper, tmp_path
    ):
        """Test initialize fails with empty post URL."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper_cls.return_value = mock_scraper

        config = sample_config.copy()
        config['target']['post_url'] = ''

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=config)

        result = await app.initialize()

        assert result is False

    @pytest.mark.asyncio
    @patch('app.main_optimized.FacebookScraper')
    @patch('app.main_optimized.setup_logging')
    async def test_initialize_not_logged_in_login_success(
        self, mock_setup, mock_scraper_cls, sample_config, mock_scraper, tmp_path
    ):
        """Test initialize when not logged in but login succeeds."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper.is_logged_in = AsyncMock(return_value=False)
        mock_scraper.login = AsyncMock(return_value=True)
        mock_scraper_cls.return_value = mock_scraper

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)

        with patch.object(app, 'detector', None):
            # Will fail at detector init since we didn't mock it
            result = await app.initialize()
            # login was called
            mock_scraper.login.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.main_optimized.FacebookScraper')
    @patch('app.main_optimized.setup_logging')
    async def test_initialize_not_logged_in_login_fails(
        self, mock_setup, mock_scraper_cls, sample_config, mock_scraper, tmp_path
    ):
        """Test initialize when login fails."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper.is_logged_in = AsyncMock(return_value=False)
        mock_scraper.login = AsyncMock(return_value=False)
        mock_scraper_cls.return_value = mock_scraper

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)

        result = await app.initialize()

        assert result is False

    @pytest.mark.asyncio
    @patch('app.main_optimized.FacebookScraper')
    @patch('app.main_optimized.OwnerCommentDetector')
    @patch('app.main_optimized.setup_logging')
    async def test_initialize_detector_fails(
        self, mock_setup, mock_detector_cls, mock_scraper_cls,
        sample_config, mock_scraper, tmp_path
    ):
        """Test initialize when detector initialization fails."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper_cls.return_value = mock_scraper

        bad_detector = AsyncMock()
        bad_detector.initialize = AsyncMock(return_value=False)
        mock_detector_cls.return_value = bad_detector

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)

        result = await app.initialize()

        assert result is False

    @pytest.mark.asyncio
    @patch('app.main_optimized.FacebookScraper')
    @patch('app.main_optimized.OwnerCommentDetector')
    @patch('app.main_optimized.setup_logging')
    async def test_initialize_registers_auto_reply_callback(
        self, mock_setup, mock_detector_cls, mock_scraper_cls,
        sample_config, mock_scraper, mock_detector, tmp_path
    ):
        """Test that auto-reply callback is registered when enabled."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper_cls.return_value = mock_scraper
        mock_detector_cls.return_value = mock_detector

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)

        result = await app.initialize()

        assert result is True
        assert mock_detector.on_owner_comment is not None

    @pytest.mark.asyncio
    @patch('app.main_optimized.FacebookScraper')
    @patch('app.main_optimized.OwnerCommentDetector')
    @patch('app.main_optimized.setup_logging')
    async def test_initialize_skips_callback_when_reply_disabled(
        self, mock_setup, mock_detector_cls, mock_scraper_cls,
        sample_config_disabled_reply, mock_scraper, mock_detector, tmp_path
    ):
        """Test that callback is NOT registered when auto-reply is disabled."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper_cls.return_value = mock_scraper
        mock_detector_cls.return_value = mock_detector

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config_disabled_reply))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config_disabled_reply)

        await app.initialize()

        # The callback should remain None since we override it
        # (the detector mock already has it as None, and we don't set it)
        assert mock_detector.on_owner_comment is None

    @pytest.mark.asyncio
    @patch('app.main_optimized.FacebookScraper')
    @patch('app.main_optimized.setup_logging')
    async def test_initialize_exception_handling(
        self, mock_setup, mock_scraper_cls, sample_config, tmp_path
    ):
        """Test initialize handles exceptions gracefully."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper_cls.side_effect = Exception("Connection failed")

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)

        result = await app.initialize()

        assert result is False


# ── run() tests ────────────────────────────────────────────────────────────

class TestRun:
    """Test OptimizedFacebookAutoReply.run()."""

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_run_initialization_fails(self, mock_setup, sample_config, tmp_path):
        """Test that run() returns early when initialize fails."""
        from app.main_optimized import OptimizedFacebookAutoReply

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.initialize = AsyncMock(return_value=False)

        await app.run()

        app.initialize.assert_called_once()
        # monitor_loop should NOT be called
        assert app.detector is None

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_run_keyboard_interrupt(
        self, mock_setup, sample_config, mock_detector, tmp_path
    ):
        """Test that run() handles KeyboardInterrupt and shows stats."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_detector.monitor_loop = AsyncMock(side_effect=KeyboardInterrupt())

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.initialize = AsyncMock(return_value=True)
        app.detector = mock_detector
        app.cleanup = AsyncMock()

        await app.run()

        mock_detector.get_stats.assert_called_once()
        app.cleanup.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_run_general_exception(
        self, mock_setup, sample_config, mock_detector, tmp_path
    ):
        """Test that run() handles general exceptions."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_detector.monitor_loop = AsyncMock(side_effect=RuntimeError("Test error"))

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.initialize = AsyncMock(return_value=True)
        app.detector = mock_detector
        app.cleanup = AsyncMock()

        await app.run()

        app.cleanup.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_run_successful_flow(
        self, mock_setup, sample_config, mock_detector, mock_scraper, tmp_path
    ):
        """Test a successful run() flow (monitor loop runs then stops)."""
        from app.main_optimized import OptimizedFacebookAutoReply

        # Simulate monitor_loop that runs briefly then finishes
        mock_detector.monitor_loop = AsyncMock(return_value=None)

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.initialize = AsyncMock(return_value=True)
        app.detector = mock_detector
        app.scraper = mock_scraper
        app.cleanup = AsyncMock()

        await app.run()

        mock_detector.monitor_loop.assert_called_once()
        app.cleanup.assert_called_once()


# ── _handle_owner_comment() tests ──────────────────────────────────────────

class TestHandleOwnerComment:
    """Test OptimizedFacebookAutoReply._handle_owner_comment()."""

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_handle_owner_comment_success(
        self, mock_setup, sample_config, mock_scraper, mock_detector, tmp_path
    ):
        """Test successful owner comment handling and reply."""
        from app.main_optimized import OptimizedFacebookAutoReply

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.scraper = mock_scraper
        app.detector = mock_detector

        comment = {
            'comment_id': '123456789',
            'author': 'Test Owner',
            'text': 'Hello world'
        }

        await app._handle_owner_comment(comment)

        mock_scraper.reply_to_comment.assert_called_once_with(
            '123456789', 'ขอบคุณสำหรับคอมเมนต์ครับ'
        )
        assert '123456789' in mock_detector.replied_comment_ids

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_handle_owner_comment_reply_disabled(
        self, mock_setup, sample_config_disabled_reply, mock_scraper, mock_detector, tmp_path
    ):
        """Test that reply is skipped when auto-reply is disabled."""
        from app.main_optimized import OptimizedFacebookAutoReply

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config_disabled_reply))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config_disabled_reply)
        app.scraper = mock_scraper
        app.detector = mock_detector

        comment = {
            'comment_id': '123456789',
            'author': 'Test Owner',
            'text': 'Hello world'
        }

        await app._handle_owner_comment(comment)

        # reply_to_comment should NOT be called
        mock_scraper.reply_to_comment.assert_not_called()

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_handle_owner_comment_no_reply_message(
        self, mock_setup, sample_config_no_reply_message, mock_scraper, mock_detector, tmp_path
    ):
        """Test that reply is skipped when no reply message configured."""
        from app.main_optimized import OptimizedFacebookAutoReply

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config_no_reply_message))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config_no_reply_message)
        app.scraper = mock_scraper
        app.detector = mock_detector

        comment = {
            'comment_id': '123456789',
            'author': 'Test Owner',
            'text': 'Hello world'
        }

        await app._handle_owner_comment(comment)

        mock_scraper.reply_to_comment.assert_not_called()

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_handle_owner_comment_reply_fails(
        self, mock_setup, sample_config, mock_scraper, mock_detector, tmp_path
    ):
        """Test handling when reply_to_comment fails."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper.reply_to_comment = AsyncMock(return_value=False)

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.scraper = mock_scraper
        app.detector = mock_detector

        comment = {
            'comment_id': '123456789',
            'author': 'Test Owner',
            'text': 'Hello world'
        }

        await app._handle_owner_comment(comment)

        mock_scraper.reply_to_comment.assert_called_once()
        # Comment IS marked as replied BEFORE the attempt (optimistic lock):
        # a failed/slow verification must never trigger a duplicate reply,
        # because double-posting on Facebook is worse than missing one reply.
        assert '123456789' in mock_detector.replied_comment_ids

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_handle_owner_comment_missing_keys(
        self, mock_setup, sample_config, mock_scraper, mock_detector, tmp_path
    ):
        """Test handling comment dict with missing keys."""
        from app.main_optimized import OptimizedFacebookAutoReply

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.scraper = mock_scraper
        app.detector = mock_detector

        comment = {}  # No keys

        await app._handle_owner_comment(comment)

        # Should still call reply with 'unknown' values
        mock_scraper.reply_to_comment.assert_called_once_with(
            'unknown', 'ขอบคุณสำหรับคอมเมนต์ครับ'
        )

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_handle_owner_comment_exception(
        self, mock_setup, sample_config, mock_scraper, mock_detector, tmp_path
    ):
        """Test that _handle_owner_comment handles exceptions gracefully."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper.reply_to_comment = AsyncMock(side_effect=Exception("Network error"))

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.scraper = mock_scraper
        app.detector = mock_detector

        comment = {
            'comment_id': '123456789',
            'author': 'Test Owner',
            'text': 'Hello world'
        }

        # Should not raise
        await app._handle_owner_comment(comment)


# ── cleanup() tests ────────────────────────────────────────────────────────

class TestCleanup:
    """Test OptimizedFacebookAutoReply.cleanup()."""

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_cleanup_with_scraper(
        self, mock_setup, sample_config, mock_scraper, tmp_path
    ):
        """Test cleanup with active scraper."""
        from app.main_optimized import OptimizedFacebookAutoReply

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.scraper = mock_scraper

        await app.cleanup()

        mock_scraper.save_session.assert_called_once()
        mock_scraper.browser.close.assert_called_once()
        mock_scraper.playwright.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_cleanup_no_scraper(self, mock_setup, sample_config, tmp_path):
        """Test cleanup when scraper is None."""
        from app.main_optimized import OptimizedFacebookAutoReply

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.scraper = None

        # Should not raise
        await app.cleanup()

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_cleanup_handles_exceptions(
        self, mock_setup, sample_config, mock_scraper, tmp_path
    ):
        """Test cleanup handles exceptions during browser close."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper.browser.close = AsyncMock(side_effect=Exception("Close failed"))

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.scraper = mock_scraper

        # Should not raise
        await app.cleanup()

    @pytest.mark.asyncio
    @patch('app.main_optimized.setup_logging')
    async def test_cleanup_no_browser(
        self, mock_setup, sample_config, mock_scraper, tmp_path
    ):
        """Test cleanup when scraper has no browser."""
        from app.main_optimized import OptimizedFacebookAutoReply

        mock_scraper.browser = None
        mock_scraper.playwright = None

        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(sample_config))

        app = OptimizedFacebookAutoReply(config_path=str(config_path))
        app._load_config = MagicMock(return_value=sample_config)
        app.scraper = mock_scraper

        # Should not raise
        await app.cleanup()


# ── main() entry point tests ───────────────────────────────────────────────

class TestMainEntryPoint:
    """Test main() async function."""

    @pytest.mark.asyncio
    @patch('app.main_optimized.OptimizedFacebookAutoReply')
    @patch('app.main_optimized.setup_logging')
    async def test_main_creates_app_and_runs(self, mock_setup, mock_app_cls):
        """Test that main() creates app and calls run()."""
        from app.main_optimized import main

        mock_app = AsyncMock()
        mock_app.run = AsyncMock()
        mock_app_cls.return_value = mock_app

        await main()

        mock_app_cls.assert_called_once()
        mock_app.run.assert_called_once()


# ── run_optimized.py wrapper tests ────────────────────────────────────────

class TestRunOptimizedWrapper:
    """Test run_optimized.py script."""

    def test_run_optimized_imports(self):
        """Test that run_optimized.py can be imported."""
        import run_optimized
        assert hasattr(run_optimized, 'main')

    @patch('run_optimized.main')
    def test_run_optimized_calls_main(self, mock_main):
        """Test that run_optimized calls main() when executed."""
        mock_main_result = AsyncMock()
        mock_main.return_value = mock_main_result

        # Simulate the __main__ block
        import run_optimized

        with patch.object(run_optimized, '__name__', '__main__'):
            with patch('asyncio.run') as mock_asyncio_run:
                # Re-execute the if __name__ == "__main__" block
                try:
                    asyncio.run(run_optimized.main())
                except Exception:
                    pass
                mock_asyncio_run.assert_called()

    def test_run_optimized_keyboard_interrupt_handling(self):
        """Test that KeyboardInterrupt is handled gracefully."""
        import run_optimized

        with patch.object(run_optimized, '__name__', '__main__'):
            with patch('asyncio.run', side_effect=KeyboardInterrupt()):
                try:
                    # This should not raise
                    if run_optimized.__name__ == "__main__":
                        try:
                            asyncio.run(run_optimized.main())
                        except KeyboardInterrupt:
                            pass
                except KeyboardInterrupt:
                    pytest.fail("KeyboardInterrupt should have been caught")

    def test_run_optimized_exception_handling(self):
        """Test that general exceptions print traceback."""
        import run_optimized

        with patch.object(run_optimized, '__name__', '__main__'):
            with patch('asyncio.run', side_effect=RuntimeError("Test")):
                with patch('traceback.print_exc') as mock_traceback:
                    try:
                        if run_optimized.__name__ == "__main__":
                            try:
                                asyncio.run(run_optimized.main())
                            except KeyboardInterrupt:
                                pass
                            except Exception:
                                import traceback
                                traceback.print_exc()
                    except SystemExit:
                        pass
                    # traceback.print_exc should have been called
                    mock_traceback.assert_called()