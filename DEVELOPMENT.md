# Development Guide

This guide covers the development workflow for install-sync using Poetry.

## Quick Setup

```bash
# Clone and install
git clone https://github.com/joris/install-sync.git
cd install-sync
poetry install

# Activate environment (choose one method)
$(poetry env activate)                              # Modern Poetry 2.0+
source $(poetry env info --path)/bin/activate      # Manual (Linux/macOS)
$(poetry env info --path)\Scripts\activate         # Manual (Windows)

# Verify installation
install-sync --help

# Set up repository (requires GitHub/GitLab token - see TOKEN_SETUP.md)
install-sync repo setup
```

## Poetry Environment Methods

### Method 1: poetry env activate (Recommended for Poetry 2.0+)
```bash
# Note: poetry env activate just prints the activation command, so we use $() to execute it
$(poetry env activate)
# Your prompt will change to show (install-sync-py3.x)
install-sync --help  # Works without 'poetry run'
deactivate           # When done
```

### Method 2: Manual activation (Universal)
```bash
# Get environment path
poetry env info --path

# Activate (Linux/macOS)
source $(poetry env info --path)/bin/activate

# Activate (Windows Command Prompt)
$(poetry env info --path)\Scripts\activate.bat

# Activate (Windows PowerShell)
$(poetry env info --path)\Scripts\Activate.ps1

# Deactivate when done
deactivate
```

### Method 3: Poetry shell plugin (Optional)
```bash
# Install plugin once
poetry self add poetry-plugin-shell

# Use shell command
poetry shell
exit  # or Ctrl+D to exit
```

### Method 4: Always use poetry run (No activation needed)
```bash
poetry run install-sync --help
poetry run pytest
poetry run black .
```

## Development Workflow

### 1. Environment Setup
```bash
poetry install
$(poetry env activate)  # or manual activation
pre-commit install
```

### 2. Code Changes
```bash
# Edit code in install_sync/
# Run tests frequently
pytest

# Format code
black .
isort .

# Type checking
mypy install_sync/

# Lint
flake8 .
```

### 3. Testing
```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_models.py

# Run with coverage
pytest --cov=install_sync

# Test CLI directly
install-sync info
install-sync --help
```

### 4. Building
```bash
# Build Python package
poetry build

# Build binary (uses Nuitka for Python 3.13+, PyInstaller for older versions)
python build_script.py
```

## Troubleshooting

### Environment not activating?
- **Important**: `poetry env activate` just prints the command - you need to run it with `$(poetry env activate)`
- Try manual activation: `source $(poetry env info --path)/bin/activate`
- Check Poetry version: `poetry --version`
- Recreate environment: `poetry env remove python && poetry install`

### Commands not found after activation?
- Verify you're in the right directory
- Check that `poetry install` completed successfully
- Try `which install-sync` to see if it's in PATH

### Poetry shell not working?
- This is normal for Poetry 2.0+
- Use `poetry env activate` or manual activation instead
- Or install shell plugin: `poetry self add poetry-plugin-shell`

## IDE Integration

### VS Code
Add to `.vscode/settings.json`:
```json
{
    "python.pythonPath": "path_from_poetry_env_info",
    "python.terminal.activateEnvironment": true
}
```

### PyCharm
- File → Settings → Project → Python Interpreter
- Add Interpreter → Existing Environment
- Use path from `poetry env info --path`

## Environment Variables

The Poetry environment automatically includes:
- All dependencies from `pyproject.toml`
- Development dependencies
- The `install-sync` command in PATH
- All Python packages in editable mode

Your prompt will typically show:
```
(install-sync-py3.x) $ install-sync --help
```

This indicates you're in the Poetry virtual environment and can run commands directly.
