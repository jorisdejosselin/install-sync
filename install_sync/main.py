"""Main CLI application for install-sync."""

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typer import Context

from . import logger as _logger
from .config_utils import load_global_config, save_global_config
from .git_manager import GitManager
from .models import AptRepoConfig, Config, GitConfig, GlobalConfig, MachineProfile, PackageInfo, ScriptPackageDef
from .package_managers import PackageManagerFactory
from .repo_manager import RepoManager
from .symbols import SYMBOLS

app = typer.Typer(
    name="install-sync",
    help="Cross-platform software installation manager with git tracking",
    rich_markup_mode="rich",
)

console = Console()


# Global state
config_path = Path("config.json")
repo_config_path = Path("repo-config.json")
current_dir = Path.cwd()

# Global flags
_debug_mode = False
_session_git_options = {"no_git": False, "auto_git": False}


def set_debug_mode(enabled: bool) -> None:
    """Set global debug mode."""
    global _debug_mode
    _debug_mode = enabled


def is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    return _debug_mode


def debug_print(message: str) -> None:
    """Print debug message if debug mode is enabled."""
    if _debug_mode:
        console.print(f"🐛 [dim]{message}[/dim]")


def load_global_config_with_debug() -> GlobalConfig:
    """Load global configuration with debug output."""
    try:
        config = load_global_config()
        _logger.setup(
            show_error_output_=config.show_error_output,
            verbose_logging_=config.verbose_logging,
        )
        debug_print("Loaded global configuration")
        return config
    except Exception as e:
        debug_print(f"Failed to load global config: {e}")
        _logger.setup()
        return GlobalConfig()


def save_global_config_with_debug(config: GlobalConfig) -> None:
    """Save global configuration with debug output."""
    try:
        save_global_config(config)
        debug_print("Saved global configuration")
    except Exception as e:
        console.print(f"⚠️  Failed to save global config: {e}")


def _apply_git_flags(no_git: bool, yes: bool) -> None:
    """Override session git options from subcommand flags."""
    global _session_git_options
    if no_git:
        _session_git_options["no_git"] = True
    if yes:
        _session_git_options["auto_git"] = True


def should_perform_git_operations() -> bool:
    """Determine if git operations should be performed based on config."""
    from rich.prompt import Confirm

    global_config = load_global_config_with_debug()

    # Check CLI overrides first
    if _session_git_options["no_git"]:
        debug_print("Git operations disabled by --no-git flag")
        return False

    if _session_git_options["auto_git"]:
        debug_print("Git operations enabled by --auto-git flag")
        return True

    # Check global config
    if global_config.git_auto_commit is False or global_config.git_auto_push is False:
        debug_print("Git operations disabled by global config")
        return False

    # If prompting is enabled, ask user
    if global_config.git_prompt:
        return bool(Confirm.ask("📝 Commit and push this change to git?", default=True))

    # Default behavior
    return True


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: Context,
    debug: bool = typer.Option(
        False, "--debug", help="Enable debug mode for verbose output"
    ),
    no_git: bool = typer.Option(False, "--no-git", help="Skip git operations"),
    auto_git: bool = typer.Option(
        False, "--auto-git", help="Auto-commit and push without prompts"
    ),
) -> None:
    """Main callback to handle global options."""
    if debug:
        set_debug_mode(True)
        debug_print("Debug mode enabled")

    # Store git preferences globally for this session
    global _session_git_options
    _session_git_options = {"no_git": no_git, "auto_git": auto_git}

    # Show help when no command is provided
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


def _create_gitignore() -> None:
    """Create .gitignore file for the repository."""
    gitignore_content = """# install-sync local configuration files (not synced)
repo-config.json

# Temporary and cache files
*.tmp
*.temp
*.bak
*.log
.DS_Store
.DS_Store?
._*
Thumbs.db
ehthumbs.db

# Note: config.json IS tracked (contains package data to sync across machines)
"""

    gitignore_path = Path(".gitignore")
    if not gitignore_path.exists():
        with open(gitignore_path, "w") as f:
            f.write(gitignore_content)
        console.print("📄 Created .gitignore file")


def _create_readme(repo_name: str) -> None:
    """Create README.md for the repository."""
    readme_content = f"""# {repo_name}

Personal software package tracking across multiple machines using
[install-sync](https://github.com/jorisdejosselin/install-sync).

## Files

- `config.json` - Package tracking configuration and data
- `.gitignore` - Git ignore rules (excludes sensitive config files)

## Usage

To manage packages on this machine:

```bash
# Install and track a package
install-sync install <package-name>

# List packages on current machine
install-sync list

# List packages on all machines
install-sync list --all

# Show machine information
install-sync info

# Sync with this repository
install-sync sync
```

## Machine Tracking

This repository automatically tracks:
- Package names and versions
- Installation timestamps
- Machine identification (OS, architecture, hostname)
- Package manager used (brew, winget, apt, poetry)

## Security

- Repository configuration files are excluded from version control
- Only package names, versions, and installation timestamps are tracked
- No sensitive information or credentials are stored
- Private repository recommended for personal use

## Supported Package Managers

| Platform | Package Manager | Command |
|----------|-----------------|---------|
| macOS | Homebrew | `brew` |
| Windows | Windows Package Manager | `winget` |
| Linux | APT | `apt` |
| Any | Poetry | `poetry` |

Generated by install-sync
"""

    readme_path = Path("README.md")
    if not readme_path.exists():
        with open(readme_path, "w") as f:
            f.write(readme_content)
        console.print("📄 Created README.md")


def get_tracking_directory() -> Path:
    """Get the package tracking directory."""
    debug_print("Determining tracking directory...")

    # Check environment variable first
    env_dir = os.environ.get("INSTALL_SYNC_DIR")
    if env_dir:
        debug_print(f"Using environment variable INSTALL_SYNC_DIR: {env_dir}")
        return Path(env_dir).expanduser().resolve()

    # Check repo config for tracking directory
    try:
        repo_manager = RepoManager(repo_config_path)
        config = repo_manager.get_config()
        if (
            config
            and hasattr(config, "tracking_directory")
            and config.tracking_directory
        ):
            debug_print(
                f"Using tracking directory from repo config: {config.tracking_directory}"
            )
            return Path(config.tracking_directory)
    except Exception:
        debug_print("No repo config found or tracking_directory not set")

    # Check global config for default tracking directory
    try:
        global_config = load_global_config()
        if global_config.default_tracking_directory:
            default_dir = (
                Path(global_config.default_tracking_directory).expanduser().resolve()
            )
            debug_print(
                f"Using default tracking directory from global config: {default_dir}"
            )
            return default_dir
    except Exception:
        debug_print("No global config found or default_tracking_directory not set")

    # IMPORTANT: Prevent source code contamination
    # If we're in the install-sync development directory, use default tracking directory
    if (
        current_dir.name == "install-sync"
        and (current_dir / "pyproject.toml").exists()
        and (current_dir / "install_sync").exists()
    ):
        if is_debug_mode():
            console.print(
                "⚠️  [yellow]Detected development directory - "
                "using default tracking directory[/yellow]"
            )
        default_tracking_dir = Path.home() / "package-tracking"
        if is_debug_mode():
            console.print(f"📁 [blue]Switched to: {default_tracking_dir}[/blue]")
        debug_print(f"Development directory detected, using: {default_tracking_dir}")
        return default_tracking_dir

    # Final fallback: use ~/package-tracking as sensible default
    default_tracking_dir = Path.home() / "package-tracking"
    debug_print(f"Using fallback default tracking directory: {default_tracking_dir}")
    return default_tracking_dir


def load_config() -> Config:
    """Load configuration from file."""
    tracking_dir = get_tracking_directory()
    config_file = tracking_dir / "config.json"

    if config_file.exists():
        with open(config_file, "r") as f:
            data = json.load(f)
            return Config(**data)
    return Config()


def save_config(config: Config) -> None:
    """Save configuration to file."""
    tracking_dir = get_tracking_directory()
    config_file = tracking_dir / "config.json"

    tracking_dir.mkdir(parents=True, exist_ok=True)

    with open(config_file, "w") as f:
        json.dump(config.dict(), f, indent=2, default=str)


def _bulk_install(
    config: Config,
    current_machine: MachineProfile,
    from_machine: Optional[str],
    manager: Optional[str],
    force: bool,
    project_path: Optional[str],
    is_bulk: bool = True,
) -> None:
    """Handle bulk installation of packages from tracked machines."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Confirm

    # Discover packages to install
    packages_to_install = set()
    source_machines = {}  # package_name -> source_machine_info

    if from_machine:
        # Install from specific machine
        target_machine = None
        for profile_id, machine_profile in config.machines.items():
            if (
                machine_profile.machine_name == from_machine
                or profile_id == from_machine
            ):
                target_machine = machine_profile
                target_packages = config.get_current_machine_packages(profile_id)
                break

        if not target_machine:
            console.print(f"❌ Machine '{from_machine}' not found")
            console.print("Available machines:")
            for machine_profile in config.machines.values():
                console.print(
                    f"  • {machine_profile.machine_name} ({machine_profile.profile_id})"
                )
            return

        for pkg in target_packages:
            # Use current machine's default package manager, not the source machine's
            try:
                current_pkg_manager = PackageManagerFactory.get_default_manager()
                manager_name = current_pkg_manager.__class__.__name__.replace(
                    "Manager", ""
                ).lower()
                packages_to_install.add((pkg.name, manager_name))
                source_machines[pkg.name] = target_machine
            except ValueError:
                # Skip if no suitable package manager for current machine
                debug_print(
                    f"Skipping {pkg.name} - no suitable package manager for current machine"
                )

        console.print(
            f"📦 Found {len(packages_to_install)} packages from {target_machine.machine_name}"
        )
    else:
        # Install packages for current machine only
        machine_packages = config.get_current_machine_packages(current_machine.profile_id)
        for pkg in machine_packages:
            # Use the original package manager from the JSON for current machine
            packages_to_install.add((pkg.name, pkg.package_manager))
            source_machines[pkg.name] = current_machine

        console.print(
            f"📦 Found {len(packages_to_install)} packages for current machine"
        )

    if not packages_to_install:
        console.print("📦 No packages found to install")
        return

    # Show preview and get confirmation
    console.print("\n📋 [bold]Packages to install:[/bold]")

    # Group by package manager for better display
    by_manager: Dict[str, List[str]] = defaultdict(list)
    for pkg_name, pkg_manager in packages_to_install:
        # Defensive coding: ensure we have a list even if defaultdict fails
        if pkg_manager not in by_manager:
            by_manager[pkg_manager] = []
        by_manager[pkg_manager].append(pkg_name)

    for pkg_manager_name, pkg_list in by_manager.items():
        console.print(f"\n  [bold magenta]{pkg_manager_name.upper()}:[/bold magenta]")
        for pkg_name in sorted(pkg_list):
            console.print(f"    • {pkg_name}")

    if not force and not Confirm.ask(
        f"\nInstall {len(packages_to_install)} packages?", default=True
    ):
        console.print("❌ Installation cancelled")
        return

    # Install packages
    _logger.clear_recent_errors()
    successful_installs: List[str] = []
    failed_installs: List[str] = []
    skipped_installs: List[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for i, (pkg_name, pkg_manager_name) in enumerate(packages_to_install, 1):
            task = progress.add_task(
                f"Installing {pkg_name} ({i} / {len(packages_to_install)})", total=1
            )

            try:
                # For bulk install (--all), skip the "already installed" check since
                # we want to restore packages on a clean/new machine

                # Get package manager instance and install the package
                if manager:
                    # Use specified manager override
                    if manager == "poetry" and project_path:
                        pkg_manager_instance = PackageManagerFactory.get_manager(
                            manager, project_path=Path(project_path)
                        )
                    else:
                        pkg_manager_instance = PackageManagerFactory.get_manager(
                            manager
                        )
                    actual_manager = manager
                else:
                    # Use original package manager
                    if pkg_manager_name == "poetry" and project_path:
                        pkg_manager_instance = PackageManagerFactory.get_manager(
                            pkg_manager_name, project_path=Path(project_path)
                        )
                    else:
                        pkg_manager_instance = PackageManagerFactory.get_manager(
                            pkg_manager_name
                        )
                    actual_manager = pkg_manager_name

                # Run apt repo setup if a definition exists for this package
                if actual_manager == "apt" and pkg_name in config.apt_repos:
                    apt_mgr = PackageManagerFactory.get_manager("apt")
                    if not apt_mgr.setup_repo(pkg_name, config.apt_repos[pkg_name]):
                        failed_installs.append(f"{pkg_name} ({actual_manager})")
                        progress.update(task, completed=1)
                        continue

                # Install the package
                if pkg_manager_instance.install(pkg_name):
                    # Get version info
                    version = pkg_manager_instance.get_version(pkg_name)

                    # Record installation (only for single package installs, not bulk)
                    if not is_bulk:
                        package_info = PackageInfo(
                            name=pkg_name, package_manager=actual_manager, version=version
                        )
                        config.add_package(current_machine.profile_id, package_info)

                    successful_installs.append(f"{pkg_name} ({actual_manager})")
                else:
                    failed_installs.append(f"{pkg_name} ({actual_manager})")

            except Exception as e:
                failed_installs.append(f"{pkg_name} ({pkg_manager_name}): {str(e)}")

            progress.update(task, completed=1)

    # Save configuration with all successful installs (only for single installs)
    if successful_installs and not is_bulk:
        save_config(config)

    # Git operations for successful installs
    if successful_installs and should_perform_git_operations():
        try:
            tracking_dir = get_tracking_directory()
            git_manager = GitManager(
                tracking_dir, config.git, debug_mode=is_debug_mode()
            )
            if git_manager.is_git_repo():
                message = (
                    f"Bulk install {len(successful_installs)} packages on "
                    f"{current_machine.machine_name}"
                )
                git_manager.commit_changes(message)
                git_manager.push_changes()
            else:
                console.print(
                    "ℹ️  Not a git repository. Run 'install-sync repo setup' "
                    "to enable git tracking."
                )
        except Exception as e:
            console.print(f"⚠️  Git operations failed: {e}")

    # Show summary
    console.print("\n📊 [bold]Installation Summary:[/bold]")

    if successful_installs:
        console.print(f"✅ [green]Installed ({len(successful_installs)}):[/green]")
        for pkg_info in successful_installs:
            console.print(f"  • {pkg_info}")

    if skipped_installs:
        console.print(f"\n⏭️  [yellow]Skipped ({len(skipped_installs)}):[/yellow]")
        for pkg_info in skipped_installs:
            console.print(f"  • {pkg_info}")

    if failed_installs:
        console.print(f"\n❌ [red]Failed ({len(failed_installs)}):[/red]")
        for pkg_info in failed_installs:
            console.print(f"  • {pkg_info}")
            pkg_name = pkg_info.split(" (")[0]
            err = _logger.get_recent_error(pkg_name)
            if err:
                first_line = err.splitlines()[0]
                console.print(f"    [dim]{first_line}[/dim]")
        console.print(f"\n[dim]Full error log: {_logger.LOG_FILE}[/dim]")

    console.print("✅ Bulk installation completed!")


@app.command()
def install(
    packages: Optional[List[str]] = typer.Argument(
        None, help="Package name(s) to install (omit to use --all)"
    ),
    manager: Optional[str] = typer.Option(
        None,
        "--manager",
        "-m",
        help="Package manager to use (brew, winget, apt, poetry, snap, pipx, cargo, asdf, npm, script)",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force installation even if already installed"
    ),
    project_path: Optional[str] = typer.Option(
        None, "--project", "-p", help="Project path for poetry manager"
    ),
    all_packages: bool = typer.Option(
        False, "--all", help="Install all packages from tracked machines"
    ),
    from_machine: Optional[str] = typer.Option(
        None,
        "--from-machine",
        help="Install packages from specific machine (use with --all)",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show full command output for this run"
    ),
    no_git: bool = typer.Option(False, "--no-git", help="Skip git operations"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm git commit/push"),
) -> None:
    """Install a package using the appropriate package manager."""
    _apply_git_flags(no_git, yes)
    # Validation: ensure either packages or --all is provided, not both
    if all_packages and packages:
        console.print("❌ Cannot specify both a package name and --all flag")
        raise typer.Exit(1)

    if not all_packages and not packages:
        console.print("❌ Must specify either a package name or use --all flag")
        raise typer.Exit(1)

    config = load_config()
    machine = MachineProfile.create_current()

    if verbose:
        _logger.show_error_output = True
        _logger.verbose_logging = True

    # Update machine profile
    config.machines[machine.profile_id] = machine

    if all_packages:
        # Handle bulk installation
        _bulk_install(config, machine, from_machine, manager, force, project_path)
        return

    # Resolve package manager once for all packages
    assert packages is not None
    try:
        if manager:
            if manager == "poetry" and project_path:
                pkg_manager = PackageManagerFactory.get_manager(
                    manager, project_path=Path(project_path)
                )
            else:
                pkg_manager = PackageManagerFactory.get_manager(manager)
        else:
            pkg_manager = PackageManagerFactory.get_default_manager()
            manager = pkg_manager.__class__.__name__.replace("Manager", "").lower()
    except ValueError as e:
        console.print(f"❌ {e}")
        raise typer.Exit(1)

    failed = []
    installed = []
    for package in packages:
        # Check if already installed (both tracked AND actually on the system)
        if not force and config.is_package_installed(machine.profile_id, package):
            if pkg_manager.is_installed(package):
                version = pkg_manager.get_version(package)
                ver_str = f" ({version})" if version else ""
                console.print(f"📦 Package [bold]{package}[/bold] is already installed{ver_str}")
                if verbose:
                    console.print(f"[dim]  manager : {manager}[/dim]")
                    console.print(f"[dim]  verified: found on system via {manager}[/dim]")
                    console.print(f"[dim]  tip     : use --force to reinstall[/dim]")
                continue
            # Tracked but not present on system — fall through to reinstall

        # Run apt repo setup if a definition exists for this package
        if manager == "apt" and package in config.apt_repos:
            apt_mgr = PackageManagerFactory.get_manager("apt")
            if not apt_mgr.setup_repo(package, config.apt_repos[package]):
                failed.append(package)
                continue

        # Install package
        console.print(
            f"{SYMBOLS['install']} Installing [bold]{package}[/bold] using {manager}..."
        )

        if pkg_manager.install(package):
            version = pkg_manager.get_version(package)
            package_info = PackageInfo(
                name=package, package_manager=manager, version=version
            )
            if config.add_package(machine.profile_id, package_info):
                installed.append(package)
        else:
            failed.append(package)

    # Save config and do a single git commit for all installed packages
    if installed:
        save_config(config)
        if should_perform_git_operations():
            try:
                tracking_dir = get_tracking_directory()
                git_manager = GitManager(
                    tracking_dir, config.git, debug_mode=is_debug_mode()
                )
                if git_manager.is_git_repo():
                    if len(installed) == 1:
                        message = config.git.commit_message_template.format(
                            package=installed[0], machine=machine.machine_name
                        )
                    else:
                        pkgs = ", ".join(installed)
                        message = f"install {pkgs} on {machine.machine_name}"
                    git_manager.commit_changes(message)
                    git_manager.push_changes()
                else:
                    console.print(
                        "ℹ️  Not a git repository. Run 'install-sync repo setup' "
                        "to enable git tracking."
                    )
            except Exception as e:
                console.print(f"⚠️  Git operations failed: {e}")

    if failed:
        raise typer.Exit(1)


@app.command()
def track(
    package: Optional[str] = typer.Argument(None, help="Package name to track"),
    manager: Optional[str] = typer.Option(
        None,
        "--manager",
        "-m",
        help="Package manager used (brew, winget, apt, poetry)",
    ),
    version: Optional[str] = typer.Option(
        None, "--version", "-v", help="Package version (auto-detected if not provided)"
    ),
    no_git: bool = typer.Option(False, "--no-git", help="Skip git operations"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm git commit/push"),
) -> None:
    """Track an already installed package without installing it."""
    _apply_git_flags(no_git, yes)
    if package is None:
        console.print(" Usage: install-sync track [OPTIONS] PACKAGE")
        console.print("")
        console.print(" Track an already installed package without installing it.")
        console.print("")
        console.print("")
        console.print(
            "╭─ Arguments ──────────────────────────────────────────────────────────────────╮"
        )
        console.print(
            "│ *    package      TEXT  Package name to track [required]                    │"
        )
        console.print(
            "╰──────────────────────────────────────────────────────────────────────────────╯"
        )
        console.print(
            "╭─ Options ────────────────────────────────────────────────────────────────────╮"
        )
        console.print(
            "│ --manager  -m      TEXT  Package manager used (brew, winget, apt, poetry)   │"
        )
        console.print(
            "│ --version  -v      TEXT  Package version (auto-detected if not provided)    │"
        )
        console.print(
            "│ --help                   Show this message and exit.                        │"
        )
        console.print(
            "╰──────────────────────────────────────────────────────────────────────────────╯"
        )
        raise typer.Exit(0)
    config = load_config()
    machine = MachineProfile.create_current()

    # Update machine profile
    config.machines[machine.profile_id] = machine

    # Determine package manager
    try:
        if manager:
            pkg_manager = PackageManagerFactory.get_manager(manager)
        else:
            pkg_manager = PackageManagerFactory.get_default_manager()
            manager = pkg_manager.__class__.__name__.replace("Manager", "").lower()
    except ValueError as e:
        console.print(f"{SYMBOLS['error']} {e}")
        raise typer.Exit(1)

    # Check if package is actually installed
    if not pkg_manager.is_installed(package):
        console.print(
            f"{SYMBOLS['error']} Package [bold]{package}[/bold] is not installed on this system"
        )
        console.print(f"Use 'install-sync install {package}' to install it first")
        raise typer.Exit(1)

    # Get version if not provided
    if not version:
        version = pkg_manager.get_version(package)

    console.print(
        f"{SYMBOLS['package']} Tracking [bold]{package}[/bold] "
        f"(version: {version or 'unknown'}) using {manager}"
    )

    # Add package to tracking
    package_info = PackageInfo(
        name=package,
        package_manager=manager,
        version=version,
    )
    changed = config.add_package(machine.profile_id, package_info)
    if changed:
        save_config(config)

        console.print(
            f"{SYMBOLS['success']} Package [bold]{package}[/bold] is now being tracked"
        )

        # Git operations
        if should_perform_git_operations():
            try:
                tracking_dir = get_tracking_directory()
                if (tracking_dir / ".git").exists():
                    git_manager = GitManager(
                        tracking_dir, config.git, debug_mode=is_debug_mode()
                    )
                    git_manager.commit_changes(
                        f"Track existing package: {package} on {machine.machine_name}"
                    )
                    git_manager.push_changes()
                else:
                    console.print(
                        f"{SYMBOLS['info']} Not a git repository. Run 'install-sync repo setup' "
                        "to enable git tracking."
                    )
            except Exception as e:
                console.print(f"{SYMBOLS['warning']} Git operations failed: {e}")
    else:
        console.print(f"ℹ️  {package} is already tracked with the same version")


@app.command()
def uninstall(
    package: str = typer.Argument(..., help="Package name to uninstall"),
    manager: Optional[str] = typer.Option(
        None,
        "--manager",
        "-m",
        help="Package manager to use (brew, winget, apt, poetry, snap, pipx, cargo, asdf, npm, script)",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force uninstallation even if not tracked"
    ),
    project_path: Optional[str] = typer.Option(
        None, "--project", "-p", help="Project path for poetry manager"
    ),
    no_git: bool = typer.Option(False, "--no-git", help="Skip git operations"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm git commit/push"),
) -> None:
    """Uninstall a package using the appropriate package manager."""
    _apply_git_flags(no_git, yes)
    config = load_config()
    machine = MachineProfile.create_current()

    # Update machine profile
    config.machines[machine.profile_id] = machine

    # Check if package is tracked
    if not force and not config.is_package_installed(machine.profile_id, package):
        console.print(
            f"📦 Package [bold]{package}[/bold] is not tracked in install-sync"
        )
        console.print("💡 Use --force to uninstall anyway")
        return

    # Get package manager
    try:
        if manager:
            if manager == "poetry" and project_path:
                pkg_manager = PackageManagerFactory.get_manager(
                    manager, project_path=Path(project_path)
                )
            else:
                pkg_manager = PackageManagerFactory.get_manager(manager)
        else:
            # Try to determine from tracked packages
            tracked_packages = config.get_current_machine_packages(machine.profile_id)
            tracked_package = next(
                (p for p in tracked_packages if p.name == package), None
            )
            if tracked_package:
                manager = tracked_package.package_manager
                if manager == "poetry" and project_path:
                    pkg_manager = PackageManagerFactory.get_manager(
                        manager, project_path=Path(project_path)
                    )
                else:
                    pkg_manager = PackageManagerFactory.get_manager(manager)
            else:
                pkg_manager = PackageManagerFactory.get_default_manager()
                manager = pkg_manager.__class__.__name__.replace("Manager", "").lower()
    except ValueError as e:
        console.print(f"❌ {e}")
        raise typer.Exit(1)

    # Check if actually installed
    if not pkg_manager.is_installed(package):
        console.print(
            f"📦 Package [bold]{package}[/bold] is not installed via {manager}"
        )
        # Remove from tracking if it exists
        if config.is_package_installed(machine.profile_id, package):
            config.packages[machine.profile_id] = [
                p for p in config.packages[machine.profile_id] if p.name != package
            ]
            save_config(config)
            console.print(f"🗑️  Removed [bold]{package}[/bold] from tracking")
        return

    # Uninstall package
    console.print(f"🗑️  Uninstalling [bold]{package}[/bold] using {manager}...")

    if pkg_manager.uninstall(package):
        # Remove from tracking
        if config.is_package_installed(machine.profile_id, package):
            config.packages[machine.profile_id] = [
                p for p in config.packages[machine.profile_id] if p.name != package
            ]
            save_config(config)
            console.print(f"📝 Removed [bold]{package}[/bold] from tracking")

        # Git operations
        if should_perform_git_operations():
            try:
                tracking_dir = get_tracking_directory()
                debug_print(f"Using tracking directory: {tracking_dir}")

                git_manager = GitManager(
                    tracking_dir, config.git, debug_mode=is_debug_mode()
                )
                if git_manager.is_git_repo():
                    message = f"Uninstall {package} from {machine.machine_name}"
                    git_manager.commit_changes(message)
                    git_manager.push_changes()
                else:
                    console.print(
                        "ℹ️  Not a git repository. Run 'install-sync repo setup' "
                        "to enable git tracking."
                    )
            except Exception as e:
                console.print(f"⚠️  Git operations failed: {e}")
    else:
        raise typer.Exit(1)


@app.command()
def upgrade(
    package: Optional[str] = typer.Argument(
        None, help="Package name to upgrade (if not provided, upgrades all packages)"
    ),
    manager: Optional[str] = typer.Option(
        None,
        "--manager",
        "-m",
        help="Package manager to use (brew, winget, apt, poetry, snap, pipx, cargo, asdf, npm, script)",
    ),
    project_path: Optional[str] = typer.Option(
        None, "--project", "-p", help="Project path for poetry manager"
    ),
) -> None:
    """Upgrade a specific package or all packages."""
    config = load_config()
    machine = MachineProfile.create_current()

    # Update machine profile
    config.machines[machine.profile_id] = machine

    if package:
        # Upgrade specific package
        if not config.is_package_installed(machine.profile_id, package):
            console.print(
                f"📦 Package [bold]{package}[/bold] is not tracked in install-sync"
            )
            console.print("💡 Use 'install-sync install' to add it first")
            return

        # Get package manager
        try:
            if manager:
                if manager == "poetry" and project_path:
                    pkg_manager = PackageManagerFactory.get_manager(
                        manager, project_path=Path(project_path)
                    )
                else:
                    pkg_manager = PackageManagerFactory.get_manager(manager)
            else:
                # Try to determine from tracked packages
                tracked_packages = config.get_current_machine_packages(
                    machine.profile_id
                )
                tracked_package = next(
                    (p for p in tracked_packages if p.name == package), None
                )
                if tracked_package:
                    manager = tracked_package.package_manager
                    if manager == "poetry" and project_path:
                        pkg_manager = PackageManagerFactory.get_manager(
                            manager, project_path=Path(project_path)
                        )
                    else:
                        pkg_manager = PackageManagerFactory.get_manager(manager)
                else:
                    pkg_manager = PackageManagerFactory.get_default_manager()
                    manager = pkg_manager.__class__.__name__.replace(
                        "Manager", ""
                    ).lower()
        except ValueError as e:
            console.print(f"❌ {e}")
            raise typer.Exit(1)

        # Check if actually installed
        if not pkg_manager.is_installed(package):
            console.print(
                f"📦 Package [bold]{package}[/bold] is not installed via {manager}"
            )
            return

        # Store old version
        old_version = pkg_manager.get_version(package)

        # Upgrade package
        console.print(f"⬆️  Upgrading [bold]{package}[/bold] using {manager}...")

        if pkg_manager.upgrade(package):
            # Get new version
            new_version = pkg_manager.get_version(package)

            # Update tracking if version changed
            if old_version != new_version:
                # Update the package info in tracking
                tracked_packages = config.get_current_machine_packages(
                    machine.profile_id
                )
                for i, pkg in enumerate(tracked_packages):
                    if pkg.name == package:
                        config.packages[machine.profile_id][i].version = new_version
                        config.packages[machine.profile_id][
                            i
                        ].installed_at = datetime.now()
                        break

                save_config(config)
                console.print(
                    f"📝 Updated [bold]{package}[/bold] version: {old_version} → {new_version}"
                )

                # Git operations
                if should_perform_git_operations():
                    try:
                        tracking_dir = get_tracking_directory()
                        debug_print(f"Using tracking directory: {tracking_dir}")

                        git_manager = GitManager(
                            tracking_dir, config.git, debug_mode=is_debug_mode()
                        )
                        if git_manager.is_git_repo():
                            message = (
                                f"Upgrade {package} from {old_version} to {new_version} "
                                f"on {machine.machine_name}"
                            )
                            git_manager.commit_changes(message)
                            git_manager.push_changes()
                        else:
                            console.print(
                                "ℹ️  Not a git repository. Run 'install-sync repo setup' "
                                "to enable git tracking."
                            )
                    except Exception as e:
                        console.print(f"⚠️  Git operations failed: {e}")
        else:
            raise typer.Exit(1)

    else:
        # Upgrade all packages
        console.print("⬆️  Upgrading all packages...")

        # Get all unique package managers used
        tracked_packages = config.get_current_machine_packages(machine.profile_id)
        managers_used = set(pkg.package_manager for pkg in tracked_packages)

        if not managers_used:
            console.print("📦 No packages tracked for this machine")
            return

        updated_packages = []

        for manager_name in managers_used:
            try:
                if manager_name == "poetry" and project_path:
                    pkg_manager = PackageManagerFactory.get_manager(
                        manager_name, project_path=Path(project_path)
                    )
                else:
                    pkg_manager = PackageManagerFactory.get_manager(manager_name)

                console.print(f"⬆️  Upgrading {manager_name} packages...")

                # Store old versions
                old_versions = {}
                manager_packages = [
                    pkg
                    for pkg in tracked_packages
                    if pkg.package_manager == manager_name
                ]
                for pkg in manager_packages:
                    old_versions[pkg.name] = pkg_manager.get_version(pkg.name)

                # Upgrade all packages for this manager
                if pkg_manager.upgrade_all():
                    # Check for version changes
                    for pkg in manager_packages:
                        new_version = pkg_manager.get_version(pkg.name)
                        if old_versions[pkg.name] != new_version:
                            # Update tracking
                            for i, tracked_pkg in enumerate(
                                config.packages[machine.profile_id]
                            ):
                                if tracked_pkg.name == pkg.name:
                                    config.packages[machine.profile_id][
                                        i
                                    ].version = new_version
                                    config.packages[machine.profile_id][
                                        i
                                    ].installed_at = datetime.now()
                                    break
                            updated_packages.append(
                                f"{pkg.name}: {old_versions[pkg.name]} → {new_version}"
                            )

            except ValueError as e:
                console.print(f"⚠️  Skipped {manager_name}: {e}")

        if updated_packages:
            save_config(config)
            console.print(f"📝 Updated {len(updated_packages)} packages")

            # Git operations
            if should_perform_git_operations():
                try:
                    tracking_dir = get_tracking_directory()
                    debug_print(f"Using tracking directory: {tracking_dir}")

                    git_manager = GitManager(
                        tracking_dir, config.git, debug_mode=is_debug_mode()
                    )
                    if git_manager.is_git_repo():
                        message = (
                            f"Upgrade {len(updated_packages)} packages "
                            f"on {machine.machine_name}"
                        )
                        git_manager.commit_changes(message)
                        git_manager.push_changes()
                    else:
                        console.print(
                            "ℹ️  Not a git repository. Run 'install-sync repo setup' "
                            "to enable git tracking."
                        )
                except Exception as e:
                    console.print(f"⚠️  Git operations failed: {e}")
        else:
            console.print("ℹ️  All packages are already up to date")


@app.command()
def list(
    all_machines: bool = typer.Option(
        False, "--all", "-a", help="Show packages for all machines"
    )
) -> None:
    """List installed packages."""
    # Auto-sync if enabled
    try:
        tracking_dir = get_tracking_directory()
        if tracking_dir and tracking_dir.exists():
            git_manager = GitManager(
                tracking_dir, GitConfig(), debug_mode=is_debug_mode()
            )
            git_manager.sync_before_operation("listing packages")
    except Exception:
        # If tracking setup fails, continue without sync
        pass

    config = load_config()
    machine = MachineProfile.create_current()

    if all_machines:
        # Show all machines
        for profile_id, machine_profile in config.machines.items():
            packages = config.get_current_machine_packages(profile_id)
            if packages:
                table = Table(
                    title=f"📦 {machine_profile.machine_name} ({machine_profile.os_type})"
                )
                table.add_column("Package", style="cyan")
                table.add_column("Manager", style="magenta")
                table.add_column("Version", style="green")
                table.add_column("Installed", style="yellow")

                for pkg in packages:
                    table.add_row(
                        pkg.name,
                        pkg.package_manager,
                        pkg.version or "Unknown",
                        pkg.installed_at.strftime("%Y-%m-%d %H:%M"),
                    )

                console.print(table)
                console.print()
    else:
        # Show current machine only
        packages = config.get_current_machine_packages(machine.profile_id)
        if packages:
            table = Table(title=f"📦 Packages on {machine.machine_name}")
            table.add_column("Package", style="cyan")
            table.add_column("Manager", style="magenta")
            table.add_column("Version", style="green")
            table.add_column("Installed", style="yellow")

            for pkg in packages:
                table.add_row(
                    pkg.name,
                    pkg.package_manager,
                    pkg.version or "Unknown",
                    pkg.installed_at.strftime("%Y-%m-%d %H:%M"),
                )

            console.print(table)
        else:
            console.print("📦 No packages recorded for this machine")


@app.command()
def sync() -> None:
    """Sync with remote repository."""
    try:
        tracking_dir = get_tracking_directory()
        git_manager = GitManager(tracking_dir, GitConfig(), debug_mode=is_debug_mode())
        if git_manager.is_git_repo():
            git_manager.pull_changes()
            # Reload config after sync
            load_config()
            console.print("✅ Synced with remote repository")
        else:
            console.print(
                "❌ Not a git repository. Run 'install-sync repo setup' first."
            )
    except Exception as e:
        console.print(f"❌ Sync failed: {e}")
        raise typer.Exit(1)


@app.command()
def info() -> None:
    """Show machine and configuration information."""
    config = load_config()
    machine = MachineProfile.create_current()

    # Machine info
    machine_info = f"""
[bold]Machine Information[/bold]
• Name: {machine.machine_name}
• OS: {machine.os_type}
• Architecture: {machine.architecture}
• Profile ID: {machine.profile_id}
"""

    # Package stats
    total_packages = sum(len(packages) for packages in config.packages.values())
    current_packages = len(config.get_current_machine_packages(machine.profile_id))

    stats_info = f"""
[bold]Statistics[/bold]
• Total machines: {len(config.machines)}
• Total packages: {total_packages}
• Packages on this machine: {current_packages}
"""

    # Git info
    try:
        tracking_dir = get_tracking_directory()
        git_manager = GitManager(tracking_dir, config.git, debug_mode=is_debug_mode())
        if git_manager.is_git_repo():
            git_status = "✅ Initialized"
            recent_commits = git_manager.get_commit_history(limit=3)
            if recent_commits:
                git_info = f"""
[bold]Git Repository[/bold]
• Status: {git_status}
• Directory: {tracking_dir}
• Auto-commit: {'✅' if config.git.auto_commit else '❌'}
• Auto-push: {'✅' if config.git.auto_push else '❌'}
• Recent commits: {len(recent_commits)}
"""
            else:
                git_info = f"""
[bold]Git Repository[/bold]
• Status: {git_status}
• Directory: {tracking_dir}
• Auto-commit: {'✅' if config.git.auto_commit else '❌'}
• Auto-push: {'✅' if config.git.auto_push else '❌'}
"""
        else:
            git_info = f"""
[bold]Git Repository[/bold]
• Status: ❌ Not initialized
• Directory: {tracking_dir}
• Run 'install-sync repo setup' to enable git tracking
"""
    except Exception:
        tracking_dir = get_tracking_directory()
        git_info = f"""
[bold]Git Repository[/bold]
• Status: ❌ Error accessing repository
• Directory: {tracking_dir}
"""

    console.print(Panel(machine_info, title="🖥️  Machine", border_style="blue"))
    console.print(Panel(stats_info, title="📊 Statistics", border_style="green"))
    console.print(Panel(git_info, title="🔧 Git", border_style="yellow"))


# Machine management commands
machine_app = typer.Typer(name="machine", help="Machine profile management")
app.add_typer(machine_app, name="machine")


@machine_app.callback(invoke_without_command=True)
def machine_callback(ctx: Context) -> None:
    """Machine profile management commands."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


def _adopt_profile_interactive(config: "Config", tracking_dir: "Path") -> bool:
    """Show adopt table, prompt user, save override and update config.json.

    Returns True if a profile was adopted, False if cancelled.
    """
    from rich.prompt import Prompt

    machines = config.machines
    if not machines:
        console.print("No existing machine profiles found.")
        return False

    # Build table
    table = Table(title="Existing Machine Profiles")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("profile_id", style="magenta")
    table.add_column("machine_name", style="white")
    table.add_column("os_type", style="yellow")
    table.add_column("architecture", style="green")
    table.add_column("packages", style="blue", justify="right")

    items = list(machines.items())
    for idx, (profile_id, machine_profile) in enumerate(items, 1):
        pkg_count = str(len(config.packages.get(profile_id, [])))
        table.add_row(
            str(idx),
            profile_id,
            machine_profile.machine_name,
            machine_profile.os_type,
            machine_profile.architecture,
            pkg_count,
        )

    console.print(table)

    choice_str = Prompt.ask(
        "Enter the number of the profile to adopt (or 0 to cancel)",
        default="0",
    )

    try:
        choice = int(choice_str)
    except ValueError:
        console.print("Invalid input, cancelling.")
        return False

    if choice == 0:
        console.print("Cancelled.")
        return False

    if choice < 1 or choice > len(items):
        console.print(f"Invalid choice: {choice}")
        return False

    selected_profile_id, selected_machine = items[choice - 1]
    old_name = selected_machine.machine_name
    current_machine = MachineProfile.create_current()
    new_name = current_machine.machine_name

    # Save override to global config
    global_config = load_global_config()
    global_config.profile_id_override = selected_profile_id
    save_global_config(global_config)

    # Update machine_name in config.json to current hostname
    config.machines[selected_profile_id].machine_name = new_name

    config_file = tracking_dir / "config.json"
    with open(config_file, "w") as f:
        import json as _json

        _json.dump(config.dict(), f, indent=2, default=str)

    # Git commit + push
    try:
        git_manager = GitManager(tracking_dir, config.git, debug_mode=is_debug_mode())
        if git_manager.is_git_repo():
            git_manager.commit_changes(
                f"Adopt profile {selected_profile_id}: {old_name} -> {new_name}"
            )
            git_manager.push_changes()
    except Exception as e:
        console.print(f"[yellow]Warning: git operations failed: {e}[/yellow]")

    console.print(
        f"[green]This machine is now profile [bold]{selected_profile_id}[/bold] "
        f"({old_name} -> {new_name})[/green]"
    )
    return True


@machine_app.command()
def adopt(
    profile_id: Optional[str] = typer.Argument(
        None, help="Profile ID to adopt (e.g. 785075ba). Omit for interactive selection."
    ),
) -> None:
    """Adopt an existing profile ID for this machine."""
    config = load_config()
    tracking_dir = get_tracking_directory()

    if profile_id:
        if profile_id not in config.machines:
            console.print(f"[red]Profile '{profile_id}' not found.[/red]")
            console.print("Available profiles:")
            for pid, m in config.machines.items():
                console.print(f"  {pid}  {m.machine_name}")
            raise typer.Exit(1)

        old_name = config.machines[profile_id].machine_name
        current_machine = MachineProfile.create_current()
        new_name = current_machine.machine_name

        global_config = load_global_config()
        global_config.profile_id_override = profile_id
        save_global_config(global_config)

        config.machines[profile_id].machine_name = new_name
        config_file = tracking_dir / "config.json"
        with open(config_file, "w") as f:
            import json as _json
            _json.dump(config.dict(), f, indent=2, default=str)

        try:
            git_manager = GitManager(tracking_dir, config.git, debug_mode=is_debug_mode())
            if git_manager.is_git_repo():
                git_manager.commit_changes(
                    f"Adopt profile {profile_id}: {old_name} -> {new_name}"
                )
                git_manager.push_changes()
        except Exception as e:
            console.print(f"[yellow]Warning: git operations failed: {e}[/yellow]")

        console.print(
            f"[green]This machine is now profile [bold]{profile_id}[/bold] "
            f"({old_name} -> {new_name})[/green]"
        )
    else:
        _adopt_profile_interactive(config, tracking_dir)


# Repository management commands
repo_app = typer.Typer(name="repo", help="Repository management commands")
app.add_typer(repo_app, name="repo")


@repo_app.callback(invoke_without_command=True)
def repo_callback(ctx: Context) -> None:
    """Repository management commands."""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        console.print(ctx.get_help())


@repo_app.command()
def clone(
    git_url: str = typer.Argument(..., help="Git repository URL to clone"),
    directory: Optional[str] = typer.Option(
        None, "--directory", "-d", help="Directory to clone into"
    ),
) -> None:
    """Clone an existing install-sync repository."""
    import subprocess

    from rich.prompt import Confirm, Prompt

    # Determine clone directory
    if directory:
        tracking_dir = Path(directory).expanduser().resolve()
    else:
        home_dir = Path.home()
        default_tracking_dir = home_dir / "package-tracking"

        console.print("\n📁 [bold]Repository Clone Setup[/bold]")
        console.print(
            "Clone your existing install-sync repository to sync packages across machines.\\n"
        )

        tracking_dir_input = Prompt.ask(
            "Where should we clone the repository?", default=str(default_tracking_dir)
        )
        tracking_dir = Path(tracking_dir_input).expanduser().resolve()

    # Check if directory exists
    if tracking_dir.exists() and any(tracking_dir.iterdir()):
        console.print(f"⚠️  Directory {tracking_dir} already exists and is not empty.")

        choice = Prompt.ask(
            "What would you like to do?",
            choices=["overwrite", "use-different", "cancel"],
            default="use-different",
        )

        if choice == "cancel":
            console.print("❌ Clone cancelled")
            return
        elif choice == "use-different":
            counter = 1
            while (tracking_dir.parent / f"{tracking_dir.name}-{counter}").exists():
                counter += 1
            tracking_dir = tracking_dir.parent / f"{tracking_dir.name}-{counter}"
            console.print(f"📁 Using directory: {tracking_dir}")
        elif choice == "overwrite":
            import shutil

            if Confirm.ask(
                f"⚠️  This will delete all contents of {tracking_dir}. Continue?",
                default=False,
            ):
                shutil.rmtree(tracking_dir)
                console.print(f"🗑️  Cleared directory: {tracking_dir}")
            else:
                console.print("❌ Clone cancelled")
                return

    # Create directory if it doesn't exist
    tracking_dir.mkdir(parents=True, exist_ok=True)

    # Clone repository
    console.print(f"📥 Cloning repository from {git_url}...")
    try:
        subprocess.run(
            ["git", "clone", git_url, str(tracking_dir)],
            capture_output=True,
            text=True,
            check=True,
        )
        console.print("✅ Repository cloned successfully!")

        # Verify it's an install-sync repository
        config_file = tracking_dir / "config.json"

        if not config_file.exists():
            console.print(
                "⚠️  Warning: This doesn't appear to be an install-sync repository"
            )
            console.print("   Expected to find config.json file")

        # Create repo-config.json to track this setup
        repo_config = {
            "platform": "external",
            "repo_name": tracking_dir.name,
            "clone_url": git_url,
            "tracking_directory": str(tracking_dir),
            "created_at": datetime.now().isoformat(),
        }

        repo_config_file = tracking_dir / "repo-config.json"
        with open(repo_config_file, "w") as f:
            json.dump(repo_config, f, indent=2)

        console.print("\\n✅ [bold green]Repository setup complete![/bold green]")
        console.print(f"📁 Tracking directory: {tracking_dir}")
        console.print(f"🔗 Repository URL: {git_url}")
        console.print(
            "\\n💡 [dim]To use install-sync from anywhere, set this environment variable:[/dim]"
        )
        console.print(f"[cyan]export INSTALL_SYNC_DIR={tracking_dir}[/cyan]")

        # Show current machine info and packages
        console.print("\\n📊 [bold]Repository Contents:[/bold]")
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    config_data = json.load(f)
                    machines = config_data.get("machines", {})
                    packages = config_data.get("packages", {})

                    console.print(f"• Machines tracked: {len(machines)}")
                    total_packages = sum(
                        len(pkg_list) for pkg_list in packages.values()
                    )
                    console.print(f"• Total packages: {total_packages}")

                    if machines:
                        console.print("\\n🖥️  [bold]Existing Machines:[/bold]")
                        for machine_id, machine_info in machines.items():
                            machine_name = machine_info.get("machine_name", "Unknown")
                            os_type = machine_info.get("os_type", "Unknown")
                            pkg_count = len(packages.get(machine_id, []))
                            console.print(
                                f"   • {machine_name} ({os_type}) - {pkg_count} packages"
                            )
            except Exception as e:
                console.print(f"   ⚠️  Could not read repository contents: {e}")

        # Show current machine status
        current_machine = MachineProfile.create_current()
        console.print("\\n🔍 [bold]Current Machine:[/bold]")
        console.print(f"   • Name: {current_machine.machine_name}")
        console.print(f"   • OS: {current_machine.os_type}")
        console.print(f"   • Profile ID: {current_machine.profile_id}")

        # Check if current machine is already tracked; offer adopt if not
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    config_data = json.load(f)
                    machines = config_data.get("machines", {})
                    if current_machine.profile_id in machines:
                        console.print(
                            "   ✅ This machine is already tracked in the repository"
                        )
                    else:
                        console.print(
                            "   🆕 This is a new machine - will be added when you install packages"
                        )
                        # Offer to adopt an existing profile
                        if machines:
                            from rich.prompt import Confirm

                            n = len(machines)
                            if Confirm.ask(
                                f"\nFound {n} existing machine profile(s). "
                                "Would you like to adopt one for this machine?",
                                default=False,
                            ):
                                cloned_config = load_config()
                                _adopt_profile_interactive(cloned_config, tracking_dir)
            except Exception:
                pass

    except subprocess.CalledProcessError as e:
        console.print(f"❌ Failed to clone repository: {e.stderr}")
        console.print("💡 Check that the repository URL is correct and accessible")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Clone failed: {e}")
        raise typer.Exit(1)


@repo_app.command()
def setup() -> None:
    """Set up remote repository for git tracking."""
    from rich.prompt import Prompt

    repo_manager = RepoManager(repo_config_path)
    config = repo_manager.interactive_setup()

    if config:
        # Determine where to create the package tracking directory
        home_dir = Path.home()
        default_tracking_dir = home_dir / "package-tracking"

        console.print("\n📁 [bold]Package Tracking Directory Setup[/bold]")
        console.print(
            "install-sync needs a dedicated directory for tracking your packages."
        )
        console.print("This should be separate from any development projects.\n")

        tracking_dir_input = Prompt.ask(
            "Where should we create your package tracking directory?",
            default=str(default_tracking_dir),
        )

        tracking_dir = Path(tracking_dir_input).expanduser().resolve()

        # Check if directory exists and has content
        if tracking_dir.exists() and any(tracking_dir.iterdir()):
            console.print(
                f"⚠️  Directory {tracking_dir} already exists and is not empty."
            )

            choice = Prompt.ask(
                "What would you like to do?",
                choices=["use", "create-new", "cancel"],
                default="create-new",
            )

            if choice == "cancel":
                console.print("❌ Setup cancelled")
                return
            elif choice == "create-new":
                counter = 1
                while (tracking_dir.parent / f"{tracking_dir.name}-{counter}").exists():
                    counter += 1
                tracking_dir = tracking_dir.parent / f"{tracking_dir.name}-{counter}"
                console.print(f"📁 Using new directory: {tracking_dir}")

        # Create directory if it doesn't exist
        tracking_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"📁 Package tracking directory: {tracking_dir}")

        # Change to the tracking directory
        original_dir = current_dir
        os.chdir(tracking_dir)

        try:
            # Initialize git repository in tracking directory
            git_manager = GitManager(
                tracking_dir, GitConfig(), debug_mode=is_debug_mode()
            )
            if not git_manager.is_git_repo():
                git_manager.init_repo()

            # Setup remote (handles existing remotes gracefully)
            try:
                git_manager.add_remote("origin", config.clone_url)
            except Exception as e:
                console.print(f"⚠️  Remote setup warning: {e}")
                # Continue with other operations

            # Create .gitignore file
            _create_gitignore()

            # Create README for the repository
            _create_readme(config.repo_name)

            # Create initial empty config.json
            config_file = tracking_dir / "config.json"
            if not config_file.exists():
                initial_config = {
                    "machines": {},
                    "packages": {},
                    "git": {"auto_commit": True, "auto_push": True},
                }
                with open(config_file, "w") as f:
                    json.dump(initial_config, f, indent=2)
                console.print("📄 Created initial config.json")

            # Create initial commit
            console.print("📝 Creating initial commit...")
            try:
                git_manager.commit_changes("Initial commit: install-sync setup")
            except Exception as e:
                console.print(f"⚠️  Commit warning: {e}")
                # Try to commit any new files at least
                if git_manager.repo.untracked_files or git_manager.repo.is_dirty():
                    console.print("📝 Attempting to commit new files...")
                    git_manager.commit_changes("Update: Add .gitignore and README")

            console.print("📤 Pushing to remote repository...")
            try:
                # First try to push directly
                git_manager.push_changes()
                console.print(
                    "✅ [bold green]Setup completed successfully![/bold green]"
                )
            except Exception:
                console.print(
                    "⚠️  Initial push failed, attempting to sync with remote..."
                )

                # Try to pull/merge remote changes first
                try:
                    console.print("🔄 Syncing with remote repository...")
                    git_manager.pull_changes()

                    console.print("📤 Retrying push...")
                    git_manager.push_changes()
                    console.print(
                        "✅ [bold green]Setup completed successfully![/bold green]"
                    )
                except Exception as sync_e:
                    console.print(f"⚠️  Push warning: {sync_e}")
                    console.print(
                        "💡 [dim]Repository created successfully. Run "
                        "'install-sync repo fix' to complete sync[/dim]"
                    )

            # Update the repo config to include the tracking directory
            config.tracking_directory = str(tracking_dir)
            repo_manager._save_config(config)

            console.print(
                "\n✅ [bold green]Package tracking setup complete![/bold green]"
            )
            console.print(f"📁 Tracking directory: {tracking_dir}")
            console.print(f"🔗 Remote repository: {config.clone_url}")
            console.print(
                "\n💡 [dim]To use install-sync from anywhere, set this environment variable:[/dim]"
            )
            console.print(f"[cyan]export INSTALL_SYNC_DIR={tracking_dir}[/cyan]")

        except Exception as e:
            console.print(f"⚠️  Git setup completed with warnings: {e}")
            console.print(
                "💡 [dim]Repository created successfully, but git operations failed[/dim]"
            )
            console.print(
                "💡 [dim]You can run 'install-sync repo fix' to complete the setup[/dim]"
            )

        finally:
            # Change back to original directory
            os.chdir(original_dir)


@repo_app.command()
def status() -> None:
    """Show repository status."""
    try:
        tracking_dir = get_tracking_directory()
        git_manager = GitManager(tracking_dir, GitConfig(), debug_mode=is_debug_mode())
        if git_manager.is_git_repo():
            status = git_manager.get_status()

            # Also show remotes
            remotes_info = "\n[bold]Remotes:[/bold]\n"
            try:
                for remote in git_manager.repo.remotes:
                    remotes_info += f"  • {remote.name}: {remote.url}\n"
            except Exception:
                remotes_info += "  No remotes configured\n"

            # Show tracking directory
            dir_info = f"\n[bold]Tracking Directory:[/bold]\n  📁 {tracking_dir}\n"

            status_with_info = status + "\n" + remotes_info + dir_info
            console.print(
                Panel(status_with_info, title="📊 Git Status", border_style="blue")
            )
        else:
            console.print(
                "❌ Not a git repository. Run 'install-sync repo setup' first."
            )
    except Exception as e:
        console.print(f"❌ Failed to get status: {e}")


@repo_app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of commits to show")
) -> None:
    """Show commit history."""
    try:
        git_manager = GitManager(current_dir, GitConfig(), debug_mode=is_debug_mode())
        if git_manager.is_git_repo():
            commits = git_manager.get_commit_history(limit=limit)
            if commits:
                table = Table(title="📚 Recent Commits")
                table.add_column("Hash", style="cyan")
                table.add_column("Message", style="white")
                table.add_column("Author", style="magenta")
                table.add_column("Date", style="yellow")

                for commit in commits:
                    table.add_row(
                        commit["hash"],
                        commit["message"][:50] + "..."
                        if len(commit["message"]) > 50
                        else commit["message"],
                        commit["author"],
                        commit["date"],
                    )

                console.print(table)
            else:
                console.print("📚 No commits found")
        else:
            console.print(
                "❌ Not a git repository. Run 'install-sync repo setup' first."
            )
    except Exception as e:
        console.print(f"❌ Failed to get history: {e}")


@repo_app.command()
def fix() -> None:
    """Fix git configuration if initial setup failed."""
    try:
        # Check if we have a repo config
        repo_manager = RepoManager(repo_config_path)
        config = repo_manager.get_config()

        if not config:
            console.print(
                "❌ No repository configuration found. Run 'install-sync repo setup' first."
            )
            return

        git_manager = GitManager(current_dir, GitConfig(), debug_mode=is_debug_mode())

        # Check current git status
        if not git_manager.is_git_repo():
            console.print("📁 Initializing git repository...")
            git_manager.init_repo()

        # Check if remote exists
        try:
            git_manager.repo.remote("origin")
            console.print("✅ Remote 'origin' already configured")
        except Exception:
            console.print("🔗 Adding remote origin...")
            git_manager.add_remote("origin", config.clone_url)

        # Create .gitignore and README if missing
        _create_gitignore()
        _create_readme(config.repo_name)

        # Try to commit and push any pending changes
        if git_manager.repo.is_dirty() or git_manager.repo.untracked_files:
            console.print("📝 Committing pending changes...")
            git_manager.commit_changes("Fix: Complete install-sync setup")

        console.print("📤 Attempting to push to remote...")
        try:
            git_manager.push_changes()
            console.print("✅ Git configuration fixed successfully!")
        except Exception:
            console.print("⚠️  Push failed, attempting to sync with remote first...")

            try:
                console.print("🔄 Syncing with remote repository...")
                git_manager.pull_changes()

                console.print("📤 Retrying push...")
                git_manager.push_changes()
                console.print("✅ Git configuration fixed successfully!")
            except Exception as sync_e:
                console.print(f"⚠️  Sync failed: {sync_e}")
                console.print(
                    "💡 [dim]Manual intervention may be required. Check for merge conflicts.[/dim]"
                )

    except Exception as e:
        console.print(f"❌ Failed to fix git configuration: {e}")
        console.print(
            "💡 [dim]You may need to check your token permissions or configure git manually[/dim]"
        )


@repo_app.command()
def delete() -> None:
    """Delete the remote repository (WARNING: Destructive operation)."""
    from rich.prompt import Confirm

    try:
        # Check if we have a repo config
        repo_manager = RepoManager(repo_config_path)
        config = repo_manager.get_config()

        if not config:
            console.print("❌ No repository configuration found. Nothing to delete.")
            return

        console.print("\n⚠️  [bold red]WARNING: Destructive Operation![/bold red]")
        console.print("This will permanently delete the repository: ")
        console.print(f"  • Platform: {config.platform.title()}")
        console.print(f"  • Repository: {config.repo_name}")
        console.print(f"  • URL: {config.clone_url}")
        console.print("\n🚨 [bold red]This action cannot be undone![/bold red]")
        console.print("All data in the remote repository will be lost forever.")

        # Double confirmation
        first_confirm = Confirm.ask(
            f"Are you absolutely sure you want to delete '{config.repo_name}'?",
            default=False,
        )

        if not first_confirm:
            console.print("❌ Deletion cancelled")
            return

        second_confirm = Confirm.ask(
            "This will permanently destroy all data. Continue?", default=False
        )

        if not second_confirm:
            console.print("❌ Deletion cancelled")
            return

        # Get token for deletion
        token = typer.prompt(
            f"Enter your {config.platform.title()} personal access token",
            hide_input=True,
        )

        console.print(f"\n🗑️  Deleting repository '{config.repo_name}'...")

        # Delete the repository
        if config.platform == "github":
            success = repo_manager.delete_github_repo(config.repo_name, token)
        else:
            success = repo_manager.delete_gitlab_repo(config.repo_name, token)

        if success:
            # Remove local configuration
            if repo_config_path.exists():
                repo_config_path.unlink()
                console.print("✅ Removed local repository configuration")

            console.print("✅ [bold green]Repository deleted successfully![/bold green]")
            console.print(
                "💡 You can run 'install-sync repo setup' to create a new repository"
            )
        else:
            console.print("❌ Failed to delete repository")

    except Exception as e:
        console.print(f"❌ Failed to delete repository: {e}")


# Apt repo management commands
apt_repo_app = typer.Typer(name="apt-repo", help="Manage apt repository definitions")
app.add_typer(apt_repo_app, name="apt-repo")

# Config management commands
config_app = typer.Typer(name="config", help="Global configuration management")
app.add_typer(config_app, name="config")


@apt_repo_app.command("add")
def apt_repo_add(
    package: str = typer.Argument(..., help="Package name to associate the repo with"),
    gpg_key_url: str = typer.Option(..., "--gpg-url", help="URL of the GPG signing key"),
    repo_url: str = typer.Option(..., "--repo-url", help="Base URL of the apt repository"),
    distribution: Optional[str] = typer.Option(
        None, "--distribution", help="e.g. focal (auto-detected if omitted)"
    ),
    components: str = typer.Option("main", "--components", help="Repo components"),
    architecture: Optional[str] = typer.Option(
        None, "--arch", help="e.g. amd64 (auto-detected if omitted)"
    ),
    sources_file: Optional[str] = typer.Option(
        None, "--sources-file", help="Path for sources.list.d file (auto-derived if omitted)"
    ),
    keyring_path: Optional[str] = typer.Option(
        None, "--keyring-path", help="Path for keyring file (auto-derived if omitted)"
    ),
) -> None:
    """Add an apt repository definition for a package (stored in config.json, git-synced)."""
    config = load_config()
    config.apt_repos[package] = AptRepoConfig(
        gpg_key_url=gpg_key_url,
        repo_url=repo_url,
        distribution=distribution,
        components=components,
        architecture=architecture,
        sources_file=sources_file,
        keyring_path=keyring_path,
    )
    repo_def = config.apt_repos[package]
    save_config(config)
    console.print(f"✅ Apt repo definition saved for [bold]{package}[/bold]")

    # Immediately set up the repo so it's validated and ready to use
    apt_mgr = PackageManagerFactory.get_manager("apt")
    # Force setup by removing existing sources file first (re-add should always refresh)
    sources_path = repo_def.sources_file or f"/etc/apt/sources.list.d/{package}.list"
    import subprocess as _sp
    _sp.run(["sudo", "rm", "-f", sources_path], capture_output=True)
    if apt_mgr.setup_repo(package, repo_def):
        console.print(f"   Run 'install-sync install {package} --manager apt' to install")
    else:
        console.print(f"⚠️  Repository setup failed — definition saved but repo may not be valid")
        raise typer.Exit(1)


@apt_repo_app.command("list")
def apt_repo_list() -> None:
    """List all configured apt repository definitions."""
    config = load_config()
    if not config.apt_repos:
        console.print("ℹ️  No apt repo definitions configured")
        return
    table = Table(title="Apt Repository Definitions")
    table.add_column("Package", style="bold")
    table.add_column("GPG Key URL")
    table.add_column("Repo URL")
    table.add_column("Distribution")
    for pkg, repo in config.apt_repos.items():
        table.add_row(
            pkg, repo.gpg_key_url, repo.repo_url, repo.distribution or "(auto)"
        )
    console.print(table)


@apt_repo_app.command("remove")
def apt_repo_remove(
    package: str = typer.Argument(..., help="Package name to remove repo definition for"),
) -> None:
    """Remove an apt repository definition and clean up files on disk."""
    import subprocess as _sp
    from pathlib import Path as _Path

    config = load_config()
    if package not in config.apt_repos:
        console.print(f"ℹ️  No apt repo definition found for {package}")
        return

    repo = config.apt_repos[package]
    sources_file = repo.sources_file or f"/etc/apt/sources.list.d/{package}.list"
    keyring_path = repo.keyring_path or f"/usr/share/keyrings/{package}-keyring.gpg"

    del config.apt_repos[package]
    save_config(config)

    removed = []
    for path in (sources_file, keyring_path):
        if _Path(path).exists():
            result = _sp.run(["sudo", "rm", "-f", path], capture_output=True, text=True)
            if result.returncode == 0:
                removed.append(path)
            else:
                console.print(f"⚠️  Could not remove {path}: {result.stderr.strip()}")

    if removed:
        _sp.run(["sudo", "apt-get", "update", "-qq"], capture_output=True)
        for path in removed:
            console.print(f"🗑️  Removed {path}")

    console.print(f"✅ Removed apt repo definition for {package}")


# ---------------------------------------------------------------------------
# script subcommand group
# ---------------------------------------------------------------------------

script_app = typer.Typer(name="script", help="Manage script-based package definitions")
app.add_typer(script_app, name="script")


@script_app.command("add")
def script_add(
    package: str = typer.Argument(..., help="Package name"),
    install_cmd: Optional[str] = typer.Option(None, "--install-cmd", help="Shell command to install the package"),
    uninstall_cmd: Optional[str] = typer.Option(None, "--uninstall-cmd", help="Shell command to uninstall the package"),
    check_cmd: Optional[str] = typer.Option(None, "--check-cmd", help="Shell command to check if package is installed"),
    version_cmd: Optional[str] = typer.Option(None, "--version-cmd", help="Shell command to get the installed version"),
) -> None:
    """Add or update a script-based package definition (stored in config.json, git-synced)."""
    config = load_config()
    config.script_packages[package] = ScriptPackageDef(
        install_cmd=install_cmd,
        uninstall_cmd=uninstall_cmd,
        check_cmd=check_cmd,
        version_cmd=version_cmd,
    )
    save_config(config)
    console.print(f"✅ Script definition saved for [bold]{package}[/bold]")
    defn = config.script_packages[package]
    if defn.install_cmd:
        console.print(f"   install:   {defn.install_cmd}")
    if defn.uninstall_cmd:
        console.print(f"   uninstall: {defn.uninstall_cmd}")
    if defn.check_cmd:
        console.print(f"   check:     {defn.check_cmd}")
    if defn.version_cmd:
        console.print(f"   version:   {defn.version_cmd}")


@script_app.command("list")
def script_list() -> None:
    """List all script-based package definitions."""
    config = load_config()
    if not config.script_packages:
        console.print("ℹ️  No script package definitions configured")
        return
    table = Table(title="Script Package Definitions")
    table.add_column("Package", style="bold")
    table.add_column("Install Cmd")
    table.add_column("Uninstall Cmd")
    table.add_column("Check Cmd")
    table.add_column("Version Cmd")
    for pkg, defn in config.script_packages.items():
        table.add_row(
            pkg,
            defn.install_cmd or "",
            defn.uninstall_cmd or "",
            defn.check_cmd or "",
            defn.version_cmd or "",
        )
    console.print(table)


@script_app.command("remove")
def script_remove(
    package: str = typer.Argument(..., help="Package name to remove script definition for"),
) -> None:
    """Remove a script-based package definition."""
    config = load_config()
    if package not in config.script_packages:
        console.print(f"ℹ️  No script definition found for {package}")
        return
    del config.script_packages[package]
    save_config(config)
    console.print(f"✅ Removed script definition for [bold]{package}[/bold]")


@config_app.callback(invoke_without_command=True)
def config_callback(ctx: Context) -> None:
    """Global configuration management."""
    if ctx.invoked_subcommand is None:
        # Show help when no subcommand is provided
        console.print(ctx.get_help())


@config_app.command()
def show() -> None:
    """Show current global configuration."""
    global_config = load_global_config_with_debug()
    global_config_path = Path.home() / ".install-sync.config"

    # Build config info in parts to avoid long lines
    auto_commit = global_config.git_auto_commit
    auto_commit_str = auto_commit if auto_commit is not None else "Default (enabled)"

    auto_push = global_config.git_auto_push
    auto_push_str = auto_push if auto_push is not None else "Default (enabled)"

    tracking_dir = (
        global_config.default_tracking_directory or "Default (~/package-tracking)"
    )

    config_info = f"""
[bold]Global Configuration[/bold]
• Config file: {global_config_path}
• File exists: {'✅' if global_config_path.exists() else '❌'}

[bold]Git Settings[/bold]
• Auto-commit: {auto_commit_str}
• Auto-push: {auto_push_str}
• Show prompts: {'✅' if global_config.git_prompt else '❌'}
• Remote preference: {'SSH' if global_config.prefer_ssh_remotes else 'HTTPS'}
• Auto-sync before push: {'✅' if global_config.git_auto_sync else '❌'}
• Auto-sync on list: {'✅' if global_config.git_auto_sync_on_list else '❌'}

[bold]Directories[/bold]
• Default tracking directory: {tracking_dir}

[bold]Package Managers[/bold]
"""

    if global_config.package_managers:
        for os_type, manager in global_config.package_managers.items():
            config_info += f"• {os_type}: {manager}\n"
    else:
        config_info += "• No custom package manager preferences set\n"

    console.print(
        Panel(config_info, title="📋 Global Configuration", border_style="blue")
    )


@config_app.command("set")
def config_set(
    git_auto_commit: Optional[bool] = typer.Option(
        None,
        "--git-auto-commit/--no-git-auto-commit",
        help="Enable/disable auto-commit",
    ),
    git_auto_push: Optional[bool] = typer.Option(
        None, "--git-auto-push/--no-git-auto-push", help="Enable/disable auto-push"
    ),
    git_prompt: Optional[bool] = typer.Option(
        None, "--git-prompt/--no-git-prompt", help="Enable/disable git prompts"
    ),
    prefer_ssh_remotes: Optional[bool] = typer.Option(
        None,
        "--prefer-ssh/--prefer-https",
        help="Prefer SSH over HTTPS for git remotes",
    ),
    git_auto_sync: Optional[bool] = typer.Option(
        None,
        "--git-auto-sync/--no-git-auto-sync",
        help="Enable/disable auto-pull before every push operation",
    ),
    git_auto_sync_on_list: Optional[bool] = typer.Option(
        None,
        "--git-auto-sync-on-list/--no-git-auto-sync-on-list",
        help="Enable/disable auto-sync when listing packages",
    ),
    tracking_directory: Optional[str] = typer.Option(
        None, "--tracking-directory", help="Set default tracking directory"
    ),
    show_error_output: Optional[bool] = typer.Option(
        None,
        "--show-error-output/--no-show-error-output",
        help="Show raw stderr in CLI when a package fails (default: on)",
    ),
    verbose_logging: Optional[bool] = typer.Option(
        None,
        "--verbose-logging/--no-verbose-logging",
        help="Write all command output to log file (default: off)",
    ),
) -> None:
    """Set global configuration options."""
    global_config = load_global_config_with_debug()

    updated = False

    if git_auto_commit is not None:
        global_config.git_auto_commit = git_auto_commit
        updated = True
        console.print(f"✅ Set git auto-commit: {git_auto_commit}")

    if git_auto_push is not None:
        global_config.git_auto_push = git_auto_push
        updated = True
        console.print(f"✅ Set git auto-push: {git_auto_push}")

    if git_prompt is not None:
        global_config.git_prompt = git_prompt
        updated = True
        console.print(f"✅ Set git prompts: {git_prompt}")

    if prefer_ssh_remotes is not None:
        global_config.prefer_ssh_remotes = prefer_ssh_remotes
        updated = True
        protocol = "SSH" if prefer_ssh_remotes else "HTTPS"
        console.print(f"✅ Set git remote preference: {protocol}")

    if git_auto_sync is not None:
        global_config.git_auto_sync = git_auto_sync
        updated = True
        console.print(f"✅ Set git auto-sync: {git_auto_sync}")

    if git_auto_sync_on_list is not None:
        global_config.git_auto_sync_on_list = git_auto_sync_on_list
        updated = True
        console.print(f"✅ Set git auto-sync on list: {git_auto_sync_on_list}")

    if tracking_directory is not None:
        # Expand and validate path
        expanded_path = Path(tracking_directory).expanduser().resolve()
        global_config.default_tracking_directory = str(expanded_path)
        updated = True
        console.print(f"✅ Set default tracking directory: {expanded_path}")

    if show_error_output is not None:
        global_config.show_error_output = show_error_output
        updated = True
        console.print(f"✅ Set show-error-output: {show_error_output}")

    if verbose_logging is not None:
        global_config.verbose_logging = verbose_logging
        updated = True
        console.print(f"✅ Set verbose-logging: {verbose_logging}")

    if updated:
        save_global_config_with_debug(global_config)
        console.print("💾 Global configuration saved")
    else:
        console.print("ℹ️  No changes made")


@config_app.command()
def reset() -> None:
    """Reset global configuration to defaults."""
    from rich.prompt import Confirm

    global_config_path = Path.home() / ".install-sync.config"

    if global_config_path.exists():
        if Confirm.ask(
            "⚠️  This will delete your global configuration. Continue?", default=False
        ):
            global_config_path.unlink()
            console.print("✅ Global configuration reset to defaults")
        else:
            console.print("❌ Reset cancelled")
    else:
        console.print("ℹ️  No global configuration file exists")


if __name__ == "__main__":
    app()
