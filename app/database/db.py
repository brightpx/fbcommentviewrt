"""Database operations for comment storage."""
import aiosqlite
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from ..models.comment import Comment, PostInfo


logger = logging.getLogger(__name__)


class CommentDatabase:
    """SQLite database for storing comments."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None
        
    async def initialize(self) -> None:
        """Initialize database and create tables."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = await aiosqlite.connect(
            self.db_path,
            timeout=30.0  # Increase timeout to 30 seconds
        )
        self.conn.row_factory = aiosqlite.Row
        
        # Enable WAL mode for better concurrent access
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA busy_timeout=30000")  # 30 seconds in milliseconds
        
        # Read and execute schema
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = f.read()
        
        await self.conn.executescript(schema)
        await self.conn.commit()
        logger.info(f"Database initialized at {self.db_path}")
    
    async def close(self) -> None:
        """Close database connection."""
        if self.conn:
            await self.conn.close()
            logger.info("Database connection closed")
    
    async def save_comment(self, comment: Comment, post_url: str) -> None:
        """Save or update a comment."""
        await self.conn.execute(
            """
            INSERT INTO comments 
            (id, parent_id, tier, author, message, created_time, last_seen, display_order, is_deleted, post_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_seen = excluded.last_seen,
                display_order = excluded.display_order,
                is_deleted = excluded.is_deleted
            """,
            (
                comment.id,
                comment.parent_id,
                comment.tier,
                comment.author,
                comment.message,
                comment.created_time,
                comment.last_seen,
                comment.display_order,
                comment.is_deleted,
                post_url
            )
        )
        await self.conn.commit()
    
    async def add_comment(
        self,
        comment_id: str,
        post_url: str,
        author: str,
        text: str,
        is_owner: bool = False,
        replied: bool = False,
        parent_id: Optional[str] = None,
        tier: int = 1
    ) -> None:
        """Save a comment using simple keyword arguments.

        Convenience wrapper used by the optimized monitor when a reply
        succeeds. Stores the comment with reply metadata in display_order
        (replied flag) so it can be audited later.

        Args:
            comment_id: Facebook comment ID
            post_url: URL of the post the comment belongs to
            author: Comment author name
            text: Comment message text
            is_owner: True if the comment is from the post owner
            replied: True if the bot has replied to this comment
            parent_id: Parent comment ID (for replies)
            tier: Comment tier (1 = top-level, 2 = first-level reply)
        """
        now = datetime.now()
        comment = Comment(
            id=comment_id,
            parent_id=parent_id,
            tier=tier,
            author=author,
            message=text,
            created_time=now,
            last_seen=now,
            # Reuse display_order as a "replied" marker (0 = not replied, 1 = replied)
            display_order=1 if replied else 0,
            is_new=False,
            children=[]
        )
        await self.save_comment(comment, post_url)
        logger.debug(f"add_comment: saved {comment_id} (owner={is_owner}, replied={replied})")

    async def save_comments_batch(self, comments: List[Comment], post_url: str) -> None:
        """Save multiple comments in a batch."""
        data = [
            (
                comment.id,
                comment.parent_id,
                comment.tier,
                comment.author,
                comment.message,
                comment.created_time,
                comment.last_seen,
                comment.display_order,
                comment.is_deleted,
                post_url
            )
            for comment in comments
        ]
        
        await self.conn.executemany(
            """
            INSERT INTO comments 
            (id, parent_id, tier, author, message, created_time, last_seen, display_order, is_deleted, post_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_seen = excluded.last_seen,
                display_order = excluded.display_order,
                is_deleted = excluded.is_deleted
            """,
            data
        )
        await self.conn.commit()
        logger.debug(f"Saved {len(comments)} comments to database")
    
    async def get_comments(self, post_url: str, limit: int = 0) -> List[Comment]:
        """Get all comments for a post."""
        query = """
            SELECT id, parent_id, tier, author, message, created_time, last_seen, display_order, is_deleted
            FROM comments
            WHERE post_url = ? AND is_deleted = 0
            ORDER BY display_order ASC
            """
        if limit > 0:
            query += f" LIMIT {limit}"
        
        cursor = await self.conn.execute(query, (post_url,))
        
        rows = await cursor.fetchall()
        comments = []
        
        for row in rows:
            comment = Comment(
                id=row['id'],
                parent_id=row['parent_id'],
                tier=row['tier'],
                author=row['author'],
                message=row['message'],
                created_time=datetime.fromisoformat(row['created_time']),
                last_seen=datetime.fromisoformat(row['last_seen']),
                display_order=row['display_order'],
                is_deleted=bool(row['is_deleted']),
                children=[]
            )
            comments.append(comment)
        
        return comments
    
    async def get_comment_ids(self, post_url: str) -> set:
        """Get all comment IDs for a post."""
        cursor = await self.conn.execute(
            "SELECT id FROM comments WHERE post_url = ? AND is_deleted = 0",
            (post_url,)
        )
        rows = await cursor.fetchall()
        return {row['id'] for row in rows}
    
    async def save_post_info(self, post_info: PostInfo) -> None:
        """Save or update post information."""
        now = datetime.now()
        await self.conn.execute(
            """
            INSERT INTO posts (url, group_name, post_id, author, content, first_seen, last_monitored)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                group_name = excluded.group_name,
                post_id = excluded.post_id,
                last_monitored = excluded.last_monitored
            """,
            (
                post_info.url,
                post_info.group_name,
                post_info.post_id,
                post_info.author,
                post_info.content,
                now,
                now
            )
        )
        await self.conn.commit()
    
    async def get_post_info(self, url: str) -> Optional[PostInfo]:
        """Get post information."""
        cursor = await self.conn.execute(
            "SELECT * FROM posts WHERE url = ?",
            (url,)
        )
        row = await cursor.fetchone()
        
        if row:
            return PostInfo(
                url=row['url'],
                group_name=row['group_name'],
                post_id=row['post_id'],
                author=row['author'],
                content=row['content']
            )
        return None
    
    async def get_statistics(self, post_url: str) -> Tuple[int, int]:
        """Get comment statistics."""
        cursor = await self.conn.execute(
            """
            SELECT 
                COUNT(CASE WHEN tier = 1 THEN 1 END) as comments,
                COUNT(CASE WHEN tier > 1 THEN 1 END) as replies
            FROM comments
            WHERE post_url = ? AND is_deleted = 0
            """,
            (post_url,)
        )
        row = await cursor.fetchone()
        return row['comments'], row['replies']
