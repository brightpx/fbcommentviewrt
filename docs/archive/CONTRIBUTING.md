# Contributing to Facebook Comment Monitor

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [How to Contribute](#how-to-contribute)
5. [Coding Standards](#coding-standards)
6. [Testing](#testing)
7. [Submitting Changes](#submitting-changes)
8. [Reporting Bugs](#reporting-bugs)
9. [Feature Requests](#feature-requests)

## Code of Conduct

This project follows a simple code of conduct:
- Be respectful and inclusive
- Focus on constructive feedback
- Help maintain a welcoming environment
- Respect differing viewpoints and experiences

## Getting Started

1. **Fork the repository**
2. **Clone your fork**
   ```bash
   git clone https://github.com/yourusername/fbcommentviewrt.git
   cd fbcommentviewrt
   ```
3. **Set up development environment** (see below)

## Development Setup

### Prerequisites
- Python 3.12+
- Git
- Virtual environment tool

### Setup Steps

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

3. **Install Playwright**
   ```bash
   playwright install chromium
   ```

4. **Setup configuration**
   ```bash
   cp config.yaml.example config.yaml
   ```

5. **Run the application**
   ```bash
   python -m app.main
   ```

## How to Contribute

### Types of Contributions

1. **Bug Fixes**
   - Fix existing bugs
   - Improve error handling
   - Resolve edge cases

2. **New Features**
   - Implement new functionality
   - Enhance existing features
   - Add configuration options

3. **Documentation**
   - Improve README and guides
   - Add code comments
   - Write tutorials

4. **Testing**
   - Write unit tests
   - Add integration tests
   - Improve test coverage

5. **Performance**
   - Optimize algorithms
   - Reduce memory usage
   - Improve speed

### Contribution Workflow

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/bug-description
   ```

2. **Make your changes**
   - Write code following standards
   - Add tests for new features
   - Update documentation

3. **Commit your changes**
   ```bash
   git add .
   git commit -m "Brief description of changes"
   ```

4. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Create Pull Request**
   - Go to GitHub
   - Click "New Pull Request"
   - Describe your changes
   - Reference related issues

## Coding Standards

### Python Style Guide

Follow PEP 8 with these specifics:

**Formatting**
- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Use double quotes for strings
- Use type hints for function signatures

**Naming Conventions**
```python
# Classes: PascalCase
class CommentParser:
    pass

# Functions/methods: snake_case
def parse_comment():
    pass

# Constants: UPPER_SNAKE_CASE
MAX_COMMENTS = 10000

# Private methods: _leading_underscore
def _internal_method():
    pass
```

**Imports**
```python
# Standard library
import asyncio
import logging
from pathlib import Path

# Third-party
from rich.console import Console
from playwright.async_api import async_playwright

# Local
from ..models.comment import Comment
from ..database.db import CommentDatabase
```

**Type Hints**
```python
from typing import List, Optional, Dict

def process_comments(
    comments: List[Comment],
    limit: Optional[int] = None
) -> Dict[str, int]:
    """Process comments and return statistics."""
    pass
```

**Docstrings**
```python
def parse_timestamp(text: str) -> datetime:
    """
    Parse relative timestamp from Facebook comment.
    
    Args:
        text: Timestamp string (e.g., "5m", "2h", "1d")
    
    Returns:
        datetime: Parsed timestamp
    
    Raises:
        ValueError: If timestamp format is invalid
    
    Example:
        >>> parse_timestamp("5m")
        datetime(2026, 8, 17, 10, 25, 0)
    """
    pass
```

### Code Organization

**Module Structure**
```
app/
├── models/           # Data models
├── scraper/          # Browser automation
├── monitor/          # Change detection
├── renderer/         # CLI display
└── database/         # Data persistence
```

**File Structure**
```python
"""Module docstring."""

# Imports
import ...

# Constants
CONSTANT = value

# Classes
class MyClass:
    pass

# Functions
def my_function():
    pass

# Main execution
if __name__ == "__main__":
    main()
```

### Error Handling

**Always handle exceptions**
```python
try:
    result = await operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    return default_value
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

**Use logging**
```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Detailed debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_parser.py

# Run specific test
pytest tests/test_parser.py::test_parse_comment
```

### Writing Tests

**Test Structure**
```python
import pytest
from app.scraper.parser import FacebookParser

@pytest.mark.asyncio
async def test_parse_comment():
    """Test comment parsing."""
    # Arrange
    parser = FacebookParser()
    html = "<div>Test comment</div>"
    
    # Act
    result = await parser.parse(html)
    
    # Assert
    assert result is not None
    assert result.message == "Test comment"
```

**Test Coverage Goals**
- Aim for >80% code coverage
- Test happy paths and edge cases
- Test error handling
- Mock external dependencies

## Submitting Changes

### Pull Request Guidelines

**PR Title Format**
```
[Type] Brief description

Types: Feature, Fix, Docs, Test, Refactor, Perf, Style
```

**PR Description Template**
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows project style guide
- [ ] Documentation updated
- [ ] Tests passing
- [ ] No breaking changes (or documented)

## Related Issues
Fixes #123
Related to #456
```

### Review Process

1. **Automated Checks**
   - Code style (flake8, black)
   - Tests (pytest)
   - Coverage (codecov)

2. **Manual Review**
   - Code quality
   - Architecture fit
   - Documentation
   - Test coverage

3. **Feedback**
   - Address review comments
   - Make requested changes
   - Update PR description

4. **Merge**
   - Approved by maintainers
   - All checks passing
   - Conflicts resolved

## Reporting Bugs

### Bug Report Template

```markdown
**Description**
Clear description of the bug

**Steps to Reproduce**
1. Run application
2. Navigate to...
3. Click on...
4. See error

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- OS: Windows 11
- Python: 3.12.0
- Version: 1.0.0

**Logs**
```
Paste relevant log output
```

**Screenshots**
If applicable
```

### Before Submitting

1. Check if bug already reported
2. Verify bug exists in latest version
3. Include reproduction steps
4. Attach logs if available

## Feature Requests

### Feature Request Template

```markdown
**Feature Description**
Clear description of the feature

**Problem It Solves**
What problem does this address?

**Proposed Solution**
How should it work?

**Alternatives Considered**
Other ways to solve this

**Additional Context**
Any other relevant information
```

### Considerations

- Is it aligned with project goals?
- Is it feasible to implement?
- Does it benefit most users?
- Are there workarounds?

## Development Tips

### Debugging

```bash
# Enable debug logging
# In config.yaml
logging:
  level: "DEBUG"

# View logs
tail -f logs/app.log
```

### Performance Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Code to profile
await monitor.refresh_comments()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Common Pitfalls

1. **Async/Await**: Don't forget await on async functions
2. **Resource Cleanup**: Always close connections
3. **Error Handling**: Catch specific exceptions
4. **Logging**: Use appropriate log levels
5. **Type Hints**: Include return types

## Questions?

- Check existing documentation
- Review closed issues
- Ask in discussions
- Contact maintainers

## Thank You!

Your contributions make this project better for everyone. Thank you for taking the time to contribute!
