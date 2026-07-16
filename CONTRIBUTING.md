# MINXG Contributing Guide

Thank you for your interest in contributing to MINXG!

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Code Style](#code-style)
4. [Testing](#testing)
5. [Submitting Changes](#submitting-changes)
6. [Code of Conduct](#code-of-conduct)

## Getting Started

### Prerequisites

- Python 3.8+
- Git
- pip

### Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/MINXG-Beta.git
cd MINXG-Beta
pip install -e ".[dev]"
```

## Development Setup

### Install Development Dependencies

```bash
pip install pytest pytest-asyncio pytest-cov ruff mypy
```

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=minxg --cov=multiligua_cli --cov-report=html

# Run specific test file
pytest tests/test_workers.py -v
```

### Lint Code

```bash
# Check with ruff
ruff check minxg/ multiligua_cli/ tests/

# Format with ruff
ruff format minxg/ multiligua_cli/ tests/
```

## Code Style

### General Guidelines

- Follow PEP 8 style guide
- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep functions small and focused
- Use meaningful variable names

### Type Hints

```python
from typing import Dict, List, Optional, Any

def process_data(
    data: List[Dict[str, Any]],
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Process data with optional limit.

    Args:
        data: List of dictionaries to process.
        limit: Maximum number of items to return.

    Returns:
        Dictionary with processed results.
    """
    if limit:
        data = data[:limit]
    return {"processed": data, "count": len(data)}
```

### Worker Structure

```python
from typing import Dict, Any

class MyWorker:
    """Description of the worker."""

    worker_id = "my_worker"
    version = "0.19.0"
    tier = "code"  # or "math", "text", etc.

    def __init__(self):
        self.tools = {}
        self._register_tools()

    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the worker.

        Returns:
            Dictionary with status and results.
        """
        try:
            # Your implementation here
            return {"status": "ok", "result": "value"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _register_tools(self):
        """Register tools for the worker."""
        self.tools = {
            "my_tool": {"description": "What this tool does", "category": "category_name"},
        }
```

### Error Handling

Always return a dictionary with either `status: "ok"` or `status: "error"`:

```python
def execute(self, path: str) -> Dict[str, Any]:
    try:
        result = do_something(path)
        return {"status": "ok", "result": result}
    except FileNotFoundError:
        return {"status": "error", "error": f"File not found: {path}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

## Testing

### Writing Tests

Place tests in `tests/` directory. Use descriptive names:

```python
import pytest

def test_my_worker_basic():
    """Test basic functionality."""
    from minxg.workers.my_module import MyWorker

    worker = MyWorker()
    result = worker.execute(input="test")

    assert result["status"] == "ok"
    assert "result" in result

def test_my_worker_error():
    """Test error handling."""
    from minxg.workers.my_module import MyWorker

    worker = MyWorker()
    result = worker.execute(input=None)

    assert result["status"] == "error"
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_my_module.py::test_my_worker_basic -v

# Run with coverage
pytest tests/ --cov=minxg --cov-report=html
```

## Submitting Changes

### Pull Request Process

1. Create a branch from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make your changes and commit:
   ```bash
   git add .
   git commit -m "feat: add my new feature"
   ```

3. Push and create PR:
   ```bash
   git push origin feature/my-feature
   ```

4. Create a Pull Request on GitHub

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation changes
- `style:` — Code style changes (formatting, etc.)
- `refactor:` — Code refactoring
- `test:` — Test changes
- `chore:` — Build/config changes

Examples:
```
feat: add PDF processing tools
fix: resolve memory leak in worker registry
docs: update README with new examples
test: add tests for crypto workers
```

## Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone.

### Expected Behavior

- Be respectful and inclusive
- Accept constructive criticism
- Focus on what is best for the community

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Publishing others' private information

### Enforcement

Report abusive behavior to the maintainers. All complaints will be reviewed and investigated.

---

## Questions?

- Open an issue on GitHub
- Join our Discord server
- Email: contributors@minxg.dev

Thank you for contributing to MINXG! 🚀
