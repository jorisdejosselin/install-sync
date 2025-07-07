"""Platform-compatible symbols and emojis."""

import platform
import sys
from typing import Dict


def get_symbols() -> Dict[str, str]:
    """Get platform-appropriate symbols."""
    # Check if we're on Windows PowerShell/Command Prompt
    is_windows_console = platform.system() == "Windows" and sys.stdout.encoding not in [
        "utf-8",
        "UTF-8",
    ]

    if is_windows_console:
        # Windows PowerShell/CMD compatible symbols
        return {
            "install": "[INSTALL]",
            "success": "[SUCCESS]",
            "error": "[ERROR]",
            "warning": "[WARNING]",
            "info": "[INFO]",
            "debug": "[DEBUG]",
            "package": "[PACKAGE]",
            "file": "[FILE]",
            "git": "[GIT]",
            "repo": "[REPO]",
        }
    else:
        # Unicode emojis for modern terminals
        return {
            "install": "🔧",
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "debug": "🐛",
            "package": "📦",
            "file": "📄",
            "git": "📝",
            "repo": "📁",
        }


# Global symbols instance
SYMBOLS = get_symbols()
