"""CLI renderer using Rich library."""
import logging
from datetime import datetime
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.table import Table
from rich.layout import Layout
from rich.text import Text
from rich import box
from ..models.comment import Comment, PostInfo


logger = logging.getLogger(__name__)


class CLIRenderer:
    """Rich-based CLI renderer."""
    
    def __init__(self, config: dict):
        self.config = config
        self.console = Console()
        self.display_config = config['display']
        self.post_info: Optional[PostInfo] = None
        self.comments: List[Comment] = []
        
    def create_header(self) -> Panel:
        """Create header panel."""
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column(style="white")
        
        table.add_row("Group:", self.post_info.group_name if self.post_info else "N/A")
        table.add_row("Post URL:", self.post_info.url if self.post_info else "N/A")
        
        if self.post_info and self.post_info.last_refresh:
            table.add_row("Last Refresh:", self.post_info.last_refresh.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            table.add_row("Last Refresh:", "Never")
        
        table.add_row("Session Status:", "✅ Active")
        
        return Panel(
            table,
            title="[bold white]Facebook Group Comment Monitor[/bold white]",
            border_style="bright_blue",
            box=box.DOUBLE
        )
    
    def create_comment_table(self) -> Table:
        """Create comment table view (one row per comment, with nested replies indented)."""
        display_limit = self.config.get('monitor', {}).get('display_limit', 50)

        # Sort by display_order ascending (display_order=0 is newest comment from Facebook)
        sorted_comments = sorted(self.comments, key=lambda c: c.display_order, reverse=False)

        if display_limit == 0:
            title = f"Comments (showing all {len(sorted_comments)})"
            comments_to_show = sorted_comments
        else:
            actual_limit = min(display_limit, len(sorted_comments))
            title = f"Comments (showing first {actual_limit} of {len(sorted_comments)})"
            comments_to_show = sorted_comments[:display_limit] if len(sorted_comments) > display_limit else sorted_comments

        table = Table(
            title=title,
            box=box.SIMPLE_HEAVY,
            show_header=True,
            header_style="bold cyan",
            padding=(0, 1),
            show_lines=False,
        )
        table.add_column("Tier", width=5, no_wrap=True)
        table.add_column("Author", width=22, no_wrap=True)
        table.add_column("Message", min_width=40, ratio=1)
        table.add_column("Time", width=20, no_wrap=True, style="dim")

        if not self.comments:
            table.add_row("", "", "[dim]No comments yet...[/dim]", "")
            return table

        for comment in comments_to_show:
            self._add_comment_to_table(table, comment, depth=0)

        return table

    def _add_comment_to_table(self, table: Table, comment: Comment, depth: int = 0) -> None:
        """Add comment and its children to table, one row each with indented replies."""
        max_tier = self.config.get('monitor', {}).get('max_tier', 999)

        if comment.tier > max_tier:
            return

        color = self._get_tier_color(comment)
        new_dot = " [bright_green bold]●[/bright_green bold]" if comment.is_new else ""

        # Tier badge (compact)
        tier_badge = f"[{color}]T{comment.tier}[/{color}]{new_dot}"

        # Author with indentation showing reply hierarchy
        indent = "  " * depth
        prefix = "└ " if depth > 0 else ""
        author = f"[bold {color}]{indent}{prefix}{comment.author}[/bold {color}]"

        # Message — truncate to keep row single-line
        max_length = self.display_config.get('max_message_length', 80)
        message = comment.message.replace("\n", " ")
        if len(message) > max_length:
            message = message[:max_length] + "…"

        # Time
        time_str = self._format_time(comment.created_time)

        table.add_row(tier_badge, author, message, time_str)

        # Recurse into children
        for child in comment.children:
            if child.tier <= max_tier:
                self._add_comment_to_table(table, child, depth + 1)
    
    def _add_comment_to_tree(self, parent_tree: Tree, comment: Comment) -> None:
        """Recursively add comment to tree."""
        # Get color based on tier
        color = self._get_tier_color(comment)
        new_badge = " [bright_green bold]NEW[/bright_green bold]" if comment.is_new else ""
        
        # Format time
        time_str = self._format_time(comment.created_time)
        
        # Format message (truncate if too long)
        max_length = self.display_config['max_message_length']
        message = comment.message
        if len(message) > max_length:
            message = message[:max_length] + "..."
        
        # Create comment node
        tier_badge = f"[{color}][T{comment.tier}][/{color}]"
        comment_text = f"{tier_badge}{new_badge}\n"
        comment_text += f"[bold {color}]{comment.author}[/bold {color}]\n"
        comment_text += f"🕒 {time_str}\n"
        comment_text += f"└─ {message}"
        
        node = parent_tree.add(comment_text)
        
        # Get max_tier from config
        max_tier = self.config.get('monitor', {}).get('max_tier', 999)
        
        # Add children only if they don't exceed max_tier
        # When max_tier=1, only show top-level comments (no children)
        if max_tier > 1:
            for child in comment.children:
                if child.tier <= max_tier:
                    self._add_comment_to_tree(node, child)
    
    def _get_tier_color(self, comment: Comment) -> str:
        """Get color for tier."""
        colors = self.display_config['colors']
        
        if comment.is_new:
            if comment.tier == 1:
                return colors['new_comment']
            else:
                return colors['new_reply']
        
        if comment.tier == 1:
            return colors['tier1']
        elif comment.tier == 2:
            return colors['tier2']
        elif comment.tier == 3:
            return colors['tier3']
        else:
            return colors['tier4plus']
    
    def _format_time(self, dt: datetime) -> str:
        """Format timestamp with relative time."""
        time_str = dt.strftime("%H:%M:%S")
        
        if self.display_config['show_relative_time']:
            now = datetime.now()
            delta = now - dt
            
            if delta.total_seconds() < 60:
                relative = f"{int(delta.total_seconds())} sec ago"
            elif delta.total_seconds() < 3600:
                relative = f"{int(delta.total_seconds() / 60)} min ago"
            elif delta.total_seconds() < 86400:
                relative = f"{int(delta.total_seconds() / 3600)} hr ago"
            else:
                relative = f"{int(delta.total_seconds() / 86400)} day ago"
            
            time_str += f" ({relative})"
        
        return time_str
    
    def create_layout(self) -> Layout:
        """Create main layout."""
        layout = Layout()
        layout.split_column(
            Layout(self.create_header(), size=10),
            Layout(self.create_comment_table())
        )
        return layout
    
    def update_display(self, post_info: PostInfo, comments: List[Comment]) -> None:
        """Update display with new data."""
        self.post_info = post_info
        self.comments = comments
        logger.debug(f"Display updated: {len(comments)} comments")
        
        # Clear and print updated layout
        self.console.clear()
        self.console.print(self.create_layout())
    
    def start_live_display(self, post_info: PostInfo, comments: List[Comment]) -> None:
        """Start live display."""
        self.post_info = post_info
        self.comments = comments
        logger.info(f"Live display started: {len(comments)} comments")
        
        # Print initial layout
        self.console.clear()
        self.console.print(self.create_layout())
    
    def stop_live_display(self) -> None:
        """Stop live display."""
        # No-op since we're not using Live anymore
        pass
    
    def show_notification_new_comment(self, comment: Comment) -> None:
        """Show notification for new comment."""
        if not self.config['monitor']['enable_notifications']:
            return
        
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column(style="white")
        
        table.add_row("Author:", comment.author)
        table.add_row("Tier:", f"T{comment.tier}")
        table.add_row("Time:", comment.created_time.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Message:", comment.message[:200])
        
        logger.info(f"NEW COMMENT DETECTED: {comment.author} (T{comment.tier}) - {comment.message[:100]}")
    
    def show_notification_new_reply(self, comment: Comment) -> None:
        """Show notification for new reply."""
        if not self.config['monitor']['enable_notifications']:
            return
        
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column(style="white")
        
        table.add_row("Author:", comment.author)
        table.add_row("Tier:", f"T{comment.tier}")
        table.add_row("Parent Comment:", comment.parent_id or "Unknown")
        table.add_row("Time:", comment.created_time.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Message:", comment.message[:200])
        
        logger.info(f"NEW REPLY DETECTED: {comment.author} (T{comment.tier}) - {comment.message[:100]}")

    
    def show_error(self, message: str) -> None:
        """Show error message."""
        logger.error(f"Error: {message}")
    
    def show_success(self, message: str) -> None:
        """Show success message."""
        logger.info(f"Success: {message}")
    
    def show_info(self, message: str) -> None:
        """Show info message."""
        logger.info(f"Info: {message}")
    
    def show_warning(self, message: str) -> None:
        """Show warning message."""
        logger.warning(f"Warning: {message}")
    
    def prompt_input(self, message: str) -> str:
        """Prompt user for input."""
        return self.console.input(f"[bold cyan]{message}[/bold cyan] ")
    
    def clear_screen(self) -> None:
        """Clear console screen."""
        self.console.clear()
