"""CLI renderer using Rich library."""
import logging
from datetime import datetime
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
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
        self.live: Optional[Live] = None
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
        
        if self.post_info:
            table.add_row("Total Comments:", str(self.post_info.total_comments))
            table.add_row("Total Replies:", str(self.post_info.total_replies))
        else:
            table.add_row("Total Comments:", "0")
            table.add_row("Total Replies:", "0")
        
        table.add_row("Session Status:", "✅ Active")
        
        return Panel(
            table,
            title="[bold white]Facebook Group Comment Monitor[/bold white]",
            border_style="bright_blue",
            box=box.DOUBLE
        )
    
    def create_comment_tree(self) -> Tree:
        """Create comment tree view."""
        tree = Tree("📝 Comments", style="bold white")
        
        if not self.comments:
            tree.add("[dim]No comments yet...[/dim]")
            return tree
        
        for comment in self.comments:
            self._add_comment_to_tree(tree, comment)
        
        return tree
    
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
        
        # Add children
        for child in comment.children:
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
            Layout(self.create_comment_tree())
        )
        return layout
    
    def update_display(self, post_info: PostInfo, comments: List[Comment]) -> None:
        """Update display with new data."""
        self.post_info = post_info
        self.comments = comments
        
        if self.live:
            self.live.update(self.create_layout())
    
    def start_live_display(self, post_info: PostInfo, comments: List[Comment]) -> None:
        """Start live display."""
        self.post_info = post_info
        self.comments = comments
        
        self.live = Live(
            self.create_layout(),
            console=self.console,
            refresh_per_second=2,
            screen=True
        )
        self.live.start()
    
    def stop_live_display(self) -> None:
        """Stop live display."""
        if self.live:
            self.live.stop()
    
    def show_notification_new_comment(self, comment: Comment) -> None:
        """Show notification for new comment."""
        if not self.config['monitor']['enable_notifications']:
            return
        
        # Temporarily stop live display
        was_live = self.live is not None
        if was_live:
            self.stop_live_display()
        
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column(style="white")
        
        table.add_row("Author:", comment.author)
        table.add_row("Tier:", f"T{comment.tier}")
        table.add_row("Time:", comment.created_time.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Message:", comment.message[:200])
        
        panel = Panel(
            table,
            title="[bold bright_green]🔔 NEW COMMENT DETECTED[/bold bright_green]",
            border_style="bright_green",
            box=box.DOUBLE
        )
        
        self.console.print(panel)
        
        # Restart live display
        if was_live:
            self.start_live_display(self.post_info, self.comments)
    
    def show_notification_new_reply(self, comment: Comment) -> None:
        """Show notification for new reply."""
        if not self.config['monitor']['enable_notifications']:
            return
        
        # Temporarily stop live display
        was_live = self.live is not None
        if was_live:
            self.stop_live_display()
        
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column(style="white")
        
        table.add_row("Author:", comment.author)
        table.add_row("Tier:", f"T{comment.tier}")
        table.add_row("Parent Comment:", comment.parent_id or "Unknown")
        table.add_row("Time:", comment.created_time.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Message:", comment.message[:200])
        
        panel = Panel(
            table,
            title="[bold bright_cyan]🔔 NEW REPLY DETECTED[/bold bright_cyan]",
            border_style="bright_cyan",
            box=box.DOUBLE
        )
        
        self.console.print(panel)
        
        # Restart live display
        if was_live:
            self.start_live_display(self.post_info, self.comments)
    
    def show_error(self, message: str) -> None:
        """Show error message."""
        self.console.print(f"[bold red]❌ Error:[/bold red] {message}")
    
    def show_success(self, message: str) -> None:
        """Show success message."""
        self.console.print(f"[bold green]✅ Success:[/bold green] {message}")
    
    def show_info(self, message: str) -> None:
        """Show info message."""
        self.console.print(f"[bold cyan]ℹ️  Info:[/bold cyan] {message}")
    
    def show_warning(self, message: str) -> None:
        """Show warning message."""
        self.console.print(f"[bold yellow]⚠️  Warning:[/bold yellow] {message}")
    
    def prompt_input(self, message: str) -> str:
        """Prompt user for input."""
        return self.console.input(f"[bold cyan]{message}[/bold cyan] ")
    
    def clear_screen(self) -> None:
        """Clear console screen."""
        self.console.clear()
