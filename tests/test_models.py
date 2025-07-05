"""Tests for models module."""

import pytest

from install_sync.models import Config, MachineProfile, PackageInfo


def test_machine_profile_creation():
    """Test machine profile creation."""
    profile = MachineProfile.create_current()

    assert profile.profile_id
    assert profile.machine_name
    assert profile.os_type
    assert profile.architecture
    assert len(profile.profile_id) == 8


def test_config_package_management():
    """Test config package management."""
    config = Config()
    profile_id = "test123"

    # Test empty state
    assert not config.is_package_installed(profile_id, "git")
    assert config.get_current_machine_packages(profile_id) == []

    # Add package
    package = PackageInfo(name="git", package_manager="brew")
    config.add_package(profile_id, package)

    # Test package is recorded
    assert config.is_package_installed(profile_id, "git")
    packages = config.get_current_machine_packages(profile_id)
    assert len(packages) == 1
    assert packages[0].name == "git"


def test_package_info_creation():
    """Test package info creation."""
    package = PackageInfo(name="python", package_manager="brew", version="3.11.0")

    assert package.name == "python"
    assert package.package_manager == "brew"
    assert package.version == "3.11.0"
    assert package.installed_at
