# Session Recovery Strategy

## Overview

The Facebook Comment Monitor uses persistent session management to avoid repeated logins. This document describes the session lifecycle and recovery mechanisms.

## Session Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│                    First Run                             │
│  1. No session file exists                               │
│  2. Browser opens to Facebook login                      │
│  3. User logs in manually                                │
│  4. Session saved to fb_session.json                     │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                 Subsequent Runs                          │
│  1. Load session from fb_session.json                    │
│  2. Validate session (check if still logged in)          │
│  3. If valid: Continue                                   │
│  4. If invalid: Trigger recovery                         │
└─────────────────────────────────────────────────────────┘
```

## Session Storage Format

### File: `session/fb_session.json`

```json
{
  "cookies": [
    {
      "name": "c_user",
      "value": "...",
      "domain": ".facebook.com",
      "path": "/",
      "expires": 1735689600,
      "httpOnly": true,
      "secure": true,
      "sameSite": "None"
    },
    {
      "name": "xs",
      "value": "...",
      "domain": ".facebook.com",
      "path": "/",
      "httpOnly": true,
      "secure": true,
      "sameSite": "None"
    }
  ],
  "origins": [
    {
      "origin": "https://www.facebook.com",
      "localStorage": []
    }
  ]
}
```

### Key Session Cookies

- **c_user**: User ID cookie (required)
- **xs**: Session cookie (required)
- **fr**: Request tracking cookie
- **datr**: Device authentication token

## Session Validation

### Validation Process

```python
async def is_logged_in(self) -> bool:
    """Check if user is logged in."""
    try:
        # Navigate to Facebook home
        await self.page.goto("https://www.facebook.com", 
                            wait_until="domcontentloaded", 
                            timeout=10000)
        
        # Wait for page to load
        await self.page.wait_for_timeout(2000)
        
        # Check for logged-in indicators
        is_logged_in = await self.page.evaluate("""
            () => {
                // Look for elements that only appear when logged in
                return document.querySelector('[data-visualcompletion="ignore-dynamic"]') !== null ||
                       document.querySelector('[aria-label="Account"]') !== null ||
                       document.querySelector('[aria-label="บัญชี"]') !== null;
            }
        """)
        
        return is_logged_in
        
    except Exception as e:
        logger.error(f"Error checking login status: {e}")
        return False
```

### Validation Triggers

1. **Application Start**: First action after browser initialization
2. **Session Load**: After loading session from file
3. **Navigation Failure**: When page access is denied
4. **Periodic Check**: Optional (every 5 minutes)

## Recovery Scenarios

### Scenario 1: No Session File

**Condition**: `session/fb_session.json` doesn't exist

**Recovery**:
```python
if not Path(self.session_file).exists():
    logger.info("No session file found, login required")
    await self._create_new_context()
    await self.login()  # Opens browser for manual login
```

**User Experience**:
```
ℹ️  Info: No saved session found
ℹ️  Info: Please login in the browser window...
[Browser opens]
[User logs in]
✅ Success: Login successful
✅ Success: Session saved
```

### Scenario 2: Corrupted Session File

**Condition**: JSON parse error or invalid format

**Recovery**:
```python
try:
    with open(self.session_file, 'r') as f:
        session_data = json.load(f)
    await self._load_session_from_data(session_data)
except (json.JSONDecodeError, KeyError) as e:
    logger.warning(f"Corrupted session file: {e}")
    Path(self.session_file).unlink()  # Delete corrupted file
    await self._create_new_context()
    await self.login()
```

**User Experience**:
```
⚠️  Warning: Session file corrupted
ℹ️  Info: Re-login required
[Browser opens for login]
```

### Scenario 3: Expired Session

**Condition**: Session cookies expired (validation fails)

**Recovery**:
```python
is_valid = await self.is_logged_in()
if not is_valid:
    logger.warning("Session expired")
    # Try to login again
    if await self.login():
        logger.info("Re-login successful")
        await self.save_session()
    else:
        raise SessionError("Failed to re-login")
```

**User Experience**:
```
⚠️  Warning: Session expired
ℹ️  Info: Please login again in the browser window...
[Browser shows login page]
[User logs in]
✅ Success: Session restored
```

### Scenario 4: Facebook Security Challenge

**Condition**: Facebook detects unusual activity, requires verification

**Recovery**:
```python
# Check for security checkpoint
checkpoint = await self.page.query_selector('[data-testid="checkpoint"]')
if checkpoint:
    logger.warning("Facebook security checkpoint detected")
    # User must complete verification manually
    await self.page.wait_for_selector('[data-visualcompletion="ignore-dynamic"]', 
                                       timeout=300000)  # 5 minutes
    await self.save_session()
```

**User Experience**:
```
⚠️  Warning: Facebook security verification required
ℹ️  Info: Please complete verification in the browser...
[User completes 2FA/verification]
✅ Success: Verification complete
```

### Scenario 5: Account Locked/Disabled

**Condition**: Facebook account is locked or disabled

**Recovery**:
```python
# Check for account status warnings
locked = await self.page.query_selector('text="Your account has been locked"')
if locked:
    logger.error("Facebook account locked")
    raise AccountError("Account locked - please resolve on facebook.com")
```

**User Experience**:
```
❌ Error: Your Facebook account is locked
ℹ️  Info: Please visit facebook.com to resolve this issue
[Application exits]
```

## Session Persistence

### Auto-Save

Session is automatically saved after:

1. **Successful Login**: After manual login completes
2. **Successful Verification**: After security challenge
3. **Periodic Saves**: Every 30 minutes (optional)
4. **Application Exit**: During cleanup

```python
async def save_session(self) -> None:
    """Save current session to file."""
    if self.context:
        Path(self.session_file).parent.mkdir(parents=True, exist_ok=True)
        session_data = await self.context.storage_state()
        with open(self.session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        logger.info(f"Session saved to {self.session_file}")
```

### Manual Save

User can manually save session:
```bash
# During monitoring, press 'S' to save session
[Feature not yet implemented]
```

## Session Security

### Best Practices

1. **File Permissions**: Session file should be readable only by user
   ```python
   import os
   os.chmod(self.session_file, 0o600)  # Read/write for owner only
   ```

2. **Encryption**: Session file can be encrypted (future enhancement)
   ```python
   # Encrypt with user password
   encrypted_data = encrypt(session_data, user_password)
   ```

3. **Expiration Check**: Validate cookie expiration times
   ```python
   def is_cookie_expired(cookie: dict) -> bool:
       if 'expires' in cookie:
           return cookie['expires'] < time.time()
       return False
   ```

4. **Git Ignore**: Never commit session file
   ```gitignore
   session/fb_session.json
   ```

### Security Checklist

- ✅ Session file in `.gitignore`
- ✅ File permissions restricted
- ✅ No session data in logs
- ✅ Auto-cleanup on uninstall
- ⏳ Optional encryption (future)
- ⏳ Session timeout enforcement (future)

## Troubleshooting

### Session Not Persisting

**Symptoms**: Must login every time

**Diagnosis**:
```bash
# Check if session file is created
ls -la session/fb_session.json

# Check file contents
cat session/fb_session.json
```

**Solutions**:
1. Verify write permissions on `session/` directory
2. Check disk space
3. Review logs for save errors

### Session Expired Too Quickly

**Symptoms**: Session expires within hours

**Causes**:
1. Facebook security settings
2. Using VPN/proxy
3. Multiple device logins
4. Suspicious activity detected

**Solutions**:
1. Use consistent IP address
2. Reduce refresh rate
3. Complete Facebook security verification
4. Use dedicated account for monitoring

### Cannot Login

**Symptoms**: Login page doesn't load or login fails

**Diagnosis**:
```bash
# Check browser installation
playwright install chromium

# Check network connectivity
ping facebook.com
```

**Solutions**:
1. Update Playwright: `pip install -U playwright`
2. Reinstall browser: `playwright install --force chromium`
3. Check firewall/antivirus settings
4. Try different network

## Configuration Options

### Session Settings in `config.yaml`

```yaml
session:
  file: "session/fb_session.json"  # Session file path
  auto_save: true                   # Auto-save on changes
  check_interval: 300               # Validation interval (seconds)
  max_age: 604800                   # Max session age (7 days)
```

## Advanced Recovery

### Multi-Account Support (Future)

```python
# Switch between multiple accounts
sessions = {
    'account1': 'session/account1.json',
    'account2': 'session/account2.json'
}

active_account = 'account1'
scraper.load_session(sessions[active_account])
```

### Automatic Failover (Future)

```python
# If primary session fails, try backup account
for account in backup_accounts:
    try:
        if await login_with_account(account):
            logger.info(f"Failover to {account} successful")
            break
    except Exception:
        continue
```

## Summary

The session recovery strategy ensures:

1. ✅ **Persistence**: Login once, reuse many times
2. ✅ **Validation**: Check session validity before use
3. ✅ **Recovery**: Automatic recovery from common failures
4. ✅ **Security**: Protected session storage
5. ✅ **User-Friendly**: Clear messages and guided recovery

Session recovery is fully automatic in most cases, requiring user intervention only for:
- Initial login (first run)
- Session expiration (re-login)
- Security verification (2FA/checkpoint)
- Account issues (locked/disabled)
