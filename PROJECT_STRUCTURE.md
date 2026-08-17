# Project Structure

```
fbcommentviewrt/
│
├── app/                           # Main application package
│   ├── __init__.py               # Package initialization
│   ├── __main__.py               # Entry point for python -m app.main
│   ├── main.py                   # Main application logic
│   │
│   ├── models/                   # Data models
│   │   ├── __init__.py
│   │   └── comment.py            # Comment and PostInfo models
│   │
│   ├── scraper/                  # Browser automation and parsing
│   │   ├── __init__.py
│   │   ├── facebook.py           # Playwright-based Facebook scraper
│   │   └── parser.py             # HTML parser for comments
│   │
│   ├── monitor/                  # Change detection and monitoring
│   │   ├── __init__.py
│   │   ├── detector.py           # Comment change detector
│   │   └── cache.py              # In-memory cache for diff detection
│   │
│   ├── renderer/                 # CLI rendering
│   │   ├── __init__.py
│   │   └── cli.py                # Rich-based CLI renderer
│   │
│   └── database/                 # Data persistence
│       ├── __init__.py
│       ├── db.py                 # SQLite database operations
│       └── schema.sql            # Database schema
│
├── session/                      # Session storage (created at runtime)
│   └── fb_session.json           # Facebook session cookies (gitignored)
│
├── database/                     # SQLite database files (created at runtime)
│   └── comments.db               # Comment storage (gitignored)
│
├── logs/                         # Application logs (created at runtime)
│   └── app.log                   # Main log file (gitignored)
│
├── config.yaml.example           # Configuration template
├── config.yaml                   # User configuration (gitignored)
├── requirements.txt              # Python dependencies
├── requirements_parser.txt       # Parser-specific dependencies
│
├── run.py                        # Run script (cross-platform)
├── run.bat                       # Windows run script
├── run.sh                        # Linux/Mac run script
├── install.bat                   # Windows installer
├── install.sh                    # Linux/Mac installer
│
├── README.md                     # Main documentation
├── QUICKSTART.md                 # Quick start guide
├── BUILD.md                      # Build instructions
├── ERROR_HANDLING.md             # Error handling strategy
├── SESSION_RECOVERY.md           # Session management details
├── CONTRIBUTING.md               # Contribution guidelines
├── CHANGELOG.md                  # Version history
├── LICENSE                       # MIT license
│
└── .gitignore                    # Git ignore rules
```

## Directory Details

### `/app` - Main Application

Core application code organized by responsibility:

- **models/**: Pure data structures (Comment, PostInfo)
- **scraper/**: Browser automation and HTML parsing
- **monitor/**: Change detection and monitoring loop
- **renderer/**: CLI display and user interaction
- **database/**: SQLite operations and schema

### `/session` - Session Storage

Contains Facebook session cookies for automatic login.

**Files:**
- `fb_session.json`: Playwright storage state (cookies, local storage)

**Security:**
- Gitignored
- Contains sensitive authentication tokens
- Should be kept private

### `/database` - Data Storage

SQLite database files for persistent comment storage.

**Files:**
- `comments.db`: Main database with comments, posts, sessions

**Tables:**
- `comments`: Comment data with hierarchy
- `posts`: Post metadata
- `sessions`: Session tracking

### `/logs` - Application Logs

Log files for debugging and monitoring.

**Files:**
- `app.log`: Main application log with rotation

**Configuration:**
- Log level: INFO (default)
- Max size: 10 MB
- Backup count: 5

## File Descriptions

### Core Python Files

**`app/main.py`**
- Main application class
- Component initialization
- Monitoring lifecycle management
- Error handling and cleanup

**`app/models/comment.py`**
- Comment data model
- PostInfo data model
- Tree structure utilities
- Serialization methods

**`app/scraper/facebook.py`**
- Playwright browser automation
- Session management
- Page navigation
- Comment expansion

**`app/scraper/parser.py`**
- HTML parsing with BeautifulSoup
- Comment extraction
- Hierarchy detection
- Timestamp parsing

**`app/monitor/detector.py`**
- Real-time monitoring loop
- Change detection
- Event callbacks
- Statistics tracking

**`app/monitor/cache.py`**
- In-memory comment cache
- Diff detection
- Update tracking

**`app/renderer/cli.py`**
- Rich-based CLI rendering
- Tree view display
- Color-coded tiers
- Notifications

**`app/database/db.py`**
- SQLite operations
- CRUD operations
- Batch inserts
- Statistics queries

### Configuration Files

**`config.yaml.example`**
- Template configuration
- All available settings
- Default values
- Comments explaining each option

**`config.yaml`** (created from example)
- User's active configuration
- Overrides defaults
- Gitignored

### Documentation Files

**`README.md`**
- Main project documentation
- Features overview
- Installation instructions
- Usage guide
- Troubleshooting

**`QUICKSTART.md`**
- Fast-start guide
- Common commands
- Quick tips
- Essential information

**`BUILD.md`**
- Build instructions
- PyInstaller setup
- Docker configuration
- Distribution packaging

**`ERROR_HANDLING.md`**
- Error handling strategy
- Recovery mechanisms
- Common issues
- Troubleshooting guide

**`SESSION_RECOVERY.md`**
- Session lifecycle
- Recovery scenarios
- Security considerations
- Configuration options

**`CONTRIBUTING.md`**
- Contribution guidelines
- Code style guide
- Testing requirements
- PR process

**`CHANGELOG.md`**
- Version history
- Release notes
- Breaking changes
- Future roadmap

**`LICENSE`**
- MIT license text
- Third-party licenses
- Disclaimer

### Scripts

**`run.py`**
- Cross-platform run script
- Python entry point
- Error handling

**`run.bat`** (Windows)
- Batch script to run application
- Activates venv
- Launches main.py

**`run.sh`** (Linux/Mac)
- Bash script to run application
- Activates venv
- Launches main.py

**`install.bat`** (Windows)
- Windows installation script
- Creates venv
- Installs dependencies
- Sets up Playwright

**`install.sh`** (Linux/Mac)
- Unix installation script
- Creates venv
- Installs dependencies
- Sets up Playwright

### Dependencies

**`requirements.txt`**
```
playwright==1.48.0      # Browser automation
rich==13.9.4            # CLI rendering
pyyaml==6.0.2           # Configuration parsing
python-dateutil==2.9.0  # Date/time utilities
aiosqlite==0.20.0       # Async SQLite
beautifulsoup4==4.12.3  # HTML parsing
```

## Data Flow

```
User Input
    ↓
CLI Renderer (app/renderer/cli.py)
    ↓
Main App (app/main.py)
    ↓
Monitor Detector (app/monitor/detector.py)
    ↓
Facebook Scraper (app/scraper/facebook.py)
    ↓
Facebook Parser (app/scraper/parser.py)
    ↓
Comment Cache (app/monitor/cache.py)
    ↓
Database (app/database/db.py)
    ↓
CLI Renderer (display update)
```

## Module Dependencies

```
main.py
  ├─ scraper/facebook.py
  │    └─ playwright
  ├─ scraper/parser.py
  │    └─ beautifulsoup4
  ├─ monitor/detector.py
  │    ├─ scraper/facebook.py
  │    ├─ scraper/parser.py
  │    └─ monitor/cache.py
  ├─ renderer/cli.py
  │    └─ rich
  └─ database/db.py
       └─ aiosqlite
```

## Configuration Hierarchy

```
config.yaml.example (template)
    ↓ copy to
config.yaml (user settings)
    ↓ loaded by
main.py (runtime config)
    ↓ passed to
Components (scraper, monitor, renderer, database)
```

## Session Flow

```
First Run:
  No session file
  → Open browser
  → User logs in
  → Save to session/fb_session.json

Subsequent Runs:
  Load session/fb_session.json
  → Validate session
  → If valid: Continue
  → If invalid: Re-login
```

## Database Schema

```sql
comments
  ├─ id (TEXT, PRIMARY KEY)
  ├─ parent_id (TEXT, FOREIGN KEY)
  ├─ tier (INTEGER)
  ├─ author (TEXT)
  ├─ message (TEXT)
  ├─ created_time (TIMESTAMP)
  ├─ last_seen (TIMESTAMP)
  ├─ is_deleted (BOOLEAN)
  └─ post_url (TEXT)

posts
  ├─ url (TEXT, PRIMARY KEY)
  ├─ group_name (TEXT)
  ├─ post_id (TEXT)
  ├─ author (TEXT)
  ├─ content (TEXT)
  ├─ first_seen (TIMESTAMP)
  └─ last_monitored (TIMESTAMP)

sessions
  ├─ id (INTEGER, PRIMARY KEY)
  ├─ created_at (TIMESTAMP)
  ├─ expires_at (TIMESTAMP)
  └─ is_active (BOOLEAN)
```

## Entry Points

1. **Main entry**: `python -m app.main`
2. **Direct run**: `python run.py`
3. **Windows**: `run.bat`
4. **Unix**: `./run.sh`
5. **Module**: `python -m app`

All entry points lead to `app/main.py:main()`

## Import Structure

```python
# Absolute imports from app root
from app.models.comment import Comment
from app.scraper.facebook import FacebookScraper
from app.database.db import CommentDatabase

# Relative imports within package
from ..models.comment import Comment
from .parser import FacebookParser
```

## Testing Structure (Future)

```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_parser.py
│   ├── test_cache.py
│   └── test_renderer.py
├── integration/
│   ├── test_scraper.py
│   ├── test_monitor.py
│   └── test_database.py
└── e2e/
    └── test_full_flow.py
```

## Build Artifacts

```
dist/                           # Built executables
├── fbcommentmonitor.exe       # Windows executable
├── fbcommentmonitor           # Linux/Mac executable
└── fbcommentmonitor.app       # macOS app bundle

build/                         # Build cache
└── (temporary files)

*.spec                         # PyInstaller spec files
```
