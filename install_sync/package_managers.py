"""Package manager implementations."""

import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

from .models import PackageInfo

console = Console()


class PackageManager(ABC):
    """Abstract base class for package managers."""
    
    @abstractmethod
    def install(self, package_name: str) -> bool:
        """Install a package."""
        pass
    
    @abstractmethod
    def uninstall(self, package_name: str) -> bool:
        """Uninstall a package."""
        pass
    
    @abstractmethod
    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed."""
        pass
    
    @abstractmethod
    def get_version(self, package_name: str) -> Optional[str]:
        """Get installed package version."""
        pass
    
    @abstractmethod
    def list_installed(self) -> List[str]:
        """List all installed packages."""
        pass


class BrewManager(PackageManager):
    """Homebrew package manager for macOS."""
    
    def install(self, package_name: str) -> bool:
        """Install package using brew."""
        try:
            result = subprocess.run(
                ["brew", "install", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            console.print(f"✅ Successfully installed {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to install {package_name}: {e.stderr}")
            return False
    
    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using brew."""
        try:
            result = subprocess.run(
                ["brew", "uninstall", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}: {e.stderr}")
            return False
    
    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via brew."""
        try:
            subprocess.run(
                ["brew", "list", package_name],
                capture_output=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_version(self, package_name: str) -> Optional[str]:
        """Get brew package version."""
        try:
            result = subprocess.run(
                ["brew", "list", "--versions", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip().split()[-1] if result.stdout.strip() else None
        except subprocess.CalledProcessError:
            return None
    
    def list_installed(self) -> List[str]:
        """List all brew packages."""
        try:
            result = subprocess.run(
                ["brew", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip().split('\n') if result.stdout.strip() else []
        except subprocess.CalledProcessError:
            return []


class WingetManager(PackageManager):
    """Windows Package Manager."""
    
    def install(self, package_name: str) -> bool:
        """Install package using winget."""
        try:
            result = subprocess.run(
                ["winget", "install", package_name, "--accept-package-agreements", "--accept-source-agreements"],
                capture_output=True,
                text=True,
                check=True
            )
            console.print(f"✅ Successfully installed {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to install {package_name}: {e.stderr}")
            return False
    
    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using winget."""
        try:
            result = subprocess.run(
                ["winget", "uninstall", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}: {e.stderr}")
            return False
    
    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via winget."""
        try:
            result = subprocess.run(
                ["winget", "list", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            return package_name.lower() in result.stdout.lower()
        except subprocess.CalledProcessError:
            return False
    
    def get_version(self, package_name: str) -> Optional[str]:
        """Get winget package version."""
        try:
            result = subprocess.run(
                ["winget", "list", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            # Parse version from winget output (simplified)
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if package_name.lower() in line.lower():
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[2]
            return None
        except subprocess.CalledProcessError:
            return None
    
    def list_installed(self) -> List[str]:
        """List all winget packages."""
        try:
            result = subprocess.run(
                ["winget", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            packages = []
            lines = result.stdout.strip().split('\n')[2:]  # Skip header
            for line in lines:
                if line.strip():
                    packages.append(line.split()[0])
            return packages
        except subprocess.CalledProcessError:
            return []


class AptManager(PackageManager):
    """APT package manager for Linux."""
    
    def install(self, package_name: str) -> bool:
        """Install package using apt."""
        try:
            result = subprocess.run(
                ["sudo", "apt", "install", "-y", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            console.print(f"✅ Successfully installed {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to install {package_name}: {e.stderr}")
            return False
    
    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using apt."""
        try:
            result = subprocess.run(
                ["sudo", "apt", "remove", "-y", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}: {e.stderr}")
            return False
    
    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via apt."""
        try:
            result = subprocess.run(
                ["dpkg", "-l", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            return "ii" in result.stdout
        except subprocess.CalledProcessError:
            return False
    
    def get_version(self, package_name: str) -> Optional[str]:
        """Get apt package version."""
        try:
            result = subprocess.run(
                ["dpkg", "-l", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.startswith("ii") and package_name in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[2]
            return None
        except subprocess.CalledProcessError:
            return None
    
    def list_installed(self) -> List[str]:
        """List all apt packages."""
        try:
            result = subprocess.run(
                ["dpkg", "-l"],
                capture_output=True,
                text=True,
                check=True
            )
            packages = []
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.startswith("ii"):
                    packages.append(line.split()[1])
            return packages
        except subprocess.CalledProcessError:
            return []


class PoetryManager(PackageManager):
    """Poetry package manager for Python."""
    
    def __init__(self, project_path: Optional[Path] = None):
        self.project_path = project_path or Path.cwd()
    
    def install(self, package_name: str) -> bool:
        """Install package using poetry."""
        try:
            result = subprocess.run(
                ["poetry", "add", package_name],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            console.print(f"✅ Successfully installed {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to install {package_name}: {e.stderr}")
            return False
    
    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using poetry."""
        try:
            result = subprocess.run(
                ["poetry", "remove", package_name],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}: {e.stderr}")
            return False
    
    def is_installed(self, package_name: str) -> bool:
        """Check if package is in poetry project."""
        try:
            result = subprocess.run(
                ["poetry", "show", package_name],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_version(self, package_name: str) -> Optional[str]:
        """Get poetry package version."""
        try:
            result = subprocess.run(
                ["poetry", "show", package_name],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.startswith("version"):
                    return line.split(":")[1].strip()
            return None
        except subprocess.CalledProcessError:
            return None
    
    def list_installed(self) -> List[str]:
        """List all poetry packages."""
        try:
            result = subprocess.run(
                ["poetry", "show"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            packages = []
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    packages.append(line.split()[0])
            return packages
        except subprocess.CalledProcessError:
            return []


class PackageManagerFactory:
    """Factory for creating package managers."""
    
    _managers: Dict[str, PackageManager] = {}
    
    @classmethod
    def get_manager(cls, manager_type: str, **kwargs) -> PackageManager:
        """Get package manager instance."""
        if manager_type not in cls._managers:
            if manager_type == "brew":
                cls._managers[manager_type] = BrewManager()
            elif manager_type == "winget":
                cls._managers[manager_type] = WingetManager()
            elif manager_type == "apt":
                cls._managers[manager_type] = AptManager()
            elif manager_type == "poetry":
                cls._managers[manager_type] = PoetryManager(**kwargs)
            else:
                raise ValueError(f"Unknown package manager: {manager_type}")
        
        return cls._managers[manager_type]
    
    @classmethod
    def get_default_manager(cls) -> PackageManager:
        """Get default package manager for current OS."""
        import platform
        
        os_type = platform.system().lower()
        if os_type == "darwin":
            return cls.get_manager("brew")
        elif os_type == "windows":
            return cls.get_manager("winget")
        elif os_type == "linux":
            return cls.get_manager("apt")
        else:
            raise ValueError(f"Unsupported OS: {os_type}")