"""Configuration utilities."""

import json
from pathlib import Path

from .models import GlobalConfig


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