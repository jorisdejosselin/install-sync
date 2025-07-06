#!/usr/bin/env python3
"""Entry point for install-sync CLI when building as standalone executable."""

import sys
from pathlib import Path

# Add the install_sync package to the path for absolute imports
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    from install_sync.main import app
    app()