"""Main application entry point."""
import asyncio
import logging
import sys
import yaml
import threading
from pathlib import Path
from typing import Optional

from .scraper.facebook import FacebookScraper
from .database.db import CommentDatabase
from .monitor.detector import CommentDetector
from .renderer.cli import CLIRenderer
from .models.comment import Comment

try:
    import msvcrt  # Windows only
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False


# Configure logging
def setup_logging(config: dict) -> None:
    """Setup logging configuration."""
    log_config = config['logging']
    log_path = Path(log_config['file'])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_config['level']),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_config['file'], encoding='utf-8', errors='replace')
        ]
    )


def cleanup_screenshots() -> None:
    """Delete all .png files in screenshots directory."""
    screenshots_dir = Path("screenshots")
    if screenshots_dir.exists():
        png_files = list(screenshots_dir.glob("*.png"))
        if png_files:
            logger = logging.getLogger(__name__)
            logger.info(f"Cleaning up {len(png_files)} screenshot files...")
            for png_file in png_files:
                try:
                    png_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete {png_file}: {e}")
            logger.info("Screenshot cleanup completed")


logger = logging.getLogger(__name__)


class FacebookCommentMonitor:
    """Main application class."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        setup_logging(self.config)
        
        self.scraper: Optional[FacebookScraper] = None
        self.database: Optional[CommentDatabase] = None
        self.detector: Optional[CommentDetector] = None
        self.renderer: Optional[CLIRenderer] = None
        
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        
        if not config_file.exists():
            # Try to load from example
            example_file = Path("config.yaml.example")
            if example_file.exists():
                logger.info("Config file not found, copying from example...")
                import shutil
                shutil.copy(example_file, config_file)
            else:
                raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    async def initialize(self) -> bool:
        """Initialize all components."""
        try:
            logger.info("Initializing Facebook Comment Monitor...")
            
            # Clean up old screenshots
            cleanup_screenshots()
            
            # Initialize renderer
            self.renderer = CLIRenderer(self.config)
            self.renderer.show_info("Starting initialization...")
            
            # Initialize database
            self.database = CommentDatabase(self.config['database']['path'])
            await self.database.initialize()
            self.renderer.show_success("Database initialized")
            
            # Initialize scraper
            self.scraper = FacebookScraper(self.config)
            await self.scraper.initialize()
            self.renderer.show_success("Browser initialized")
            
            # Get post URL from config early
            post_url = self.config.get('target', {}).get('post_url', '')
            
            # Navigate to post_url directly (will check login there)
            if post_url and post_url != "https://www.facebook.com/groups/YOUR_GROUP_ID/posts/YOUR_POST_ID/":
                self.renderer.show_info(f"Opening post: {post_url}")
                try:
                    await self.scraper.page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
                    await self.scraper.page.wait_for_timeout(self.config['monitor']['timings']['after_goto_post'])
                    
                    # Check if login is required (redirected to login page)
                    current_url = self.scraper.page.url
                    if "login" in current_url.lower():
                        self.renderer.show_warning("Not logged in to Facebook")
                        self.renderer.show_info("Please login in the browser window...")
                        
                        if not await self.scraper.login():
                            self.renderer.show_error("Login failed")
                            return False
                        
                        self.renderer.show_success("Login successful")
                        # Navigate back to post after login
                        await self.scraper.page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
                    else:
                        self.renderer.show_success("Already logged in to Facebook")
                except Exception as e:
                    logger.error(f"Error navigating to post: {e}")
                    self.renderer.show_error(f"Failed to open post: {e}")
                    return False
            else:
                # No valid post_url, check login status normally
                is_logged_in = await self.scraper.is_logged_in()
                
                if not is_logged_in:
                    self.renderer.show_warning("Not logged in to Facebook")
                    self.renderer.show_info("Please login in the browser window...")
                    
                    if not await self.scraper.login():
                        self.renderer.show_error("Login failed")
                        return False
                    
                    self.renderer.show_success("Login successful")
                else:
                    self.renderer.show_success("Already logged in to Facebook")
            
            # Initialize detector
            self.detector = CommentDetector(
                self.scraper,
                self.database,
                self.config
            )
            
            # Setup callbacks
            self.detector.on_new_comment = self._on_new_comment
            self.detector.on_new_reply = self._on_new_reply
            self.detector.on_refresh = self._on_refresh
            
            self.renderer.show_success("All components initialized")
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            if self.renderer:
                self.renderer.show_error(f"Initialization failed: {e}")
            return False
    
    async def _on_new_comment(self, comment: Comment) -> None:
        """Callback for new comment."""
        self.renderer.show_notification_new_comment(comment)
    
    async def _on_new_reply(self, comment: Comment) -> None:
        """Callback for new reply."""
        self.renderer.show_notification_new_reply(comment)
    
    async def _on_refresh(self, comments: list, post_info) -> None:
        """Callback for refresh."""
        logger.info(f"_on_refresh called with {len(comments)} comments")
        if post_info:
            logger.info("Calling renderer.update_display...")
            self.renderer.update_display(post_info, comments)
            logger.info("renderer.update_display completed")
    
    async def _check_and_post_comment(self) -> None:
        """Post a test comment (for testing purposes only)."""
        # This method is kept for potential future manual testing
        # but is no longer called from the monitoring loop
        return
    
    async def post_new_comment(self, message: str) -> bool:
        """Post a new comment to Facebook (public API)
        
        Opens a separate browser session to post the comment,
        without interfering with the monitoring session.
        
        Args:
            message: Comment message to post
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            from datetime import datetime
            log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            self.renderer.show_info(f"Posting comment in separate session: {message}")
            logger.info(f"[{log_time}] Posting comment in separate session: {message}")
            
            # Use separate session method with post URL
            post_url = self.config['target']['post_url']
            success = await self.scraper.post_comment_separate_session(message, post_url)
            
            if success:
                logger.info(f"[{log_time}] Comment posted successfully: {message}")
                self.renderer.show_success(f"Comment posted: {message}")
                self.renderer.show_info("Waiting 5 seconds for comment to appear...")
                await asyncio.sleep(self.config['monitor']['timings']['after_post_success'] / 1000.0)
                # Force refresh to show new comment immediately
                await self.detector.refresh_comments()
                # Give user time to see the new comment before next refresh cycle
                self.renderer.show_success("New comment displayed! Resuming normal refresh cycle...")
                await asyncio.sleep(self.config['monitor']['timings']['after_post_refresh'] / 1000.0)
                return True
            else:
                logger.error(f"[{log_time}] ✗ Failed to post comment: {message}")
                self.renderer.show_error("Failed to post comment")
                return False
                
        except Exception as e:
            from datetime import datetime
            log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.error(f"[{log_time}] ✗ Error posting comment: {e}", exc_info=True)
            self.renderer.show_error(f"Comment error: {e}")
            return False
    
    async def start_monitoring(self, post_url: str) -> None:
        """Start monitoring a post."""
        try:
            self.renderer.show_info(f"Starting monitoring: {post_url}")
            
            # Start monitoring
            if not await self.detector.start_monitoring(post_url):
                self.renderer.show_error("Failed to start monitoring")
                return
            
            # Initial refresh
            comments = await self.detector.refresh_comments()
            
            # Start live display
            self.renderer.start_live_display(self.detector.post_info, comments)
            
            # Start monitoring loop
            refresh_interval_ms = self.config['monitor']['refresh_interval']
            refresh_interval = refresh_interval_ms / 1000.0
            
            # Keep-alive background task
            keep_alive_config = self.config['monitor'].get('keep_alive', {})
            keep_alive_task = None
            
            if keep_alive_config.get('enabled', False):
                async def keep_alive_loop():
                    interval = keep_alive_config.get('interval', 45)
                    while self.detector.is_running:
                        await asyncio.sleep(interval)
                        if self.detector.is_running:
                            await self.scraper.keep_alive()
                
                keep_alive_task = asyncio.create_task(keep_alive_loop())
                logger.info(f"Keep-alive enabled: {keep_alive_config.get('interval', 45)}s interval")
            
            try:
                while self.detector.is_running:
                    try:
                        
                        # Refresh comments and update display
                        await self.detector.refresh_comments()
                        
                        # Sleep for the configured interval before next refresh
                        await asyncio.sleep(refresh_interval)
                        
                    except KeyboardInterrupt:
                        # User pressed Ctrl+C - stop monitoring
                        logger.info("Monitoring stopped by user")
                        self.detector.stop_monitoring()
                        raise  # Re-raise to propagate to main()
                    except Exception as e:
                        logger.error(f"Error in monitor loop: {e}")
                        await asyncio.sleep(self.config['monitor']['timings']['error_retry_delay'] / 1000.0)
            finally:
                # Cancel keep-alive task when monitoring stops
                if keep_alive_task:
                    keep_alive_task.cancel()
                    try:
                        await keep_alive_task
                    except asyncio.CancelledError:
                        pass
            
        except KeyboardInterrupt:
            # User pressed Ctrl+C - stop and cleanup
            logger.info("Monitoring interrupted by user")
            self.renderer.stop_live_display()
            self.renderer.show_info("\n\nMonitoring stopped by user.")
            raise  # Re-raise to exit cleanly
        except Exception as e:
            logger.error(f"Error during monitoring: {e}", exc_info=True)
            self.renderer.show_error(f"Monitoring error: {e}")
        finally:
            self.renderer.stop_live_display()
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            logger.info("Cleaning up resources...")
            
            if self.detector:
                self.detector.stop_monitoring()
            
            if self.scraper:
                await self.scraper.close()
            
            if self.database:
                await self.database.close()
            
            if self.renderer:
                self.renderer.show_success("Cleanup complete")
            
            logger.info("Cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
    
    async def run(self) -> None:
        """Main run method."""
        try:
            # Initialize
            if not await self.initialize():
                return
            
            # Get post URL from config
            self.renderer.clear_screen()
            post_url = self.config.get('target', {}).get('post_url', '')
            
            if not post_url or post_url == "https://www.facebook.com/groups/YOUR_GROUP_ID/posts/YOUR_POST_ID/":
                self.renderer.show_error("Please configure 'target.post_url' in config.yaml")
                self.renderer.show_info("Example: https://www.facebook.com/groups/123456789/posts/987654321/")
                return
            
            self.renderer.show_info(f"Monitoring post from config: {post_url}")
            
            # Start monitoring
            await self.start_monitoring(post_url)
            
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            if self.renderer:
                self.renderer.show_error(f"Application error: {e}")
        finally:
            await self.cleanup()


async def main():
    """Main entry point."""
    try:
        monitor = FacebookCommentMonitor()
        await monitor.run()
    except KeyboardInterrupt:
        # User pressed Ctrl+C - exit cleanly without extra message
        pass
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
