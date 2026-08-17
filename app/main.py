"""Main application entry point."""
import asyncio
import logging
import sys
import yaml
from pathlib import Path
from typing import Optional

from .scraper.facebook import FacebookScraper
from .database.db import CommentDatabase
from .monitor.detector import CommentDetector
from .renderer.cli import CLIRenderer
from .models.comment import Comment


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
            logging.FileHandler(log_config['file']),
            logging.StreamHandler()
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
            
            # Check login status
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
    
    async def _on_refresh(self, comments: list, new_count: int, updated_count: int) -> None:
        """Callback for refresh."""
        if self.detector.post_info:
            self.renderer.update_display(self.detector.post_info, comments)
    
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
            await self.detector.monitor_loop(post_url)
            
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
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
