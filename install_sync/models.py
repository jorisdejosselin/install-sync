"""Data models for install-sync."""

import hashlib
import platform
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MachineProfile(BaseModel):
    """Machine profile information."""

    profile_id: str = Field(..., description="Unique machine identifier")
    machine_name: str = Field(..., description="Machine hostname")
    os_type: str = Field(..., description="Operating system type")
    architecture: str = Field(..., description="Machine architecture")

    @classmethod
    def create_current(cls) -> "MachineProfile":
        """Create profile for current machine."""
        from .config_utils import load_global_config

        global_config = load_global_config()

        os_type = platform.system().lower()
        machine_name = platform.node()
        architecture = platform.machine()

        if global_config.profile_id_override:
            return cls(
                profile_id=global_config.profile_id_override,
                machine_name=machine_name,
                os_type=os_type,
                architecture=architecture,
            )

        # Generate unique profile ID
        unique_str = f"{machine_name}_{os_type}_{architecture}"
        profile_id = hashlib.md5(unique_str.encode()).hexdigest()[:8]

        return cls(
            profile_id=profile_id,
            machine_name=machine_name,
            os_type=os_type,
            architecture=architecture,
        )


class PackageInfo(BaseModel):
    """Information about an installed package."""

    name: str = Field(..., description="Package name")
    package_manager: str = Field(..., description="Package manager used")
    installed_at: datetime = Field(
        default_factory=datetime.now, description="Installation timestamp"
    )
    version: Optional[str] = Field(None, description="Package version")


class GitConfig(BaseModel):
    """Git configuration settings."""

    auto_commit: bool = True
    auto_push: bool = True
    commit_message_template: str = "Install {package} on {machine}"


class Config(BaseModel):
    """Main configuration model."""

    machines: Dict[str, MachineProfile] = Field(default_factory=dict)
    packages: Dict[str, List[PackageInfo]] = Field(default_factory=dict)
    git: GitConfig = Field(default_factory=lambda: GitConfig())
    apt_repos: Dict[str, "AptRepoConfig"] = Field(default_factory=dict)
    script_packages: Dict[str, "ScriptPackageDef"] = Field(default_factory=dict)

    def get_current_machine_packages(self, profile_id: str) -> List[PackageInfo]:
        """Get packages for current machine."""
        return self.packages.get(profile_id, [])

    def add_package(self, profile_id: str, package: PackageInfo) -> bool:
        """Add or update package. Returns True if config actually changed."""
        if profile_id not in self.packages:
            self.packages[profile_id] = []

        existing = next(
            (p for p in self.packages[profile_id] if p.name == package.name), None
        )
        if existing:
            if (
                existing.version == package.version
                and existing.package_manager == package.package_manager
            ):
                return False  # Nothing changed — don't write or commit
            # Update in place (version or manager changed)
            self.packages[profile_id] = [
                package if p.name == package.name else p
                for p in self.packages[profile_id]
            ]
        else:
            self.packages[profile_id].append(package)
        return True

    def is_package_installed(self, profile_id: str, package_name: str) -> bool:
        """Check if package is installed on machine."""
        packages = self.get_current_machine_packages(profile_id)
        return any(pkg.name == package_name for pkg in packages)


class AptRepoConfig(BaseModel):
    """Structured apt repository definition (stored in config.json, git-synced)."""

    gpg_key_url: str                          # URL to download the GPG signing key
    repo_url: str                             # Base URL of the apt repository
    distribution: Optional[str] = None       # e.g. "focal"; auto-detected if None
    components: str = "main"                  # repo component(s)
    architecture: Optional[str] = None       # e.g. "amd64"; auto-detected if None
    sources_file: Optional[str] = None       # auto-derived: /etc/apt/sources.list.d/<pkg>.list
    keyring_path: Optional[str] = None       # auto-derived: /usr/share/keyrings/<pkg>-keyring.gpg


class ScriptPackageDef(BaseModel):
    """Custom script-based package definition stored in GlobalConfig."""

    install_cmd: Optional[str] = None
    uninstall_cmd: Optional[str] = None
    check_cmd: Optional[str] = None
    version_cmd: Optional[str] = None


class GlobalConfig(BaseModel):
    """Global user configuration stored in ~/.install-sync.config"""

    git_auto_commit: Optional[bool] = None
    git_auto_push: Optional[bool] = None
    git_prompt: bool = True
    prefer_ssh_remotes: bool = True  # Default to SSH for better security
    git_auto_sync: bool = True  # Always auto-pull before push operations
    git_auto_sync_on_list: bool = False  # Auto-sync when listing packages
    default_tracking_directory: Optional[str] = None
    package_managers: Dict[str, str] = Field(default_factory=dict)
    profile_id_override: Optional[str] = None  # Per-machine profile ID override
    custom_packages: Dict[str, ScriptPackageDef] = Field(default_factory=dict)
    show_error_output: bool = True   # show raw stderr in CLI when a package fails
    verbose_logging: bool = False    # write all command output to log file


class RepoConfig(BaseModel):
    """Repository configuration."""

    platform: str = Field(..., description="Git platform (github/gitlab)")
    repo_name: str = Field(..., description="Repository name")
    clone_url: str = Field(..., description="Repository clone URL")
    tracking_directory: Optional[str] = Field(
        None, description="Local tracking directory path"
    )
    created_at: datetime = Field(default_factory=datetime.now)
