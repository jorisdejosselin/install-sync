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
        os_type = platform.system().lower()
        machine_name = platform.node()
        architecture = platform.machine()

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

    def get_current_machine_packages(self, profile_id: str) -> List[PackageInfo]:
        """Get packages for current machine."""
        return self.packages.get(profile_id, [])

    def add_package(self, profile_id: str, package: PackageInfo) -> None:
        """Add package to machine profile."""
        if profile_id not in self.packages:
            self.packages[profile_id] = []
        self.packages[profile_id].append(package)

    def is_package_installed(self, profile_id: str, package_name: str) -> bool:
        """Check if package is installed on machine."""
        packages = self.get_current_machine_packages(profile_id)
        return any(pkg.name == package_name for pkg in packages)


class GlobalConfig(BaseModel):
    """Global user configuration stored in ~/.install-sync.config"""

    git_auto_commit: Optional[bool] = None
    git_auto_push: Optional[bool] = None
    git_prompt: bool = True
    prefer_ssh_remotes: bool = True  # Default to SSH for better security
    default_tracking_directory: Optional[str] = None
    package_managers: Dict[str, str] = Field(default_factory=dict)


class RepoConfig(BaseModel):
    """Repository configuration."""

    platform: str = Field(..., description="Git platform (github/gitlab)")
    repo_name: str = Field(..., description="Repository name")
    clone_url: str = Field(..., description="Repository clone URL")
    tracking_directory: Optional[str] = Field(
        None, description="Local tracking directory path"
    )
    created_at: datetime = Field(default_factory=datetime.now)
