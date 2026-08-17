# Quick Start Guide

## Installation

1. **Install Python 3.12+**
   - Download from https://www.python.org/downloads/

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

4. **Setup configuration**
   ```bash
   # Windows
   copy config.yaml.example config.yaml
   
   # Linux/Mac
   cp config.yaml.example config.yaml
   ```

5. **Configure target post URL**
   
   Edit `config.yaml` and set your Facebook post URL:
   ```yaml
   target:
     post_url: "https://www.facebook.com/groups/YOUR_GROUP_ID/posts/YOUR_POST_ID/"
   ```

## First Run (Login)

```bash
python -m app.main
```

Or using the run script:
```bash
python run.py
```

1. Browser window will open automatically
2. Login to Facebook with your account
3. Session will be saved to `session/fb_session.json`
4. You only need to login once
5. Monitor will start automatically with configured URL

## Daily Usage

1. **Configure post URL in config.yaml**
   ```yaml
   target:
     post_url: "https://www.facebook.com/groups/123456789/posts/987654321/"
   ```

2. **Start the monitor**
   ```bash
   python -m app.main
   ```

3. **Monitor displays automatically**
   - Comments appear in tree structure
   - New comments show [NEW] badge
   - Colors indicate tier level
   - Updates every 0.5 seconds

4. **Stop monitoring**
   - Press `Ctrl+C` to stop

## Configuration Options

Edit `config.yaml`:

### Target Post URL
```yaml
target:
  post_url: "https://www.facebook.com/groups/123456789/posts/987654321/"
```

### Refresh Speed
```yaml
monitor:
  refresh_interval: 0.5  # seconds (0.5 = fast, 1.0 = moderate, 2.0 = slow)
```

### Headless Mode (No Browser Window)
```yaml
browser:
  headless: true  # true = hidden, false = visible
```

### Notifications
```yaml
monitor:
  enable_notifications: true  # true = show alerts, false = silent
```

### Display
```yaml
display:
  max_message_length: 200  # truncate long messages
  show_relative_time: true # show "5 min ago"
```

## Troubleshooting

### "Please configure target.post_url"
```bash
# Edit config.yaml and set a valid Facebook post URL
# Make sure to replace YOUR_GROUP_ID and YOUR_POST_ID with actual values
```

### "playwright not found"
```bash
pip install playwright
playwright install chromium
```

### Session expired
```bash
# Delete session file and login again
# Windows
del session\fb_session.json

# Linux/Mac
rm session/fb_session.json
```

### Cannot access private group
- Make sure your Facebook account is a member of the group
- Login with the correct account

### No comments showing
1. Verify post URL is correct
2. Check if post has comments
3. Wait a few seconds for loading
4. Check logs: `logs/app.log`

## URL Formats

### Public Group Post
```
https://www.facebook.com/groups/GROUP_ID/posts/POST_ID
```

### Private Group Post
```
https://www.facebook.com/groups/GROUP_ID/posts/POST_ID
```
(Must be a group member)

### Permalink Format
```
https://www.facebook.com/groups/GROUP_ID/permalink/POST_ID
```

## Understanding the Display

```
[T1][NEW]           ← Tier 1 (main comment), NEW badge
Somchai             ← Author name
🕒 09:30:21 (5s)    ← Timestamp with relative time
└─ สนใจครับ         ← Comment message

   [T2]             ← Tier 2 (reply to T1)
   Admin            ← Reply author
   🕒 09:30:33 (2m)
   └─ ทัก inbox ได้เลย

      [T3]          ← Tier 3 (reply to T2)
      Somchai
      🕒 09:31:10
      └─ ขอบคุณครับ
```

### Color Legend
- **Green** = Tier 1 (main comments)
- **Cyan** = Tier 2 (first replies)
- **Yellow** = Tier 3 (nested replies)
- **Red** = Tier 4+ (deep nesting)
- **Bright colors** = NEW items

## Tips

1. **Multiple Posts**: Stop current monitor (Ctrl+C) and start with new URL

2. **Performance**: Increase `refresh_interval` if CPU usage is high

3. **History**: All comments saved to database for later review

4. **Logs**: Check `logs/app.log` for detailed information

5. **Security**: Keep `session/fb_session.json` private (contains login tokens)

## Need Help?

1. Check `README.md` for full documentation
2. Review `logs/app.log` for error details
3. Verify `config.yaml` settings
4. Ensure Facebook account has access to target group

## Quick Commands

```bash
# Start monitoring
python -m app.main

# Install/update dependencies
pip install -r requirements.txt

# Reinstall browser
playwright install chromium

# View logs (Windows PowerShell)
Get-Content logs/app.log -Wait

# View logs (Linux/Mac)
tail -f logs/app.log

# Clear session (logout)
del session\fb_session.json  # Windows
rm session/fb_session.json   # Linux/Mac

# Clear database (reset)
del database\comments.db     # Windows
rm database/comments.db      # Linux/Mac
```
