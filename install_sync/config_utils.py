"""Configuration utilities."""

import json
import os
from pathlib import Path

from .models import Config, GlobalConfig


def _resolve_tracking_dir() -> Path:
    """Minimal tracking-dir resolver usable outside of main.py (no RepoManager/console)."""
    env_dir = os.environ.get("INSTALL_SYNC_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    try:
        global_config = load_global_config()
        if global_config.default_tracking_directory:
            return Path(global_config.default_tracking_directory).expanduser().resolve()
    except Exception:
        pass
    return Path.home() / "package-tracking"


def load_config() -> Config:
    """Load configuration from the tracking directory."""
    config_file = _resolve_tracking_dir() / "config.json"
    if config_file.exists():
        with open(config_file, "r") as f:
            return Config(**json.load(f))
    return Config()


def save_config(config: Config) -> None:
    """Save configuration to the tracking directory."""
    tracking_dir = _resolve_tracking_dir()
    tracking_dir.mkdir(parents=True, exist_ok=True)
    with open(tracking_dir / "config.json", "w") as f:
        json.dump(config.dict(), f, indent=2, default=str)


def load_global_config() -> GlobalConfig:
    """Load global configuration from ~/.install-sync.config"""
    global_config_path = Path.home() / ".install-sync.config"
    if global_config_path.exists():
        try:
            with open(global_config_path, "r") as f:
                data = json.load(f)
                return GlobalConfig(**data)
        except Exception:
            # If config is corrupted, return default
            pass
    return GlobalConfig()


def save_global_config(config: GlobalConfig) -> None:
    """Save global configuration to ~/.install-sync.config"""
    global_config_path = Path.home() / ".install-sync.config"
    try:
        with open(global_config_path, "w") as f:
            json.dump(config.dict(), f, indent=2)
    except Exception:
        # Silently fail if we can't save config
        pass
