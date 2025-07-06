#!/usr/bin/env python3
"""Build script for install-sync."""

import subprocess
import sys
from pathlib import Path


def build_with_nuitka() -> None:
    """Build using Nuitka (for Python 3.13+)."""
    cmd = [
        "poetry",
        "run",
        "nuitka",
        "--onefile",
        "--output-filename=install-sync",
        "--include-package=install_sync",
        "cli_entry.py",
    ]

    subprocess.run(cmd, check=True)
    print("✅ Built with Nuitka")


def build_with_pyinstaller() -> None:
    """Build using PyInstaller (for Python < 3.13)."""
    cmd = [
        "poetry",
        "run",
        "pyinstaller",
        "--onefile",
        "--name",
        "install-sync",
        "--add-data",
        "install_sync:install_sync",
        "--hidden-import",
        "install_sync",
        "--hidden-import",
        "install_sync.main",
        "--hidden-import",
        "install_sync.config_utils",
        "--hidden-import",
        "install_sync.models",
        "--hidden-import",
        "install_sync.git_manager",
        "--hidden-import",
        "install_sync.package_managers",
        "--hidden-import",
        "install_sync.repo_manager",
        "--hidden-import",
        "ipaddress",
        "--hidden-import",
        "pathlib",
        "--hidden-import",
        "urllib",
        "--hidden-import",
        "urllib.parse",
        "--collect-all",
        "typer",
        "--collect-all",
        "rich",
        "--collect-all",
        "pydantic",
        "cli_entry.py",
    ]

    subprocess.run(cmd, check=True)
    print("✅ Built with PyInstaller")


def main() -> None:
    """Main build function."""
    print(
        f"🔧 Building install-sync for Python "
        f"{sys.version_info.major}.{sys.version_info.minor}"
    )

    # Install build dependencies
    print("📦 Installing build dependencies...")
    subprocess.run(["poetry", "install", "--with", "build"], check=True)

    # Choose build tool based on Python version
    if sys.version_info >= (3, 13):
        print("🚀 Using Nuitka for Python 3.13+")
        build_with_nuitka()
    else:
        print("🚀 Using PyInstaller for Python < 3.13")
        build_with_pyinstaller()

    # Find the built executable
    exe_path = Path("install-sync")
    if exe_path.exists():
        print(f"✅ Built executable: {exe_path}")

        # Test the executable
        print("🧪 Testing executable...")
        result = subprocess.run(
            [str(exe_path), "--help"], capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✅ Executable test passed!")
        else:
            print(f"❌ Executable test failed: {result.stderr}")
    else:
        print("❌ Executable 'install-sync' not found")


if __name__ == "__main__":
    main()
