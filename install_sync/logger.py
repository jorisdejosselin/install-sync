"""Centralized logging for install-sync."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

LOG_FILE = Path.home() / ".install-sync.log"

# Module-level flags set by setup()
show_error_output: bool = True
verbose_logging: bool = False

# In-memory store for the most recent error per package (for summary display)
_recent_errors: Dict[str, str] = {}

_initialized = False


def setup(show_error_output_: bool = True, verbose_logging_: bool = False) -> None:
    """Call once at startup with settings from GlobalConfig."""
    global show_error_output, verbose_logging, _initialized
    if _initialized:
        return
    show_error_output = show_error_output_
    verbose_logging = verbose_logging_
    _initialized = True

    logger = logging.getLogger("install_sync")
    logger.setLevel(logging.DEBUG)

    fh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(fh)


def _get_logger() -> logging.Logger:
    return logging.getLogger("install_sync")


def _last_error_line(text: str) -> str:
    """Return the last non-empty, non-warning line from stderr output."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Skip generic warning lines to find the most specific error
    for line in reversed(lines):
        if not line.lower().startswith("warning:") and not line.lower().startswith("note:"):
            return line
    return lines[-1] if lines else ""


def log_failure(package_name: str, manager: str, stderr: str, stdout: str = "") -> None:
    """Log a failed command. Always writes to file; optionally prints stderr to console."""
    if not _initialized:
        setup()  # Use defaults if not explicitly initialized

    from rich.console import Console
    _c = Console()

    msg = f"[{manager}:{package_name}] FAILED"
    if stderr:
        msg += f"\n  stderr: {stderr.strip()}"
    if stdout:
        msg += f"\n  stdout: {stdout.strip()}"
    _get_logger().error(msg)

    # Store the most specific error line for summary display
    summary = _last_error_line(stderr) or _last_error_line(stdout)
    _recent_errors[package_name] = summary

    # In verbose mode show full stderr; otherwise show last meaningful line
    if verbose_logging and (stderr.strip() or stdout.strip()):
        if stderr.strip():
            _c.print(f"[dim]{stderr.strip()}[/dim]")
        if stdout.strip():
            _c.print(f"[dim]{stdout.strip()}[/dim]")
    elif show_error_output and summary:
        _c.print(f"[dim]  └─ {summary}[/dim]")


def log_success(package_name: str, manager: str, stdout: str = "", stderr: str = "") -> None:
    """Log a successful command to file when verbose_logging is enabled."""
    if not verbose_logging:
        return
    msg = f"[{manager}:{package_name}] OK"
    if stdout:
        msg += f"\n  stdout: {stdout.strip()}"
    if stderr:
        msg += f"\n  stderr: {stderr.strip()}"
    _get_logger().debug(msg)


def get_recent_error(package_name: str) -> Optional[str]:
    """Retrieve stored error for a package (used by --all summary)."""
    return _recent_errors.get(package_name)


def clear_recent_errors() -> None:
    """Clear the in-memory error store. Call at the start of a bulk operation."""
    _recent_errors.clear()
