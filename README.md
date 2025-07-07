# install-sync

Cross-platform software installation manager with git tracking for personal use across multiple machines.

[![CI/CD Pipeline](https://github.com/jorisdejosselin/install-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/jorisdejosselin/install-sync/actions/workflows/ci.yml)
[![Release](https://github.com/jorisdejosselin/install-sync/actions/workflows/release.yml/badge.svg)](https://github.com/jorisdejosselin/install-sync/actions/workflows/release.yml)
[![PyPI version](https://badge.fury.io/py/install-sync.svg)](https://badge.fury.io/py/install-sync)

## Features

- **Cross-platform support**: Works on macOS, Windows, and Linux
- **Multiple package managers**: Supports brew, winget, apt, and Poetry
- **Git integration**: Automatically commits and pushes installation records
- **Machine identification**: Tracks which software is installed on which machine
- **Remote repository creation**: Easy setup with GitHub or GitLab
- **Rich CLI**: Beautiful command-line interface with Typer and Rich
- **Binary distribution**: Single executable files for easy deployment

## Installation

### Quick Install Script
Once the first release is published, you can install using these one-liners:

```bash
# Linux/macOS
curl -sSL https://raw.githubusercontent.com/jorisdejosselin/install-sync/main/install.sh | bash

# Windows (PowerShell)
iwr -useb https://raw.githubusercontent.com/jorisdejosselin/install-sync/main/install.ps1 | iex
```

### Download Binary
Pre-built binaries will be available from the releases page:

- **Linux (x64)**: `install-sync-linux-amd64`
- **Windows (x64)**: `install-sync-windows-amd64.exe`
- **macOS (Intel x64)**: `install-sync-darwin-amd64`
- **macOS (Apple Silicon ARM64)**: `install-sync-darwin-arm64`

Make the binary executable and place it in your PATH.

### From Source
```bash
git clone https://github.com/jorisdejosselin/install-sync.git
cd install-sync
poetry install
poetry run install-sync --help
```

### Using Poetry Environment
If you're developing or want to avoid typing `poetry run` before every command:

**Option 1: Using poetry env activate (Poetry 2.0+)**
```bash
# Get the activation command and run it
$(poetry env activate)

# Now you can run commands directly
install-sync --help
install-sync info
install-sync install git

# Deactivate when done
deactivate
```

**Option 2: Manual activation**
```bash
# Get the virtual environment path
poetry env info --path

# Activate manually (Linux/macOS)
source $(poetry env info --path)/bin/activate

# Activate manually (Windows)
$(poetry env info --path)\Scripts\activate

# Deactivate when done
deactivate
```

**Option 3: Poetry shell (if you have the shell plugin)**
```bash
# Install shell plugin first (one-time setup)
poetry self add poetry-plugin-shell

# Then use shell command
poetry shell
```

## Personal Access Token Setup

Before using `install-sync repo setup`, you'll need to create a Personal Access Token (PAT) for your chosen platform:

### GitHub Token Setup

1. **Go to GitHub Settings**: https://github.com/settings/tokens
2. **Click "Generate new token"** → **"Generate new token (classic)"**
3. **Set expiration**: Choose based on your preference (30 days, 90 days, or custom)
4. **Select scopes**: Check **`repo`** (Full control of private repositories)
   - This includes: `repo:status`, `repo_deployment`, `public_repo`, `repo:invite`, `security_events`
5. **Generate and copy the token** (you won't see it again!)

### GitLab Token Setup

1. **Go to GitLab Profile Settings**: https://gitlab.com/-/profile/personal_access_tokens
2. **Click "Add new token"**
3. **Set expiration date**: Choose based on your preference
4. **Select scopes**: Check **`api`** (Complete read/write access to the API)
   - This allows creating repositories and managing project settings
5. **Create and copy the token** (you won't see it again!)

### Security Notes

- 🔒 **Tokens are only used once** during repository creation and are **not stored** by install-sync
- 🔒 Use **private repositories** (default) to keep your package data secure
- 🔒 Set **reasonable expiration dates** and regenerate tokens periodically
- 🔒 **Never share your tokens** or commit them to code

### Minimal Permissions Alternative

If you prefer more restrictive permissions:

**GitHub**: Use **`public_repo`** scope instead of `repo` if you only want public repositories

**GitLab**: You can use **`read_api`** + **`write_repository`** instead of full `api` access, but repository creation requires broader permissions

📖 **For detailed step-by-step instructions, see [TOKEN_SETUP.md](TOKEN_SETUP.md)**

### Handling Existing Repositories

If you run `install-sync repo setup` and a repository with the same name already exists, you'll be given three options:

1. **Rename** (default): Create a new repository with a different name (e.g., `my-software-packages-v2`)
2. **Delete**: Permanently delete the existing repository and create a new one
3. **Cancel**: Abort the setup process

**⚠️ Deletion Warning**: Choosing to delete will permanently remove all data from the existing repository. This action cannot be undone!

## Quick Start

1. **Set up repository**:
   ```bash
   install-sync repo setup
   ```

2. **Install packages**:
   ```bash
   install-sync install git
   install-sync install python3
   ```

3. **List packages**:
   ```bash
   install-sync list
   ```

4. **Show machine info**:
   ```bash
   install-sync info
   ```

## Usage

### Repository Management
```bash
# Interactive setup - creates remote repo and dedicated tracking directory
# Default repository name: "my-software-packages"
# Default tracking directory: "~/package-tracking"
# Automatically creates .gitignore and README.md
install-sync repo setup

# Fix git configuration if setup hangs or fails
install-sync repo fix

# Show repository status and tracking directory
install-sync repo status

# Show commit history
install-sync repo history --limit 5

# Delete remote repository (WARNING: Destructive!)
install-sync repo delete
```

### Package Management
```bash
# Install with default package manager
install-sync install git

# Install with specific package manager
install-sync install --manager brew python3
install-sync install --manager poetry requests

# Install Poetry package in specific project
install-sync install --manager poetry --project /path/to/project fastapi

# Force reinstall
install-sync install --force nodejs

# List packages for current machine
install-sync list

# List packages for all machines
install-sync list --all

# Sync with remote repository
install-sync sync
```

### Machine Information
```bash
# Show detailed machine and configuration info
install-sync info
```

## Configuration

The system creates several files:

**Local files (not committed to git):**
- `config.json` - Package tracking data and machine profiles
- `repo-config.json` - Repository configuration (created during setup)

**Repository files (committed to git):**
- `.gitignore` - Excludes sensitive config files from version control
- `README.md` - Documentation for your package repository

### Directory Structure

install-sync creates a **dedicated tracking directory** (default: `~/package-tracking/`) that contains:

```
~/package-tracking/
├── .git/              # Git repository
├── .gitignore         # Excludes local config files
├── README.md          # Repository documentation
├── config.json        # Package tracking data (synced)
└── repo-config.json   # Local repository settings (excluded)
```

**Key Points:**
- 📁 **Separate from development projects** - No source code mixed with data
- 🔄 **Syncs across machines** - Each machine updates the same data repository
- 🔒 **Local configs excluded** - Only package data is shared via git

The `config.json` tracks:
- Machine profiles (OS, architecture, hostname)
- Installed packages per machine with versions and timestamps
- Git settings (auto-commit, auto-push)

Example `config.json`:
```json
{
  "machines": {
    "a1b2c3d4": {
      "profile_id": "a1b2c3d4",
      "machine_name": "MacBook-Pro",
      "os_type": "darwin",
      "architecture": "arm64"
    }
  },
  "packages": {
    "a1b2c3d4": [
      {
        "name": "git",
        "package_manager": "brew",
        "version": "2.42.0",
        "installed_at": "2025-01-15T10:30:00"
      }
    ]
  },
  "git": {
    "auto_commit": true,
    "auto_push": true,
    "commit_message_template": "Install {package} on {machine}"
  }
}
```

## Package Manager Support

| OS | Package Manager | Command | Status |
|---|---|---|---|
| macOS | Homebrew | `brew` | ✅ Supported |
| Windows | Windows Package Manager | `winget` | ✅ Supported |
| Linux | APT | `apt` | ✅ Supported |
| Any | Poetry | `poetry` | ✅ Supported |

## Development

### Poetry Workflow (Recommended)

For the best development experience, use Poetry's virtual environment:

```bash
# Clone and setup
git clone https://github.com/jorisdejosselin/install-sync.git
cd install-sync
poetry install

# Activate Poetry environment (Poetry 2.0+)
$(poetry env activate)

# Now all commands work without 'poetry run' prefix
install-sync --help
pytest
black .
mypy install_sync/

# When done developing
deactivate
```

**Benefits of activating the Poetry environment:**
- No need to prepend `poetry run` to every command
- Your terminal prompt shows you're in the virtual environment
- All installed dependencies are directly available
- Works across different operating systems

**Alternative: Manual activation (works with all Poetry versions)**
```bash
# Direct activation (recommended for reliability)
source $(poetry env info --path)/bin/activate  # Linux/macOS
# or
$(poetry env info --path)\Scripts\activate     # Windows
```

### Setup
```bash
git clone https://github.com/jorisdejosselin/install-sync.git
cd install-sync
poetry install
$(poetry env activate)  # Activate virtual environment
pre-commit install
```

### Testing
If you're using Poetry environment (recommended for development):
```bash
# After running '$(poetry env activate)'
pytest
black --check .
isort --check-only .
flake8 .
mypy install_sync/
```

Or with `poetry run` prefix:
```bash
poetry run pytest
poetry run black --check .
poetry run isort --check-only .
poetry run flake8 .
poetry run mypy install_sync/
```

### Building
```bash
# Build Python package
poetry build

# Build binary (if in Poetry environment)
python build_script.py

# Or with poetry run
poetry run python build_script.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Security Notes

- Personal access tokens are not stored locally
- Repository can be set to private for security
- No sensitive data is tracked beyond package names and installation dates
- All git operations are performed with user credentials
