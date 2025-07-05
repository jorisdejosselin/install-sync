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
        "install_sync/main.py",
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
        "install_sync/main.py",
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
    dist_path = Path("dist")
    if dist_path.exists():
        executables = list(dist_path.glob("install-sync*"))
        if executables:
            exe_path = executables[0]
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
            print("❌ No executable found in dist/")
    else:
        print("❌ dist/ directory not found")


if __name__ == "__main__":
    main()
