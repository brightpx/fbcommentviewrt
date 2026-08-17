# Error Handling Strategy

## Overview

The Facebook Comment Monitor implements comprehensive error handling at multiple layers to ensure robustness and reliability.

## Error Categories

### 1. Network Errors

**Symptoms:**
- Connection timeout
- DNS resolution failure
- Network unavailable

**Handling:**
```python
# In FacebookScraper.navigate_to_post()
try:
    await self.page.goto(url, wait_until="domcontentloaded")
except Exception as e:
    logger.error(f"Failed to navigate: {e}")
    return False  # Graceful failure, retry on next loop
```

**Recovery:**
- Log error with context
- Return failure status
- Monitor loop retries automatically
- User sees warning in CLI

### 2. Session Errors

**Symptoms:**
- Session expired
- Invalid cookies
- Authentication required

**Handling:**
```python
# In FacebookScraper.is_logged_in()
try:
    # Check login status
    is_logged_in = await self._check_login_indicators()
    if not is_logged_in:
        # Trigger re-login flow
        return False
except Exception:
    # Session file corrupted
    return False
```

**Recovery:**
- Delete invalid session file
- Prompt user for login
- Save new session
- Resume monitoring

### 3. Parsing Errors

**Symptoms:**
- HTML structure changed
- Elements not found
- Invalid data format

**Handling:**
```python
# In FacebookParser._parse_comment_element()
try:
    comment_data = await self._extract_fields(element)
except Exception as e:
    logger.debug(f"Parse failed: {e}")
    return None  # Skip this comment, continue with others
```

**Recovery:**
- Skip problematic element
- Continue parsing other elements
- Log detailed error for debugging
- Partial data still displayed

### 4. Database Errors

**Symptoms:**
- File locked
- Disk full
- Corrupted database

**Handling:**
```python
# In CommentDatabase.save_comments_batch()
try:
    await self.conn.executemany(...)
    await self.conn.commit()
except Exception as e:
    logger.error(f"Database error: {e}")
    await self.conn.rollback()
    # Continue without saving (in-memory cache still works)
```

**Recovery:**
- Rollback transaction
- Log error details
- Continue monitoring (cache in memory)
- User notified of save failure

### 5. Browser Errors

**Symptoms:**
- Browser crashed
- Page unresponsive
- JavaScript error

**Handling:**
```python
# In CommentDetector.refresh_comments()
try:
    await self.scraper.expand_all_comments()
    comments = await self.parser.parse_comments()
except Exception as e:
    logger.error(f"Refresh error: {e}")
    return []  # Return empty, retry on next cycle
```

**Recovery:**
- Return empty result
- Monitoring loop continues
- Browser auto-recovers on next cycle
- User sees temporary gap in data

## Error Propagation

```
Low Level (Scraper/Parser)
    ↓ Log + Return None/False
Mid Level (Detector)
    ↓ Log + Return Empty/Default
High Level (Main App)
    ↓ Display Error + Continue/Retry
User Level (CLI)
    ↓ Show Warning + Suggest Action
```

## Logging Strategy

### Log Levels

**DEBUG**: Detailed parsing steps, element inspection
```python
logger.debug(f"Parsing element with ID: {element_id}")
```

**INFO**: Normal operations, status changes
```python
logger.info("Monitoring started successfully")
```

**WARNING**: Recoverable issues, degraded performance
```python
logger.warning("Session expired, re-login required")
```

**ERROR**: Failed operations, critical issues
```python
logger.error(f"Database connection failed: {e}", exc_info=True)
```

### Log Format

```
2026-08-17 10:30:45 - app.scraper.facebook - ERROR - Failed to navigate to post: TimeoutError
Traceback (most recent call last):
  ...
```

## User Notifications

### CLI Messages

**Error (Red):**
```
❌ Error: Failed to start monitoring
```

**Warning (Yellow):**
```
⚠️  Warning: Session expired, please login again
```

**Info (Cyan):**
```
ℹ️  Info: Retrying connection...
```

**Success (Green):**
```
✅ Success: Session saved successfully
```

## Retry Logic

### Automatic Retry

**Monitor Loop:**
```python
while self.is_running:
    try:
        await self.refresh_comments()
    except Exception as e:
        logger.error(f"Loop error: {e}")
        # Continue to next iteration
    await asyncio.sleep(refresh_interval)
```

**Session Check:**
```python
if not await self.scraper.is_logged_in():
    logger.warning("Session invalid, attempting re-login...")
    if await self.scraper.login():
        logger.info("Re-login successful")
    else:
        raise SessionError("Re-login failed")
```

### Exponential Backoff

For critical failures (not implemented yet, future enhancement):
```python
retry_delay = 1
max_retries = 5

for attempt in range(max_retries):
    try:
        result = await operation()
        break
    except Exception:
        await asyncio.sleep(retry_delay)
        retry_delay *= 2  # Exponential backoff
```

## Graceful Degradation

### Partial Functionality

1. **Database Unavailable**: Continue with in-memory cache only
2. **Network Slow**: Increase timeout, reduce refresh rate
3. **Parse Failures**: Show successfully parsed comments
4. **Session Issues**: Prompt re-login, preserve current data

### User Experience

- **Never crash**: Always handle exceptions
- **Always inform**: Show clear error messages
- **Offer solutions**: Suggest next steps
- **Preserve data**: Save before exit when possible

## Critical Error Handling

### Unrecoverable Errors

```python
try:
    await monitor.run()
except KeyboardInterrupt:
    logger.info("User stopped monitoring")
    await monitor.cleanup()
except Exception as e:
    logger.critical(f"Fatal error: {e}", exc_info=True)
    await monitor.cleanup()
    sys.exit(1)
```

### Cleanup on Exit

```python
async def cleanup(self):
    """Ensure resources are released."""
    try:
        if self.detector:
            self.detector.stop_monitoring()
        if self.scraper:
            await self.scraper.save_session()  # Try to save
            await self.scraper.close()
        if self.database:
            await self.database.close()
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
```

## Testing Error Scenarios

### Manual Tests

1. **Network Disconnection**: Disable WiFi during monitoring
2. **Session Expiration**: Delete cookies in browser
3. **Invalid URL**: Enter malformed Facebook URL
4. **Private Group Access**: Try monitoring without membership
5. **Database Lock**: Open db file in another program

### Expected Behavior

- Errors logged to `logs/app.log`
- User sees clear message in CLI
- Application continues or exits gracefully
- No data loss (saved to database)
- No hanging processes

## Error Recovery Checklist

When error occurs:

1. ✅ **Logged**: Error written to log file with context
2. ✅ **Notified**: User sees message in CLI
3. ✅ **Handled**: Exception caught and processed
4. ✅ **Recovered**: System returns to stable state
5. ✅ **Continued**: Monitoring resumes if possible

## Common Issues & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| Session expired | Cookies invalid | Re-login prompted |
| Parse failure | Facebook UI changed | Log details, skip element |
| Database locked | Multiple instances | Close other instances |
| Network timeout | Poor connection | Auto-retry with longer timeout |
| Access denied | Not group member | Show error, suggest joining |
| Browser crash | Resource exhaustion | Restart browser, continue |

## Future Improvements

1. **Exponential backoff** for retries
2. **Circuit breaker** pattern for repeated failures
3. **Health checks** for all components
4. **Metrics collection** for error rates
5. **Auto-recovery strategies** for common errors
6. **Error reporting** to external service (optional)
