"""Package manager implementations."""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

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
    def upgrade(self, package_name: str) -> bool:
        """Upgrade a package to latest version."""
        pass

    @abstractmethod
    def upgrade_all(self) -> bool:
        """Upgrade all packages."""
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
            subprocess.run(
                ["brew", "install", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully installed {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            stdout = e.stdout.strip() if e.stdout else ""

            # Check for specific brew errors
            if "No available formula" in stderr or "No formula found" in stderr:
                console.print(f"❌ Package '{package_name}' not found in Homebrew")
                console.print(
                    f"💡 [dim]Try searching with: brew search {package_name}[/dim]"
                )
            elif "already installed" in stderr:
                console.print(f"ℹ️  Package {package_name} is already installed")
                console.print(
                    f"💡 [dim]Use 'brew upgrade {package_name}' to update[/dim]"
                )
                return True  # Not really a failure
            elif "Permission denied" in stderr:
                console.print(f"❌ Permission denied installing {package_name}")
                console.print(
                    "💡 [dim]Check Homebrew permissions or try with sudo[/dim]"
                )
            else:
                console.print(f"❌ Failed to install {package_name}")
                if stderr:
                    console.print(f"   Error: {stderr}")
                if stdout:
                    console.print(f"   Output: {stdout}")
            return False

    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using brew."""
        try:
            subprocess.run(
                ["brew", "uninstall", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}: {e.stderr}")
            return False

    def upgrade(self, package_name: str) -> bool:
        """Upgrade package using brew."""
        try:
            subprocess.run(
                ["brew", "upgrade", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully upgraded {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            # Check if package is already up to date
            stderr_lower = str(e.stderr).lower()
            if "already installed" in stderr_lower or "up-to-date" in stderr_lower:
                console.print(f"ℹ️  {package_name} is already up to date")
                return True
            console.print(f"❌ Failed to upgrade {package_name}: {e.stderr}")
            return False

    def upgrade_all(self) -> bool:
        """Upgrade all brew packages."""
        try:
            subprocess.run(
                ["brew", "upgrade"], capture_output=True, text=True, check=True
            )
            console.print("✅ Successfully upgraded all packages")
            return True
        except subprocess.CalledProcessError as e:
            stderr_lower = str(e.stderr).lower()
            if "already installed" in stderr_lower or "up-to-date" in stderr_lower:
                console.print("ℹ️  All packages are already up to date")
                return True
            console.print(f"❌ Failed to upgrade packages: {e.stderr}")
            return False

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via brew."""
        try:
            subprocess.run(
                ["brew", "list", package_name], capture_output=True, check=True
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
                check=True,
            )
            return result.stdout.strip().split()[-1] if result.stdout.strip() else None
        except subprocess.CalledProcessError:
            return None

    def list_installed(self) -> List[str]:
        """List all brew packages."""
        try:
            result = subprocess.run(
                ["brew", "list"], capture_output=True, text=True, check=True
            )
            return result.stdout.strip().split("\n") if result.stdout.strip() else []
        except subprocess.CalledProcessError:
            return []


class WingetManager(PackageManager):
    """Windows Package Manager."""

    def install(self, package_name: str) -> bool:
        """Install package using winget."""
        try:
            subprocess.run(
                [
                    "winget",
                    "install",
                    package_name,
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully installed {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            stdout = e.stdout.strip() if e.stdout else ""

            # Check for specific winget errors
            if "No package found matching input criteria" in stderr:
                console.print(
                    f"❌ Package '{package_name}' not found in winget repositories"
                )
                console.print(
                    f"💡 [dim]Try searching with: winget search {package_name}[/dim]"
                )
            elif "requires admin" in stderr.lower() or "elevation" in stderr.lower():
                console.print(f"❌ Admin privileges required to install {package_name}")
                console.print("💡 [dim]Run as administrator or use --scope user[/dim]")
            elif "already installed" in stderr.lower():
                console.print(f"ℹ️  Package {package_name} is already installed")
                console.print(
                    f"💡 [dim]Use 'winget upgrade {package_name}' to update[/dim]"
                )
                return True  # Not really a failure
            elif (
                "cannot be upgraded" in stderr.lower()
                or "cannot upgrade" in stderr.lower()
            ):
                console.print(f"❌ Package {package_name} cannot be upgraded via winget")
                console.print("💡 [dim]Some packages require manual updates[/dim]")
            else:
                console.print(f"❌ Failed to install {package_name}")
                if stderr:
                    console.print(f"   Error: {stderr}")
                if stdout:
                    console.print(f"   Output: {stdout}")
            return False

    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using winget."""
        try:
            subprocess.run(
                ["winget", "uninstall", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}: {e.stderr}")
            return False

    def upgrade(self, package_name: str) -> bool:
        """Upgrade package using winget."""
        try:
            subprocess.run(
                ["winget", "upgrade", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully upgraded {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            stdout = e.stdout.strip() if e.stdout else ""
            stderr_lower = stderr.lower()

            if "no newer version" in stderr_lower or "up to date" in stderr_lower:
                console.print(f"ℹ️  {package_name} is already up to date")
                return True
            elif (
                "cannot be upgraded" in stderr_lower or "cannot upgrade" in stderr_lower
            ):
                console.print(
                    f"⚠️  Package {package_name} cannot be upgraded via winget"
                )
                console.print(
                    "💡 [dim]This package may require manual updates or be managed by another installer[/dim]"
                )
                return True  # Treat as "success" - package exists but can't be upgraded
            elif "package not found" in stderr_lower:
                console.print(f"❌ Package {package_name} not found for upgrade")
                console.print(
                    "💡 [dim]Package may have been uninstalled or installed differently[/dim]"
                )
            elif "requires admin" in stderr_lower or "elevation" in stderr_lower:
                console.print(f"❌ Admin privileges required to upgrade {package_name}")
                console.print("💡 [dim]Run as administrator[/dim]")
            else:
                console.print(f"❌ Failed to upgrade {package_name}")
                if stderr:
                    console.print(f"   Error: {stderr}")
                if stdout:
                    console.print(f"   Output: {stdout}")
            return False

    def upgrade_all(self) -> bool:
        """Upgrade all winget packages."""
        try:
            subprocess.run(
                ["winget", "upgrade", "--all"],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print("✅ Successfully upgraded all packages")
            return True
        except subprocess.CalledProcessError as e:
            stderr_lower = str(e.stderr).lower()
            if "no newer version" in stderr_lower or "up to date" in stderr_lower:
                console.print("ℹ️  All packages are already up to date")
                return True
            console.print(f"❌ Failed to upgrade packages: {e.stderr}")
            return False

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via winget."""
        try:
            result = subprocess.run(
                ["winget", "list", package_name],
                capture_output=True,
                text=True,
                check=True,
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
                check=True,
            )
            # Parse version from winget output (simplified)
            lines = result.stdout.strip().split("\n")
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
                ["winget", "list"], capture_output=True, text=True, check=True
            )
            packages = []
            lines = result.stdout.strip().split("\n")[2:]
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
            subprocess.run(
                ["sudo", "apt", "install", "-y", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully installed {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            stdout = e.stdout.strip() if e.stdout else ""

            # Check for specific apt errors
            if "Unable to locate package" in stderr or "No package" in stderr:
                console.print(
                    f"❌ Package '{package_name}' not found in apt repositories"
                )
                console.print(
                    f"💡 [dim]Try searching with: apt search {package_name}[/dim]"
                )
                console.print(
                    "💡 [dim]You may need to update package lists: sudo apt update[/dim]"
                )
            elif (
                "already the newest version" in stderr or "already installed" in stderr
            ):
                console.print(f"ℹ️  Package {package_name} is already up to date")
                return True  # Not really a failure
            elif "sudo" in stderr and "permission" in stderr.lower():
                console.print(f"❌ Root privileges required to install {package_name}")
                console.print("💡 [dim]Command should include sudo[/dim]")
            elif "dpkg was interrupted" in stderr:
                console.print(
                    f"❌ Package manager interrupted during {package_name} installation"
                )
                console.print("💡 [dim]Try: sudo dpkg --configure -a[/dim]")
            else:
                console.print(f"❌ Failed to install {package_name}")
                if stderr:
                    console.print(f"   Error: {stderr}")
                if stdout:
                    console.print(f"   Output: {stdout}")
            return False

    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using apt."""
        try:
            subprocess.run(
                ["sudo", "apt", "remove", "-y", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}: {e.stderr}")
            return False

    def upgrade(self, package_name: str) -> bool:
        """Upgrade package using apt."""
        try:
            # First update package lists
            subprocess.run(["sudo", "apt", "update"], capture_output=True, check=True)

            subprocess.run(
                ["sudo", "apt", "upgrade", "-y", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully upgraded {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            if "already the newest version" in str(e.stderr).lower():
                console.print(f"ℹ️  {package_name} is already up to date")
                return True
            console.print(f"❌ Failed to upgrade {package_name}: {e.stderr}")
            return False

    def upgrade_all(self) -> bool:
        """Upgrade all apt packages."""
        try:
            # First update package lists
            subprocess.run(["sudo", "apt", "update"], capture_output=True, check=True)

            subprocess.run(
                ["sudo", "apt", "upgrade", "-y"],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print("✅ Successfully upgraded all packages")
            return True
        except subprocess.CalledProcessError as e:
            if "already the newest version" in str(e.stderr).lower():
                console.print("ℹ️  All packages are already up to date")
                return True
            console.print(f"❌ Failed to upgrade packages: {e.stderr}")
            return False

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via apt."""
        try:
            result = subprocess.run(
                ["dpkg", "-l", package_name], capture_output=True, text=True, check=True
            )
            return "ii" in result.stdout
        except subprocess.CalledProcessError:
            return False

    def get_version(self, package_name: str) -> Optional[str]:
        """Get apt package version."""
        try:
            result = subprocess.run(
                ["dpkg", "-l", package_name], capture_output=True, text=True, check=True
            )
            lines = result.stdout.strip().split("\n")
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
                ["dpkg", "-l"], capture_output=True, text=True, check=True
            )
            packages = []
            lines = result.stdout.strip().split("\n")
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
            subprocess.run(
                ["poetry", "add", package_name],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully installed {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            stdout = e.stdout.strip() if e.stdout else ""

            # Check for specific poetry errors
            if "Could not find a matching version" in stderr or "not found" in stderr:
                console.print(f"❌ Package '{package_name}' not found on PyPI")
                console.print(
                    f"💡 [dim]Check package name or try searching PyPI directly[/dim]"
                )
            elif "already present" in stderr or "already installed" in stderr:
                console.print(f"ℹ️  Package {package_name} is already in dependencies")
                return True  # Not really a failure
            elif "not a poetry project" in stderr.lower() or "pyproject.toml" in stderr:
                console.print(f"❌ Not a Poetry project in {self.project_path}")
                console.print(
                    "💡 [dim]Run 'poetry init' to create a Poetry project[/dim]"
                )
            elif "lock file" in stderr and "outdated" in stderr:
                console.print(f"❌ Poetry lock file is outdated")
                console.print("💡 [dim]Try: poetry lock --no-update[/dim]")
            else:
                console.print(f"❌ Failed to install {package_name}")
                if stderr:
                    console.print(f"   Error: {stderr}")
                if stdout:
                    console.print(f"   Output: {stdout}")
            return False

    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using poetry."""
        try:
            subprocess.run(
                ["poetry", "remove", package_name],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}: {e.stderr}")
            return False

    def upgrade(self, package_name: str) -> bool:
        """Upgrade package using poetry."""
        try:
            subprocess.run(
                ["poetry", "update", package_name],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"✅ Successfully upgraded {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            if "already up-to-date" in str(e.stderr).lower():
                console.print(f"ℹ️  {package_name} is already up to date")
                return True
            console.print(f"❌ Failed to upgrade {package_name}: {e.stderr}")
            return False

    def upgrade_all(self) -> bool:
        """Upgrade all poetry packages."""
        try:
            subprocess.run(
                ["poetry", "update"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )
            console.print("✅ Successfully upgraded all packages")
            return True
        except subprocess.CalledProcessError as e:
            if "already up-to-date" in str(e.stderr).lower():
                console.print("ℹ️  All packages are already up to date")
                return True
            console.print(f"❌ Failed to upgrade packages: {e.stderr}")
            return False

    def is_installed(self, package_name: str) -> bool:
        """Check if package is in poetry project."""
        try:
            subprocess.run(
                ["poetry", "show", package_name],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
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
                check=True,
            )
            lines = result.stdout.strip().split("\n")
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
                check=True,
            )
            packages = []
            lines = result.stdout.strip().split("\n")
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
    def get_manager(cls, manager_type: str, **kwargs: Any) -> PackageManager:
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
