# Build Instructions

## Development Build

### Prerequisites

- Python 3.12 or higher
- pip (Python package manager)
- Git (optional, for version control)

### Setup Development Environment

1. **Clone/Download Project**
   ```bash
   cd fbcommentviewrt
   ```

2. **Create Virtual Environment (Recommended)**
   
   **Windows:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
   
   **Linux/Mac:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright Browsers**
   ```bash
   playwright install chromium
   ```

5. **Setup Configuration**
   ```bash
   # Windows
   copy config.yaml.example config.yaml
   
   # Linux/Mac
   cp config.yaml.example config.yaml
   ```

6. **Run Development Version**
   ```bash
   python -m app.main
   ```

## Production Build

### Option 1: Standalone Executable (PyInstaller)

1. **Install PyInstaller**
   ```bash
   pip install pyinstaller
   ```

2. **Create Executable**
   
   **Windows:**
   ```bash
   pyinstaller --name fbcommentmonitor ^
               --onefile ^
               --windowed ^
               --add-data "config.yaml.example;." ^
               --add-data "app/database/schema.sql;app/database" ^
               --hidden-import playwright ^
               --hidden-import rich ^
               --hidden-import aiosqlite ^
               run.py
   ```
   
   **Linux/Mac:**
   ```bash
   pyinstaller --name fbcommentmonitor \
               --onefile \
               --windowed \
               --add-data "config.yaml.example:." \
               --add-data "app/database/schema.sql:app/database" \
               --hidden-import playwright \
               --hidden-import rich \
               --hidden-import aiosqlite \
               run.py
   ```

3. **Output**
   - Executable: `dist/fbcommentmonitor.exe` (Windows) or `dist/fbcommentmonitor` (Linux/Mac)
   - Size: ~50-100 MB (includes Python runtime)

4. **Post-Build Setup**
   ```bash
   # Copy to deployment directory
   mkdir deployment
   cp dist/fbcommentmonitor deployment/
   cp config.yaml.example deployment/
   
   # Install Playwright browsers in deployment
   cd deployment
   playwright install chromium
   ```

### Option 2: Python Package (Wheel)

1. **Install Build Tools**
   ```bash
   pip install build wheel
   ```

2. **Create setup.py**
   ```python
   from setuptools import setup, find_packages
   
   setup(
       name="fbcommentmonitor",
       version="1.0.0",
       packages=find_packages(),
       install_requires=[
           'playwright>=1.48.0',
           'rich>=13.9.4',
           'pyyaml>=6.0.2',
           'python-dateutil>=2.9.0',
           'aiosqlite>=0.20.0',
       ],
       entry_points={
           'console_scripts': [
               'fbcommentmonitor=app.main:main',
           ],
       },
       python_requires='>=3.12',
   )
   ```

3. **Build Package**
   ```bash
   python -m build
   ```

4. **Output**
   - Wheel: `dist/fbcommentmonitor-1.0.0-py3-none-any.whl`
   - Source: `dist/fbcommentmonitor-1.0.0.tar.gz`

5. **Install Package**
   ```bash
   pip install dist/fbcommentmonitor-1.0.0-py3-none-any.whl
   playwright install chromium
   ```

6. **Run Installed Package**
   ```bash
   fbcommentmonitor
   ```

### Option 3: Docker Container

1. **Create Dockerfile**
   ```dockerfile
   FROM python:3.12-slim
   
   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       wget \
       gnupg \
       && rm -rf /var/lib/apt/lists/*
   
   # Set working directory
   WORKDIR /app
   
   # Copy application files
   COPY requirements.txt .
   COPY app/ ./app/
   COPY config.yaml.example ./config.yaml
   COPY run.py .
   
   # Install Python dependencies
   RUN pip install --no-cache-dir -r requirements.txt
   
   # Install Playwright browsers
   RUN playwright install chromium
   RUN playwright install-deps chromium
   
   # Create directories
   RUN mkdir -p session database logs
   
   # Run application
   CMD ["python", "-m", "app.main"]
   ```

2. **Create docker-compose.yml**
   ```yaml
   version: '3.8'
   
   services:
     fbcommentmonitor:
       build: .
       container_name: fbcommentmonitor
       volumes:
         - ./session:/app/session
         - ./database:/app/database
         - ./logs:/app/logs
         - ./config.yaml:/app/config.yaml
       environment:
         - DISPLAY=:99
       restart: unless-stopped
   ```

3. **Build Docker Image**
   ```bash
   docker build -t fbcommentmonitor:1.0.0 .
   ```

4. **Run Container**
   ```bash
   docker-compose up -d
   ```

5. **View Logs**
   ```bash
   docker logs -f fbcommentmonitor
   ```

## Distribution Package

### Create Distribution Package

1. **Create Distribution Structure**
   ```
   fbcommentmonitor-1.0.0/
   ├── fbcommentmonitor.exe (or binary)
   ├── config.yaml.example
   ├── README.md
   ├── QUICKSTART.md
   ├── LICENSE
   └── data/
       └── playwright/ (browsers)
   ```

2. **Bundle Script (Windows)**
   ```powershell
   # Create distribution folder
   $version = "1.0.0"
   $distDir = "fbcommentmonitor-$version"
   
   New-Item -ItemType Directory -Force -Path $distDir
   
   # Copy executable
   Copy-Item "dist/fbcommentmonitor.exe" "$distDir/"
   
   # Copy documentation
   Copy-Item "README.md" "$distDir/"
   Copy-Item "QUICKSTART.md" "$distDir/"
   Copy-Item "config.yaml.example" "$distDir/"
   
   # Create directories
   New-Item -ItemType Directory -Force -Path "$distDir/session"
   New-Item -ItemType Directory -Force -Path "$distDir/database"
   New-Item -ItemType Directory -Force -Path "$distDir/logs"
   
   # Create archive
   Compress-Archive -Path $distDir -DestinationPath "$distDir.zip"
   ```

3. **Bundle Script (Linux/Mac)**
   ```bash
   #!/bin/bash
   
   VERSION="1.0.0"
   DIST_DIR="fbcommentmonitor-$VERSION"
   
   # Create distribution folder
   mkdir -p "$DIST_DIR"
   
   # Copy executable
   cp dist/fbcommentmonitor "$DIST_DIR/"
   chmod +x "$DIST_DIR/fbcommentmonitor"
   
   # Copy documentation
   cp README.md "$DIST_DIR/"
   cp QUICKSTART.md "$DIST_DIR/"
   cp config.yaml.example "$DIST_DIR/"
   
   # Create directories
   mkdir -p "$DIST_DIR/session"
   mkdir -p "$DIST_DIR/database"
   mkdir -p "$DIST_DIR/logs"
   
   # Create archive
   tar -czf "$DIST_DIR.tar.gz" "$DIST_DIR"
   ```

## Testing Build

### Test Checklist

Before distribution, verify:

1. **Functionality**
   - [ ] Application starts without errors
   - [ ] Login flow works
   - [ ] Session persists across runs
   - [ ] Comments are detected
   - [ ] Display renders correctly
   - [ ] Database saves data
   - [ ] Cleanup on exit works

2. **Dependencies**
   - [ ] All required libraries included
   - [ ] Playwright browsers installed
   - [ ] Configuration file present

3. **Cross-Platform**
   - [ ] Windows 10/11 compatibility
   - [ ] Linux (Ubuntu 20.04+) compatibility
   - [ ] macOS (10.15+) compatibility

4. **Performance**
   - [ ] Memory usage < 500MB
   - [ ] CPU usage < 10% idle
   - [ ] Startup time < 10 seconds
   - [ ] Handles 10,000+ comments

### Manual Test Script

```bash
# 1. Clean install test
rm -rf session/ database/ logs/
python -m app.main

# 2. Login test
# - Verify browser opens
# - Login with Facebook
# - Verify session saves

# 3. Monitoring test
# - Enter valid post URL
# - Verify comments display
# - Wait for new comment
# - Verify NEW badge appears

# 4. Persistence test
# - Stop monitoring (Ctrl+C)
# - Restart application
# - Verify session reused (no login)

# 5. Error handling test
# - Enter invalid URL
# - Verify error message
# - Disconnect network
# - Verify recovery message
```

## Optimization

### Reduce Build Size

1. **Exclude Unnecessary Files**
   ```bash
   # In PyInstaller spec file
   excludes=['tkinter', 'matplotlib', 'scipy', 'numpy']
   ```

2. **Use UPX Compression**
   ```bash
   pip install upx
   pyinstaller --upx-dir=/usr/bin/upx ...
   ```

3. **Strip Debug Symbols**
   ```bash
   strip dist/fbcommentmonitor  # Linux/Mac
   ```

### Improve Performance

1. **Use Compiled Code**
   ```bash
   # Compile Python files
   python -m compileall app/
   ```

2. **Optimize Database**
   ```sql
   -- In schema.sql
   PRAGMA journal_mode = WAL;
   PRAGMA synchronous = NORMAL;
   PRAGMA cache_size = 10000;
   ```

3. **Configure Browser**
   ```yaml
   # In config.yaml
   browser:
     headless: true          # Faster without GUI
     slow_mo: 0              # No artificial delays
     timeout: 15000          # Shorter timeout
   ```

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Build

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.12']
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        playwright install chromium
    
    - name: Run tests
      run: |
        python -m pytest tests/
    
    - name: Build executable
      run: |
        pip install pyinstaller
        pyinstaller --onefile run.py
    
    - name: Upload artifact
      uses: actions/upload-artifact@v3
      with:
        name: fbcommentmonitor-${{ matrix.os }}
        path: dist/
```

## Version Management

### Semantic Versioning

Format: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### Version Update Checklist

1. Update `app/__init__.py`:
   ```python
   __version__ = "1.1.0"
   ```

2. Update `README.md`: Add to changelog

3. Tag release:
   ```bash
   git tag -a v1.1.0 -m "Release version 1.1.0"
   git push origin v1.1.0
   ```

4. Build distribution package

5. Create GitHub release with binaries

## Troubleshooting Build Issues

### "Module not found" during build

**Solution**: Add missing imports to PyInstaller spec
```bash
--hidden-import missing_module
```

### Executable won't run

**Solution**: Check for missing DLLs
```bash
# Windows
depends.exe fbcommentmonitor.exe

# Linux
ldd fbcommentmonitor
```

### Large executable size

**Solution**: Use UPX compression and exclude unnecessary modules

### Browser not found in executable

**Solution**: Bundle Playwright browsers or install post-deployment

## Deployment Checklist

- [ ] Version number updated
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Configuration example included
- [ ] Build for all platforms
- [ ] Test on clean systems
- [ ] Create release notes
- [ ] Upload to distribution platform
- [ ] Update website/repository
