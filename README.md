# Facebook Group Comment Monitor

Real-time Facebook Group comment monitoring tool with CLI interface. Monitor comments and replies from Facebook Groups (both Public and Private) with live updates and tree-structured display.

## Features

- 🔐 **Session Management**: Login once and reuse session automatically
- 📊 **Real-time Monitoring**: Refresh every 0.5 seconds to detect new comments
- 🌲 **Tree View Display**: Hierarchical comment structure with tier levels
- 🎨 **Color-coded Tiers**: Visual distinction between comment levels
- 💾 **SQLite Database**: Persistent storage for comment history
- 🔔 **Notifications**: Alert for new comments and replies
- 🚀 **High Performance**: Handles 10,000+ comments efficiently
- 🌐 **Multi-language Support**: Works with Thai and English Facebook

## Requirements

- Python 3.12+
- Windows/Linux/macOS
- Internet connection
- Facebook account with access to target groups

## Installation

1. Clone or download the repository:
```bash
cd fbcommentviewrt
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

4. Copy configuration file:
```bash
copy config.yaml.example config.yaml
```

## Configuration

Edit `config.yaml` to customize settings:

```yaml
# Target post URL to monitor
target:
  post_url: "https://www.facebook.com/groups/YOUR_GROUP_ID/posts/YOUR_POST_ID/"

browser:
  headless: false        # Set true to hide browser window
  timeout: 30000         # Request timeout in milliseconds
  
monitor:
  refresh_interval: 0.5  # Refresh frequency in seconds
  enable_notifications: true

display:
  max_message_length: 200  # Truncate long messages
  show_relative_time: true # Show "5 min ago" format
```

**Important**: Replace `YOUR_GROUP_ID` and `YOUR_POST_ID` with actual values from your target Facebook post URL.

## Usage

### First Run (Login)

1. Run the application:
```bash
python -m app.main
```

2. A browser window will open to Facebook login page
3. Login with your Facebook account
4. Session will be saved automatically to `session/fb_session.json`

### Subsequent Runs

1. Configure your target post URL in `config.yaml`:
```yaml
target:
  post_url: "https://www.facebook.com/groups/123456789/posts/987654321/"
```

2. Run the application:
```bash
python -m app.main
```

3. The monitor will automatically start monitoring the configured post URL

### Supported URL Formats

- Public Group Post: `https://www.facebook.com/groups/{group_id}/posts/{post_id}`
- Private Group Post: `https://www.facebook.com/groups/{group_id}/posts/{post_id}` (must be a member)
- Permalink: `https://www.facebook.com/groups/{group_id}/permalink/{post_id}`

## Display Format

```
================================================
Facebook Group Comment Monitor
================================================

Group: Example Group Name
Post URL: https://www.facebook.com/...
Last Refresh: 2026-08-17 10:30:45
Total Comments: 42
Total Replies: 87
Session Status: ✅ Active

================================================

📝 Comments
[T1][NEW]
Somchai
🕒 09:30:21 (5 sec ago)
└─ สนใจครับ

   [T2][NEW]
   Admin
   🕒 09:30:33 (2 min ago)
   └─ ทัก inbox ได้เลยครับ

      [T3]
      Somchai
      🕒 09:31:10 (5 min ago)
      └─ ขอบคุณครับ
```

## Color Legend

- **Tier 1** (Green): Main comments
- **Tier 2** (Cyan): First-level replies
- **Tier 3** (Yellow): Second-level replies
- **Tier 4+** (Red): Deep nested replies
- **NEW** (Bright colors): Newly detected comments/replies

## Database

All comments are stored in `database/comments.db` (SQLite):

- **comments**: Comment data with full hierarchy
- **posts**: Post metadata
- **sessions**: Session tracking

Data persists across runs, allowing you to:
- Review comment history
- Detect truly new comments (not seen before)
- Resume monitoring after restart

## Project Structure

```
fbcommentviewrt/
├── app/
│   ├── main.py              # Main application entry point
│   ├── __init__.py          # Package initialization
│   │
│   ├── models/
│   │   └── comment.py       # Data models (Comment, PostInfo)
│   │
│   ├── scraper/
│   │   ├── facebook.py      # Browser automation with Playwright
│   │   └── parser.py        # HTML parsing and comment extraction
│   │
│   ├── monitor/
│   │   ├── detector.py      # Change detection and monitoring loop
│   │   └── cache.py         # In-memory cache for diff detection
│   │
│   ├── renderer/
│   │   └── cli.py           # Rich-based CLI rendering
│   │
│   └── database/
│       ├── db.py            # Database operations
│       └── schema.sql       # Database schema
│
├── session/
│   └── fb_session.json      # Saved Facebook session (created on first login)
│
├── database/
│   └── comments.db          # SQLite database (created automatically)
│
├── logs/
│   └── app.log              # Application logs
│
├── config.yaml              # User configuration
├── config.yaml.example      # Configuration template
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## Architecture

### Clean Architecture Principles

1. **Models Layer**: Pure data structures (Comment, PostInfo)
2. **Scraper Layer**: Browser automation and HTML parsing
3. **Monitor Layer**: Change detection and caching logic
4. **Renderer Layer**: CLI display and user interaction
5. **Database Layer**: Data persistence

### Key Components

**FacebookScraper**
- Playwright-based browser automation
- Session management
- Page navigation and interaction
- Comment expansion (load more buttons)

**FacebookParser**
- HTML parsing with BeautifulSoup
- Comment extraction from DOM
- Hierarchy detection (tier calculation)
- Timestamp parsing (relative and absolute)

**CommentDetector**
- Real-time monitoring loop
- Change detection using cache
- New comment/reply identification
- Event callbacks for notifications

**CommentCache**
- In-memory diff detection
- Fast lookup by comment ID
- Tree flattening utilities

**CommentDatabase**
- SQLite operations
- Batch inserts for performance
- Comment history tracking
- Statistics aggregation

**CLIRenderer**
- Rich library integration
- Live updating display
- Tree view rendering
- Color-coded tiers
- Notification panels

## Error Handling

### Session Expired

If session expires:
```
⚠️ Warning: Session expired
ℹ️ Info: Please login in the browser window...
```

The browser will open for re-authentication.

### Connection Issues

If network fails:
```
❌ Error: Failed to navigate to post
```

The monitor will continue retrying based on `refresh_interval`.

### Access Denied (Private Group)

```
❌ Error: Cannot access private group
```

Ensure your Facebook account is a member of the group.

## Performance Optimization

- **Incremental Rendering**: Only updates changed comments
- **Batch Database Operations**: Reduces I/O overhead
- **Efficient Caching**: O(1) lookup for comment changes
- **Lazy Loading**: Expands comments progressively
- **Memory Efficient**: Handles 10,000+ comments

## Troubleshooting

### Browser doesn't open

```bash
playwright install chromium
```

### "Module not found" errors

```bash
pip install -r requirements.txt
```

### Session keeps expiring

Delete `session/fb_session.json` and login again:
```bash
del session\fb_session.json
python -m app.main
```

### No comments detected

1. Ensure the post URL is correct
2. Check if you have access to the group
3. Verify the post has comments
4. Check `logs/app.log` for detailed errors

### High CPU usage

Increase `refresh_interval` in `config.yaml`:
```yaml
monitor:
  refresh_interval: 1.0  # Slower refresh rate
```

## Development

### Adding New Features

1. **Add data fields**: Update `models/comment.py`
2. **Modify parsing**: Edit `scraper/parser.py`
3. **Change display**: Update `renderer/cli.py`
4. **Database schema**: Modify `database/schema.sql`

### Running in Debug Mode

```yaml
logging:
  level: "DEBUG"
```

### Testing

The application logs detailed information to `logs/app.log`:
```bash
tail -f logs/app.log  # Linux/Mac
Get-Content logs/app.log -Wait  # Windows PowerShell
```

## Security Notes

⚠️ **Important Security Considerations**:

1. **Session File**: `session/fb_session.json` contains authentication tokens
   - Keep it private
   - Don't commit to version control
   - Don't share with others

2. **Database**: `comments.db` may contain personal information
   - Secure file permissions
   - Regular backups recommended

3. **Logging**: Logs may contain sensitive data
   - Review before sharing
   - Rotate logs regularly

## Limitations

- Facebook's UI changes may break parsing (update parser as needed)
- Rate limiting may occur with very frequent refreshes
- Large groups (100,000+ comments) may be slow to load
- Nested replies beyond 10 levels are capped at tier 10
- Requires active internet connection

## Future Enhancements

- [ ] Multi-post monitoring
- [ ] Keyword filtering
- [ ] Export to CSV/JSON
- [ ] Sentiment analysis
- [ ] User statistics
- [ ] REST API endpoint
- [ ] Web dashboard
- [ ] Docker support

## License

This project is for educational purposes only. Use responsibly and comply with Facebook's Terms of Service.

## Support

For issues or questions:
1. Check `logs/app.log` for errors
2. Review this README
3. Check configuration in `config.yaml`

## Changelog

### Version 1.0.0 (2026-08-17)
- Initial release
- Real-time comment monitoring
- Session management
- Tree view display
- SQLite storage
- Color-coded tiers
- Notification system
