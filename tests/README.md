# Test Suite Documentation

## 📋 Overview

Test suite ครอบคลุมทุก component ของ Facebook Comment Monitor พร้อม debug configuration

## 🧪 Test Files

### Unit Tests

| File | Description | Coverage |
|------|-------------|----------|
| `test_models.py` | Test Comment & PostInfo models | Data structures, tree operations |
| `test_cache.py` | Test CommentCache | Change detection, statistics |
| `test_database.py` | Test CommentDatabase | CRUD operations, persistence |
| `test_parser.py` | Test FacebookParser | HTML parsing, time parsing |

### Integration Tests

| File | Description | Coverage |
|------|-------------|----------|
| `test_integration.py` | End-to-end workflows | Cache + DB, multiple posts |

### Fixtures

| File | Description |
|------|-------------|
| `conftest.py` | Shared fixtures and configuration |

## 🚀 Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_models.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_models.py::TestComment -v
```

### Run Specific Test Function
```bash
pytest tests/test_models.py::TestComment::test_comment_creation -v
```

### Run with Coverage
```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term
```

### Run Integration Tests Only
```bash
pytest tests/ -v -m integration
```

### Run Unit Tests Only
```bash
pytest tests/ -v -m unit
```

### Run with Output
```bash
pytest tests/ -v -s
```

### Run Failed Tests Only
```bash
pytest tests/ --lf
```

### Run Specific Pattern
```bash
pytest tests/ -k "test_comment" -v
```

## 🐛 Debugging Tests

### VS Code Debug Configurations

#### 1. Debug All Tests
- Press `F5`
- Select: **Python: All Tests**
- Breakpoints will work in test files

#### 2. Debug Current Test File
- Open test file
- Press `F5`
- Select: **Python: Test Current File**

#### 3. Debug Single Test
- Highlight test name
- Press `F5`
- Select: **Python: Debug Single Test**

#### 4. Debug Specific Component
- Select: **Python: Debug Facebook Scraper**
- Or: **Python: Debug Parser**

#### 5. Debug Main Application
- Select: **Python: Main Application**
- Debug full application flow

### Command Line Debugging

```bash
# Run with pdb on failure
pytest tests/ --pdb

# Drop into pdb on first failure
pytest tests/ -x --pdb

# Show local variables on failure
pytest tests/ -l

# Verbose output
pytest tests/ -vv
```

## 📊 Test Coverage

### Generate HTML Coverage Report
```bash
pytest tests/ --cov=app --cov-report=html
```

Then open: `htmlcov/index.html`

### Show Missing Lines
```bash
pytest tests/ --cov=app --cov-report=term-missing
```

## 🔧 Test Configuration

### pytest.ini
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    asyncio: async tests
    slow: slow running tests
    integration: integration tests
    unit: unit tests
```

## 📝 Writing New Tests

### Basic Test Structure

```python
import pytest
from app.models.comment import Comment

class TestYourFeature:
    """Test your feature"""
    
    def test_basic_functionality(self):
        """Test basic case"""
        # Arrange
        comment = Comment(...)
        
        # Act
        result = comment.some_method()
        
        # Assert
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_async_functionality(self):
        """Test async case"""
        result = await some_async_function()
        assert result is not None
```

### Using Fixtures

```python
def test_with_fixture(sample_comment):
    """Use fixture from conftest.py"""
    assert sample_comment.id == "123456"
```

### Mocking

```python
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_with_mock(mock_playwright_page):
    """Use mock objects"""
    mock_playwright_page.goto = AsyncMock()
    await mock_playwright_page.goto("https://facebook.com")
    mock_playwright_page.goto.assert_called_once()
```

## 🎯 Test Markers

### Mark Tests

```python
@pytest.mark.slow
def test_slow_operation():
    """Slow test"""
    pass

@pytest.mark.integration
def test_integration():
    """Integration test"""
    pass

@pytest.mark.asyncio
async def test_async():
    """Async test"""
    pass
```

### Run Marked Tests

```bash
pytest -m slow          # Run slow tests only
pytest -m "not slow"    # Skip slow tests
pytest -m integration   # Run integration tests
```

## 📦 Test Dependencies

Required packages:
```txt
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
```

Install:
```bash
pip install pytest pytest-asyncio pytest-cov pytest-mock
```

## 🔍 Debugging Tips

### 1. Print Debugging
```python
def test_with_print(capsys):
    print("Debug message")
    result = some_function()
    captured = capsys.readouterr()
    assert "Debug" in captured.out
```

### 2. Breakpoint
```python
def test_with_breakpoint():
    result = some_function()
    breakpoint()  # Drops into pdb
    assert result is not None
```

### 3. Logging
```python
import logging

def test_with_logging(caplog):
    with caplog.at_level(logging.INFO):
        some_function()
    assert "Expected message" in caplog.text
```

### 4. Temporary Files
```python
def test_with_temp_file(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("content")
    assert file.read_text() == "content"
```

## 📈 CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run tests
  run: |
    pytest tests/ --cov=app --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## 🎓 Best Practices

1. ✅ **One assertion per test** (when possible)
2. ✅ **Use descriptive test names** (test_should_do_something_when_condition)
3. ✅ **Arrange-Act-Assert** pattern
4. ✅ **Mock external dependencies**
5. ✅ **Clean up resources** (use fixtures with cleanup)
6. ✅ **Test edge cases** (empty, null, boundary values)
7. ✅ **Keep tests fast** (mock slow operations)
8. ✅ **Independent tests** (no test should depend on another)

## 🐛 Common Issues

### Issue: Async tests not running
**Solution:** Add `@pytest.mark.asyncio` decorator

### Issue: Fixtures not found
**Solution:** Check `conftest.py` is in the right directory

### Issue: Import errors
**Solution:** Set `PYTHONPATH`:
```bash
export PYTHONPATH="${PYTHONPATH}:${PWD}"  # Linux/Mac
$env:PYTHONPATH="$PWD"                     # Windows PowerShell
```

### Issue: Database locked
**Solution:** Use separate test database:
```python
db = CommentDatabase(str(temp_dir / "test.db"))
```

## 📞 Support

- 📖 Read pytest docs: https://docs.pytest.org/
- 🔍 Check test output carefully
- 💬 Use `-vv` for verbose output
- 🐛 Use `--pdb` for debugging

---

Happy Testing! 🎉
