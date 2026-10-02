#!/usr/bin/env python
"""
Post a comment to Facebook

Usage:
    python post_comment.py "Your comment message here"
    python post_comment.py --reply "Your reply message" --owner "Owner Name"
"""

import sys
import asyncio
import yaml
import logging
from pathlib import Path
from app.scraper.facebook import FacebookScraper


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def post_comment(message: str):
    """Post a comment to Facebook."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Load config
    config = load_config()
    post_url = config['target']['post_url']
    
    # Initialize scraper
    scraper = FacebookScraper(config)
    
    try:
        logger.info("Initializing browser...")
        await scraper.initialize()
        
        logger.info(f"Navigating to post: {post_url}")
        await scraper.navigate_to_post(post_url)
        
        logger.info("Posting comment...")
        success = await scraper.post_comment(message)
        
        if success:
            print(f"\n✅ Comment posted successfully!")
            print(f"Message: {message}")
        else:
            print(f"\n❌ Failed to post comment")
            print(f"Check screenshots/ directory for debugging")
        
        # Wait a bit to see the result
        await asyncio.sleep(2)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"\n❌ Error: {e}")
    finally:
        logger.info("Closing browser...")
        await scraper.close()


async def reply_to_owner(message: str, owner_name: str):
    """Reply to the latest comment from the post owner."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Load config
    config = load_config()
    post_url = config['target']['post_url']
    
    # Initialize scraper
    scraper = FacebookScraper(config)
    
    try:
        logger.info("Initializing browser...")
        await scraper.initialize()
        
        logger.info(f"Navigating to post: {post_url}")
        await scraper.navigate_to_post(post_url)
        
        logger.info(f"Replying to owner's comment: {owner_name}")
        success = await scraper.reply_to_latest_owner_comment(message, owner_name)
        
        if success:
            print(f"\n✅ Reply posted successfully!")
            print(f"Reply to: {owner_name}")
            print(f"Message: {message}")
        else:
            print(f"\n❌ Failed to post reply")
            print(f"Check screenshots/ directory for debugging")
        
        # Wait a bit to see the result
        await asyncio.sleep(2)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"\n❌ Error: {e}")
    finally:
        logger.info("Closing browser...")
        await scraper.close()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print('  Post T1 comment: python post_comment.py "Your comment message"')
        print('  Reply T2 to owner: python post_comment.py --reply "Your reply" --owner "Owner Name"')
        print("\nExamples:")
        print('  python post_comment.py "Hello, this is a test!"')
        print('  python post_comment.py --reply "Thank you!" --owner "John Doe"')
        sys.exit(1)
    
    # Check if this is a reply command
    if '--reply' in sys.argv:
        try:
            reply_idx = sys.argv.index('--reply')
            owner_idx = sys.argv.index('--owner')
            
            message = sys.argv[reply_idx + 1]
            owner_name = sys.argv[owner_idx + 1]
            
            if not message.strip() or not owner_name.strip():
                print("❌ Error: Reply message and owner name cannot be empty")
                sys.exit(1)
            
            print(f"\n🚀 Replying to {owner_name}: {message}\n")
            asyncio.run(reply_to_owner(message, owner_name))
            
        except (ValueError, IndexError):
            print("❌ Error: Invalid reply command format")
            print('Usage: python post_comment.py --reply "Your reply" --owner "Owner Name"')
            sys.exit(1)
    else:
        # Regular T1 comment
        message = sys.argv[1]
        
        if not message.strip():
            print("❌ Error: Comment message cannot be empty")
            sys.exit(1)
        
        print(f"\n🚀 Posting comment: {message}\n")
        asyncio.run(post_comment(message))


if __name__ == "__main__":
    main()
