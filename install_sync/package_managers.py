"""Package manager implementations."""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

from . import logger as _logger
from .symbols import SYMBOLS

console = Console()


def _run(cmd, **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess command, printing cmd + output when verbose_logging is on."""
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if _logger.verbose_logging:
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        console.print(f"[dim]  → {cmd_str}[/dim]")
        if result.stdout.strip():
            console.print(f"[dim]{result.stdout.strip()}[/dim]")
        if result.stderr.strip():
            console.print(f"[dim]{result.stderr.strip()}[/dim]")
    return result


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
            result = subprocess.run(
                ["brew", "install", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"{SYMBOLS['success']} Successfully installed {package_name}")
            _logger.log_success(package_name, "brew", result.stdout, result.stderr)
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
                console.print(f"{SYMBOLS['error']} Failed to install {package_name}")
            _logger.log_failure(package_name, "brew", stderr, stdout)
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
            console.print(f"❌ Failed to uninstall {package_name}")
            _logger.log_failure(package_name, "brew", e.stderr or "", e.stdout or "")
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
            console.print(f"❌ Failed to upgrade {package_name}")
            _logger.log_failure(package_name, "brew", e.stderr or "", e.stdout or "")
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
            console.print("❌ Failed to upgrade packages")
            _logger.log_failure("(all)", "brew", e.stderr or "", e.stdout or "")
            return False

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via brew."""
        result = _run(["brew", "list", package_name])
        return result.returncode == 0

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
            console.print(f"{SYMBOLS['success']} Successfully installed {package_name}")
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
                "Found an existing package already installed" in stderr
                and "No available upgrade found" in stderr
            ):
                console.print(
                    f"ℹ️  Package {package_name} is already installed and up to date"
                )
                console.print("💡 [dim]Package is already at the latest version[/dim]")
                return True  # Not really a failure - package is installed and current
            elif (
                "cannot be upgraded" in stderr.lower()
                or "cannot upgrade" in stderr.lower()
            ):
                console.print(f"❌ Package {package_name} cannot be upgraded via winget")
                console.print("💡 [dim]Some packages require manual updates[/dim]")
            else:
                console.print(f"{SYMBOLS['error']} Failed to install {package_name}")
            _logger.log_failure(package_name, "winget", stderr, stdout)
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
            console.print(f"❌ Failed to uninstall {package_name}")
            _logger.log_failure(package_name, "winget", e.stderr or "", e.stdout or "")
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
                    "💡 [dim]This package may require manual updates or be managed "
                    "by another installer[/dim]"
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
            _logger.log_failure(package_name, "winget", stderr, stdout)
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
            console.print("❌ Failed to upgrade packages")
            _logger.log_failure("(all)", "winget", e.stderr or "", e.stdout or "")
            return False

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via winget."""
        result = _run(["winget", "list", package_name])
        return result.returncode == 0 and package_name.lower() in result.stdout.lower()

    def get_version(self, package_name: str) -> Optional[str]:
        """Get winget package version."""
        try:
            result = subprocess.run(
                ["winget", "list", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            lines = result.stdout.strip().split("\n")

            # Skip header lines and find the package entry
            for line in lines:
                if (
                    package_name.lower() in line.lower()
                    and not line.startswith("Name")
                    and not line.startswith("-")
                    and line.strip()
                ):
                    # Split by multiple spaces/tabs to handle formatted output
                    import re

                    parts = re.split(r"\s{2,}", line.strip())

                    # Winget output format: Name, Id, Version, Available, Source
                    # Look for version-like string (contains numbers and dots)
                    for part in parts:
                        if re.match(r"^\d+[\d\.\-\w]*$", part.strip()):
                            return part.strip()

                    # Fallback: if we have at least 3 parts, assume 3rd is version
                    if len(parts) >= 3:
                        version_candidate = parts[2].strip()
                        # Only return if it looks like a version
                        if re.match(r"[\d\.\-\w]+", version_candidate):
                            return version_candidate

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
            result = subprocess.run(
                ["sudo", "apt", "install", "-y", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            console.print(f"{SYMBOLS['success']} Successfully installed {package_name}")
            _logger.log_success(package_name, "apt", result.stdout, result.stderr)
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
                console.print(f"{SYMBOLS['error']} Failed to install {package_name}")
            _logger.log_failure(package_name, "apt", stderr, stdout)
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
            console.print(f"❌ Failed to uninstall {package_name}")
            _logger.log_failure(package_name, "apt", e.stderr or "", e.stdout or "")
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
            console.print(f"❌ Failed to upgrade {package_name}")
            _logger.log_failure(package_name, "apt", e.stderr or "", e.stdout or "")
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
            console.print("❌ Failed to upgrade packages")
            _logger.log_failure("(all)", "apt", e.stderr or "", e.stdout or "")
            return False

    def setup_repo(self, package_name: str, repo: Any) -> bool:
        """Add apt repo for package_name if not already configured. Idempotent."""
        sources_file = repo.sources_file or f"/etc/apt/sources.list.d/{package_name}.list"
        # Skip if the sources file already exists (repo already configured)
        if Path(sources_file).exists():
            return True

        console.print(f"🔧 Setting up apt repository for [bold]{package_name}[/bold]...")

        # Resolve dynamic values
        distribution = repo.distribution
        if not distribution:
            r = subprocess.run(["lsb_release", "-cs"], capture_output=True, text=True)
            distribution = r.stdout.strip() if r.returncode == 0 else "stable"

        architecture = repo.architecture
        if not architecture:
            r = subprocess.run(["dpkg", "--print-architecture"], capture_output=True, text=True)
            architecture = r.stdout.strip() if r.returncode == 0 else "amd64"

        keyring_path = repo.keyring_path or f"/usr/share/keyrings/{package_name}-keyring.gpg"
        sources_file = repo.sources_file or f"/etc/apt/sources.list.d/{package_name}.list"

        # 1. Download and install GPG key
        result = subprocess.run(
            f"curl -fsSL {repo.gpg_key_url} | gpg --dearmor | sudo tee {keyring_path} > /dev/null",
            shell=True, capture_output=True, text=True,
        )
        if result.returncode != 0:
            console.print(f"❌ Failed to install GPG key for {package_name}")
            _logger.log_failure(package_name, "apt-repo", result.stderr or "", result.stdout or "")
            return False

        # 2. Write sources.list.d entry
        repo_line = (
            f"deb [arch={architecture} signed-by={keyring_path}] "
            f"{repo.repo_url} {distribution} {repo.components}"
        )
        result = subprocess.run(
            f'echo "{repo_line}" | sudo tee {sources_file}',
            shell=True, capture_output=True, text=True,
        )
        if result.returncode != 0:
            console.print(f"❌ Failed to write sources file for {package_name}")
            _logger.log_failure(package_name, "apt-repo", result.stderr or "", result.stdout or "")
            return False

        # 3. apt update to pick up the new source
        result = subprocess.run(["sudo", "apt", "update"], capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"❌ apt update failed after adding repo for {package_name}")
            _logger.log_failure(package_name, "apt-repo", result.stderr or "", result.stdout or "")
            return False

        console.print(f"✅ Repository configured for {package_name}")
        return True

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via apt."""
        result = _run(["dpkg", "-l", package_name])
        return result.returncode == 0 and "ii" in result.stdout

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
            console.print(f"{SYMBOLS['success']} Successfully installed {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            stdout = e.stdout.strip() if e.stdout else ""

            # Check for specific poetry errors
            if "Could not find a matching version" in stderr or "not found" in stderr:
                console.print(f"❌ Package '{package_name}' not found on PyPI")
                console.print(
                    "💡 [dim]Check package name or try searching PyPI directly[/dim]"
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
                console.print("❌ Poetry lock file is outdated")
                console.print("💡 [dim]Try: poetry lock --no-update[/dim]")
            else:
                console.print(f"{SYMBOLS['error']} Failed to install {package_name}")
            _logger.log_failure(package_name, "poetry", stderr, stdout)
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
            console.print(f"❌ Failed to uninstall {package_name}")
            _logger.log_failure(package_name, "poetry", e.stderr or "", e.stdout or "")
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
            console.print(f"❌ Failed to upgrade {package_name}")
            _logger.log_failure(package_name, "poetry", e.stderr or "", e.stdout or "")
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
            console.print("❌ Failed to upgrade packages")
            _logger.log_failure("(all)", "poetry", e.stderr or "", e.stdout or "")
            return False

    def is_installed(self, package_name: str) -> bool:
        """Check if package is in poetry project."""
        result = _run(["poetry", "show", package_name], cwd=self.project_path)
        return result.returncode == 0

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


class SnapManager(PackageManager):
    """Snap package manager for Linux."""

    def install(self, package_name: str) -> bool:
        """Install package using snap, retrying with --classic on confinement error."""
        try:
            result = _run(["sudo", "snap", "install", package_name])
            if result.returncode == 0:
                if "already installed" in result.stderr:
                    # snap suggests refresh instead — run it
                    result = _run(["sudo", "snap", "refresh", package_name])
                console.print(f"{SYMBOLS['success']} Successfully installed {package_name}")
                _logger.log_success(package_name, "snap", result.stdout, result.stderr)
                return True
            if "classic confinement" in result.stderr or "--classic" in result.stderr:
                result2 = _run(["sudo", "snap", "install", "--classic", package_name])
                if result2.returncode == 0:
                    console.print(f"{SYMBOLS['success']} Successfully installed {package_name}")
                    _logger.log_success(package_name, "snap", result2.stdout, result2.stderr)
                    return True
                console.print(f"{SYMBOLS['error']} Failed to install {package_name}")
                _logger.log_failure(package_name, "snap", result2.stderr or "", result2.stdout or "")
                return False
            console.print(f"{SYMBOLS['error']} Failed to install {package_name}")
            _logger.log_failure(package_name, "snap", result.stderr or "", result.stdout or "")
            return False
        except Exception as e:
            console.print(f"{SYMBOLS['error']} Failed to install {package_name}: {e}")
            _logger.log_failure(package_name, "snap", str(e))
            return False

    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using snap."""
        try:
            subprocess.run(["sudo", "snap", "remove", package_name], capture_output=True, text=True, check=True)
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}")
            _logger.log_failure(package_name, "snap", e.stderr or "", e.stdout or "")
            return False

    def upgrade(self, package_name: str) -> bool:
        """Upgrade package using snap."""
        try:
            subprocess.run(["sudo", "snap", "refresh", package_name], capture_output=True, text=True, check=True)
            console.print(f"✅ Successfully upgraded {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to upgrade {package_name}")
            _logger.log_failure(package_name, "snap", e.stderr or "", e.stdout or "")
            return False

    def upgrade_all(self) -> bool:
        """Upgrade all snap packages."""
        try:
            subprocess.run(["sudo", "snap", "refresh"], capture_output=True, text=True, check=True)
            console.print("✅ Successfully upgraded all snap packages")
            return True
        except subprocess.CalledProcessError as e:
            console.print("❌ Failed to upgrade snap packages")
            _logger.log_failure("(all)", "snap", e.stderr or "", e.stdout or "")
            return False

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via snap."""
        result = _run(["snap", "list", package_name])
        return result.returncode == 0

    def get_version(self, package_name: str) -> Optional[str]:
        """Get snap package version (column 2 of snap list output)."""
        result = subprocess.run(["snap", "list", package_name], capture_output=True, text=True)
        if result.returncode != 0:
            return None
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]
        return None

    def list_installed(self) -> List[str]:
        """List all installed snap packages."""
        result = subprocess.run(["snap", "list"], capture_output=True, text=True)
        if result.returncode != 0:
            return []
        packages = []
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:  # skip header
            parts = line.split()
            if parts:
                packages.append(parts[0])
        return packages


class PipxManager(PackageManager):
    """pipx package manager for Python CLI tools."""

    def install(self, package_name: str) -> bool:
        """Install package using pipx."""
        try:
            result = subprocess.run(["pipx", "install", package_name], capture_output=True, text=True, check=True)
            console.print(f"{SYMBOLS['success']} Successfully installed {package_name}")
            _logger.log_success(package_name, "pipx", result.stdout, result.stderr)
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"{SYMBOLS['error']} Failed to install {package_name}")
            _logger.log_failure(package_name, "pipx", e.stderr or "", e.stdout or "")
            return False

    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using pipx."""
        try:
            subprocess.run(["pipx", "uninstall", package_name], capture_output=True, text=True, check=True)
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}")
            _logger.log_failure(package_name, "pipx", e.stderr or "", e.stdout or "")
            return False

    def upgrade(self, package_name: str) -> bool:
        """Upgrade package using pipx."""
        try:
            subprocess.run(["pipx", "upgrade", package_name], capture_output=True, text=True, check=True)
            console.print(f"✅ Successfully upgraded {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to upgrade {package_name}")
            _logger.log_failure(package_name, "pipx", e.stderr or "", e.stdout or "")
            return False

    def upgrade_all(self) -> bool:
        """Upgrade all pipx packages."""
        try:
            subprocess.run(["pipx", "upgrade-all"], capture_output=True, text=True, check=True)
            console.print("✅ Successfully upgraded all pipx packages")
            return True
        except subprocess.CalledProcessError as e:
            console.print("❌ Failed to upgrade pipx packages")
            _logger.log_failure("(all)", "pipx", e.stderr or "", e.stdout or "")
            return False

    def _list_json(self) -> dict:
        """Return parsed pipx list --json output, or empty dict on failure."""
        result = subprocess.run(["pipx", "list", "--json"], capture_output=True, text=True)
        if result.returncode != 0:
            return {}
        try:
            import json
            return json.loads(result.stdout).get("venvs", {})
        except Exception:
            return {}

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via pipx."""
        return package_name in self._list_json()

    def get_version(self, package_name: str) -> Optional[str]:
        """Get pipx package version."""
        venvs = self._list_json()
        entry = venvs.get(package_name)
        if not entry:
            return None
        try:
            return entry["metadata"]["main_package"]["package_version"]
        except (KeyError, TypeError):
            return None

    def list_installed(self) -> List[str]:
        """List all installed pipx packages."""
        return list(self._list_json().keys())


class CargoManager(PackageManager):
    """Cargo package manager for Rust tools."""

    def _installed_map(self) -> dict:
        """Return dict of package_name -> version from cargo install --list."""
        result = _run(["cargo", "install", "--list"])
        packages = {}
        if result.returncode != 0:
            return packages
        current_pkg = None
        for line in result.stdout.splitlines():
            if line and not line.startswith(" "):
                # Format: "package_name version:"
                parts = line.split()
                if parts:
                    current_pkg = parts[0]
                    version = parts[1].strip(":") if len(parts) > 1 else None
                    packages[current_pkg] = version
        return packages

    def install(self, package_name: str) -> bool:
        """Install package using cargo."""
        try:
            result = subprocess.run(["cargo", "install", package_name], capture_output=True, text=True, check=True)
            console.print(f"{SYMBOLS['success']} Successfully installed {package_name}")
            _logger.log_success(package_name, "cargo", result.stdout, result.stderr)
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"{SYMBOLS['error']} Failed to install {package_name}")
            _logger.log_failure(package_name, "cargo", e.stderr or "", e.stdout or "")
            return False

    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using cargo."""
        try:
            subprocess.run(["cargo", "uninstall", package_name], capture_output=True, text=True, check=True)
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}")
            _logger.log_failure(package_name, "cargo", e.stderr or "", e.stdout or "")
            return False

    def upgrade(self, package_name: str) -> bool:
        """Upgrade package by reinstalling via cargo."""
        return self.install(package_name)

    def upgrade_all(self) -> bool:
        """Upgrade all cargo packages using cargo-update if available."""
        result = subprocess.run(["cargo", "install-update", "-a"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("✅ Successfully upgraded all cargo packages")
            return True
        console.print("ℹ️  cargo-update not available. Install it with: cargo install cargo-update")
        return False

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed via cargo."""
        return package_name in self._installed_map()

    def get_version(self, package_name: str) -> Optional[str]:
        """Get cargo package version."""
        return self._installed_map().get(package_name)

    def list_installed(self) -> List[str]:
        """List all cargo-installed packages."""
        return list(self._installed_map().keys())


class AsdfManager(PackageManager):
    """asdf version manager."""

    def install(self, package_name: str, version: str = "latest") -> bool:
        """Install plugin, then install and set global version."""
        # Add plugin (idempotent)
        subprocess.run(["asdf", "plugin", "add", package_name], capture_output=True, text=True)
        try:
            subprocess.run(["asdf", "install", package_name, version], capture_output=True, text=True, check=True)
            subprocess.run(["asdf", "global", package_name, version], capture_output=True, text=True, check=True)
            console.print(f"{SYMBOLS['success']} Successfully installed {package_name} {version}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"{SYMBOLS['error']} Failed to install {package_name}")
            _logger.log_failure(package_name, "asdf", e.stderr or "", e.stdout or "")
            return False

    def uninstall(self, package_name: str) -> bool:
        """Uninstall current version of package via asdf."""
        version = self.get_version(package_name)
        if not version:
            console.print(f"❌ No version found for {package_name}")
            return False
        try:
            subprocess.run(["asdf", "uninstall", package_name, version], capture_output=True, text=True, check=True)
            console.print(f"✅ Successfully uninstalled {package_name} {version}")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"❌ Failed to uninstall {package_name}")
            _logger.log_failure(package_name, "asdf", e.stderr or "", e.stdout or "")
            return False

    def upgrade(self, package_name: str) -> bool:
        """Upgrade package to latest via asdf."""
        return self.install(package_name, "latest")

    def upgrade_all(self) -> bool:
        """Upgrade all tracked asdf packages to latest."""
        packages = self.list_installed()
        success = True
        for pkg in packages:
            if not self.upgrade(pkg):
                success = False
        return success

    def is_installed(self, package_name: str) -> bool:
        """Check if package has a current version set in asdf."""
        result = _run(["asdf", "current", package_name])
        if result.returncode != 0:
            return False
        return "No version" not in result.stdout and result.stdout.strip() != ""

    def get_version(self, package_name: str) -> Optional[str]:
        """Get current asdf version of package."""
        result = subprocess.run(["asdf", "current", package_name], capture_output=True, text=True)
        if result.returncode != 0:
            return None
        parts = result.stdout.strip().split()
        if parts and "No" not in parts[0]:
            return parts[1] if len(parts) > 1 else parts[0]
        return None

    def list_installed(self) -> List[str]:
        """List all packages managed by asdf."""
        result = subprocess.run(["asdf", "list"], capture_output=True, text=True)
        if result.returncode != 0:
            return []
        packages = []
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith(" ") and not stripped.startswith("*"):
                packages.append(stripped)
        return packages


class ScriptManager(PackageManager):
    """Custom script-based package manager using definitions in GlobalConfig."""

    def _get_def(self, package_name: str):
        """Return ScriptPackageDef for package, or None.

        Checks Config.script_packages (git-synced) first, then falls back to
        GlobalConfig.custom_packages (local machine only).
        """
        from .config_utils import load_config, load_global_config
        config = load_config()
        if package_name in config.script_packages:
            return config.script_packages[package_name]
        global_config = load_global_config()
        return global_config.custom_packages.get(package_name)

    def _prompt_and_save_def(self, package_name: str, need_install: bool = True):
        """Prompt user for script commands and save to GlobalConfig."""
        from .config_utils import load_global_config, save_global_config
        from .models import ScriptPackageDef

        console.print(f"\n[bold]Define script commands for '{package_name}'[/bold]")
        install_cmd = None
        if need_install:
            install_cmd = input("  Install command (leave blank to track only): ").strip() or None
        uninstall_cmd = input("  Uninstall command (leave blank to skip): ").strip() or None
        check_cmd = input("  Check command (leave blank to assume installed): ").strip() or None
        version_cmd = input("  Version command (leave blank to skip): ").strip() or None

        defn = ScriptPackageDef(
            install_cmd=install_cmd,
            uninstall_cmd=uninstall_cmd,
            check_cmd=check_cmd,
            version_cmd=version_cmd,
        )
        config = load_global_config()
        config.custom_packages[package_name] = defn
        save_global_config(config)
        return defn

    def install(self, package_name: str) -> bool:
        """Install package using custom script."""
        defn = self._get_def(package_name) or self._prompt_and_save_def(package_name)
        if not defn.install_cmd:
            console.print("No install command defined — tracking only")
            return True
        result = subprocess.run(defn.install_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            console.print(f"{SYMBOLS['success']} Successfully installed {package_name}")
            _logger.log_success(package_name, "script", result.stdout, result.stderr)
            return True
        console.print(f"{SYMBOLS['error']} Install command failed for {package_name}")
        _logger.log_failure(package_name, "script", result.stderr or "", result.stdout or "")
        return False

    def uninstall(self, package_name: str) -> bool:
        """Uninstall package using custom script."""
        defn = self._get_def(package_name) or self._prompt_and_save_def(package_name, need_install=False)
        if not defn.uninstall_cmd:
            console.print(f"No uninstall command defined for {package_name}")
            return False
        result = subprocess.run(defn.uninstall_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            console.print(f"✅ Successfully uninstalled {package_name}")
            return True
        console.print(f"❌ Uninstall command failed for {package_name}")
        _logger.log_failure(package_name, "script", result.stderr or "", result.stdout or "")
        return False

    def upgrade(self, package_name: str) -> bool:
        """Upgrade package by re-running install command."""
        return self.install(package_name)

    def upgrade_all(self) -> bool:
        """Not meaningful for script manager."""
        return False

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed using check_cmd, or assume installed."""
        defn = self._get_def(package_name)
        if not defn or not defn.check_cmd:
            return True
        result = subprocess.run(defn.check_cmd, shell=True, capture_output=True)
        return result.returncode == 0

    def get_version(self, package_name: str) -> Optional[str]:
        """Get package version using version_cmd."""
        defn = self._get_def(package_name)
        if not defn or not defn.version_cmd:
            return None
        result = subprocess.run(defn.version_cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    def list_installed(self) -> List[str]:
        """List all script-managed packages that pass is_installed check."""
        from .config_utils import load_config, load_global_config
        all_names: set = set()
        all_names.update(load_config().script_packages.keys())
        all_names.update(load_global_config().custom_packages.keys())
        return [name for name in sorted(all_names) if self.is_installed(name)]


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
            elif manager_type == "snap":
                cls._managers[manager_type] = SnapManager()
            elif manager_type == "pipx":
                cls._managers[manager_type] = PipxManager()
            elif manager_type == "cargo":
                cls._managers[manager_type] = CargoManager()
            elif manager_type == "asdf":
                cls._managers[manager_type] = AsdfManager()
            elif manager_type == "script":
                cls._managers[manager_type] = ScriptManager()
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
