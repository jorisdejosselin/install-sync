"""Repository creation and management."""

import json
from pathlib import Path
from typing import Optional

import requests
from rich.console import Console
from rich.prompt import Confirm, Prompt

from .config_utils import load_global_config
from .models import RepoConfig

console = Console()


def convert_https_to_ssh(https_url: str) -> str:
    """Convert HTTPS git URL to SSH format."""
    # Handle GitHub URLs
    if "https://github.com/" in https_url:
        path = https_url.replace("https://github.com/", "")
        return f"git@github.com:{path}"

    # Handle GitLab URLs
    if "https://gitlab.com/" in https_url:
        path = https_url.replace("https://gitlab.com/", "")
        return f"git@gitlab.com:{path}"

    # For other git providers, try to parse generically
    if https_url.startswith("https://"):
        # Extract domain and path
        without_protocol = https_url[8:]  # Remove "https://"
        if "/" in without_protocol:
            domain, path = without_protocol.split("/", 1)
            return f"git@{domain}:{path}"

    # If we can't convert, return original
    return https_url


def convert_ssh_to_https(ssh_url: str) -> str:
    """Convert SSH git URL to HTTPS format."""
    # Handle GitHub URLs
    if ssh_url.startswith("git@github.com:"):
        path = ssh_url.replace("git@github.com:", "")
        return f"https://github.com/{path}"

    # Handle GitLab URLs
    if ssh_url.startswith("git@gitlab.com:"):
        path = ssh_url.replace("git@gitlab.com:", "")
        return f"https://gitlab.com/{path}"

    # For other git providers, try to parse generically
    if ssh_url.startswith("git@"):
        # Extract domain and path
        without_prefix = ssh_url[4:]  # Remove "git@"
        if ":" in without_prefix:
            domain, path = without_prefix.split(":", 1)
            return f"https://{domain}/{path}"

    # If we can't convert, return original
    return ssh_url


class RepoManager:
    """Manages remote repository creation and configuration."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Optional[RepoConfig]:
        """Load repository configuration."""
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                data = json.load(f)
                return RepoConfig(**data)
        return None

    def _save_config(self, config: RepoConfig) -> None:
        """Save repository configuration."""
        with open(self.config_path, "w") as f:
            json.dump(config.dict(), f, indent=2, default=str)

    def create_github_repo(
        self, repo_name: str, token: str, private: bool = True
    ) -> Optional[str]:
        """Create repository on GitHub."""
        url = "https://api.github.com/user/repos"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        data = {
            "name": repo_name,
            "description": "Personal software package tracking across multiple "
            "machines - managed by install-sync",
            "private": private,
            "auto_init": False,  # Don't auto-init to avoid conflicts
            # Note: We'll create our own initial files
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            repo_data = response.json()
            console.print(
                f"✅ Successfully created GitHub repository: {repo_data['html_url']}"
            )
            return str(repo_data["clone_url"])
        except requests.RequestException as e:
            console.print(f"❌ Failed to create GitHub repository: {e}")
            if hasattr(e, "response") and e.response is not None:
                if e.response.status_code == 401:
                    console.print(
                        "🔑 [red]Authentication failed[/red] - Check your token: "
                    )
                    console.print("   • Ensure token has [cyan]repo[/cyan] permissions")
                    console.print("   • Verify token hasn't expired")
                    console.print("   • See TOKEN_SETUP.md for detailed instructions")
                elif e.response.status_code == 403:
                    console.print(
                        "🚫 [red]Permission denied[/red] - Token may lack required permissions: "
                    )
                    console.print(
                        "   • Token needs [cyan]repo[/cyan] scope for private repositories"
                    )
                    console.print(
                        "   • For organizations, ensure SSO is enabled for the token"
                    )
                else:
                    console.print(f"Response: {e.response.text}")
            return None

    def create_gitlab_repo(
        self, repo_name: str, token: str, private: bool = True
    ) -> Optional[str]:
        """Create repository on GitLab."""
        url = "https://gitlab.com/api/v4/projects"
        headers = {"Private-Token": token, "Content-Type": "application/json"}
        data = {
            "name": repo_name,
            "description": "Personal software package tracking across multiple "
            "machines - managed by install-sync",
            "visibility": "private" if private else "public",
            "initialize_with_readme": False,  # Don't auto-init to avoid conflicts
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            repo_data = response.json()
            console.print(
                f"✅ Successfully created GitLab repository: {repo_data['web_url']}"
            )
            return str(repo_data["http_url_to_repo"])
        except requests.RequestException as e:
            console.print(f"❌ Failed to create GitLab repository: {e}")
            if hasattr(e, "response") and e.response is not None:
                if e.response.status_code == 401:
                    console.print(
                        "🔑 [red]Authentication failed[/red] - Check your token: "
                    )
                    console.print("   • Ensure token has [cyan]api[/cyan] scope")
                    console.print("   • Verify token hasn't expired")
                    console.print("   • See TOKEN_SETUP.md for detailed instructions")
                elif e.response.status_code == 403:
                    console.print(
                        "🚫 [red]Permission denied[/red] - Token may lack required permissions: "
                    )
                    console.print(
                        "   • Token needs [cyan]api[/cyan] scope for repository creation"
                    )
                    console.print("   • Ensure you have Developer role or higher")
                else:
                    console.print(f"Response: {e.response.text}")
            return None

    def delete_github_repo(self, repo_name: str, token: str) -> bool:
        """Delete repository on GitHub."""
        # First get the authenticated user's username
        user_url = "https://api.github.com/user"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            user_response = requests.get(user_url, headers=headers)
            user_response.raise_for_status()
            username = user_response.json()["login"]

            # Delete the repository
            delete_url = f"https://api.github.com/repos/{username}/{repo_name}"
            response = requests.delete(delete_url, headers=headers)

            if response.status_code == 204:
                console.print(
                    f"✅ Successfully deleted GitHub repository: {username}/{repo_name}"
                )
                return True
            elif response.status_code == 404:
                console.print(
                    f"ℹ️  Repository {username}/{repo_name} not found (may already be deleted)"
                )
                return True
            else:
                console.print(
                    f"❌ Failed to delete GitHub repository: {response.status_code}"
                )
                console.print(f"Response: {response.text}")
                return False

        except requests.RequestException as e:
            console.print(f"❌ Failed to delete GitHub repository: {e}")
            return False

    def delete_gitlab_repo(self, repo_name: str, token: str) -> bool:
        """Delete repository on GitLab."""
        # First get the authenticated user's username
        user_url = "https://gitlab.com/api/v4/user"
        headers = {"Private-Token": token, "Content-Type": "application/json"}

        try:
            user_response = requests.get(user_url, headers=headers)
            user_response.raise_for_status()
            username = user_response.json()["username"]

            # Get project ID
            project_url = f"https://gitlab.com/api/v4/projects/{username}%2F{repo_name}"
            project_response = requests.get(project_url, headers=headers)

            if project_response.status_code == 404:
                console.print(
                    f"ℹ️  Repository {username}/{repo_name} not found (may already be deleted)"
                )
                return True

            project_response.raise_for_status()
            project_id = project_response.json()["id"]

            # Delete the repository
            delete_url = f"https://gitlab.com/api/v4/projects/{project_id}"
            response = requests.delete(delete_url, headers=headers)

            if response.status_code == 202:
                console.print(
                    f"✅ Successfully deleted GitLab repository: {username}/{repo_name}"
                )
                return True
            else:
                console.print(
                    f"❌ Failed to delete GitLab repository: {response.status_code}"
                )
                console.print(f"Response: {response.text}")
                return False

        except requests.RequestException as e:
            console.print(f"❌ Failed to delete GitLab repository: {e}")
            return False

    def check_repo_exists(self, repo_name: str, token: str, platform: str) -> bool:
        """Check if repository already exists."""
        if platform == "github":
            user_url = "https://api.github.com/user"
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            }
        else:  # gitlab
            user_url = "https://gitlab.com/api/v4/user"
            headers = {"Private-Token": token, "Content-Type": "application/json"}

        try:
            # Get username
            user_response = requests.get(user_url, headers=headers)
            user_response.raise_for_status()
            username = user_response.json()[
                "login" if platform == "github" else "username"
            ]

            # Check if repo exists
            if platform == "github":
                repo_url = f"https://api.github.com/repos/{username}/{repo_name}"
                response = requests.get(repo_url, headers=headers)
            else:  # gitlab
                repo_url = (
                    f"https://gitlab.com/api/v4/projects/{username}%2F{repo_name}"
                )
                response = requests.get(repo_url, headers=headers)

            return bool(response.status_code == 200)

        except requests.RequestException:
            return False

    def interactive_setup(self) -> Optional[RepoConfig]:
        """Interactive repository setup."""
        console.print("\n🚀 [bold]install-sync Repository Setup[/bold]")
        console.print(
            "This will create a remote repository to track your personal "
            "software packages across all your machines\n"
        )

        # Choose platform
        platform = Prompt.ask(
            "Choose git platform", choices=["github", "gitlab"], default="github"
        )

        # Get repository name
        console.print(
            "💡 [dim]Suggested names: my-software-packages, "
            "personal-package-tracker, software-inventory[/dim]"
        )
        repo_name = Prompt.ask("Repository name", default="my-software-packages")

        # Get token
        console.print(
            f"\n🔑 [bold]{platform.title()} Personal Access Token Required[/bold]"
        )
        if platform == "github":
            console.print(
                "📋 Required permissions: [cyan]repo[/cyan] (Full control of private repositories)"
            )
            console.print(
                "🔗 Create token at: [link]https://github.com/settings/tokens[/link]"
            )
        else:  # gitlab
            console.print(
                "📋 Required scopes: [cyan]api[/cyan] (Complete read/write access to the API)"
            )
            console.print(
                "   [dim]Note: 'api' includes repository creation AND git push permissions[/dim]"
            )
            console.print(
                "🔗 Create token at: "
                "[link]https://gitlab.com/-/profile/personal_access_tokens[/link]"
            )

        console.print(
            "ℹ️  [dim]Token is only used once to create the repository and is not stored[/dim]\n"
        )

        token = Prompt.ask(
            f"Enter your {platform.title()} personal access token", password=True
        )

        # Check if repository already exists
        console.print(f"\n🔍 Checking if repository '{repo_name}' already exists...")
        if self.check_repo_exists(repo_name, token, platform):
            console.print(
                f"⚠️  [yellow]Repository '{repo_name}' already exists "
                f"on {platform.title()}[/yellow]"
            )

            choice = Prompt.ask(
                "What would you like to do?",
                choices=["delete", "rename", "cancel"],
                default="rename",
            )

            if choice == "cancel":
                console.print("❌ Setup cancelled")
                return None
            elif choice == "delete":
                console.print(
                    "\n⚠️  [bold red]WARNING: This will permanently delete "
                    "the existing repository![/bold red]"
                )
                console.print(
                    "This action cannot be undone. All data in the repository will be lost."
                )

                confirm_delete = Confirm.ask(
                    f"Are you sure you want to delete '{repo_name}' on {platform.title()}?",
                    default=False,
                )

                if not confirm_delete:
                    console.print("❌ Deletion cancelled")
                    return None

                console.print("\n🗑️  Deleting existing repository...")
                if platform == "github":
                    success = self.delete_github_repo(repo_name, token)
                else:
                    success = self.delete_gitlab_repo(repo_name, token)

                if not success:
                    console.print("❌ Failed to delete existing repository")
                    return None

                console.print("✅ Existing repository deleted successfully")
            elif choice == "rename":
                new_name = Prompt.ask(
                    "Enter a new repository name", default=f"{repo_name}-v2"
                )
                repo_name = new_name

                # Check if the new name also exists
                if self.check_repo_exists(repo_name, token, platform):
                    console.print(
                        f"❌ Repository '{repo_name}' also already exists. "
                        f"Please try a different name or choose to delete the existing one."
                    )
                    return None

        # Privacy setting
        private = Confirm.ask("Make repository private?", default=True)

        # Create repository
        console.print(f"\n🔧 Creating {platform.title()} repository...")
        if platform == "github":
            clone_url = self.create_github_repo(repo_name, token, private)
        else:
            clone_url = self.create_gitlab_repo(repo_name, token, private)

        if clone_url:
            # Check if user prefers SSH remotes
            global_config = load_global_config()
            if global_config.prefer_ssh_remotes:
                ssh_url = convert_https_to_ssh(clone_url)
                console.print(f"🔐 Using SSH remote: {ssh_url}")
                final_clone_url = ssh_url
            else:
                final_clone_url = clone_url

            # Save configuration
            config = RepoConfig(
                platform=platform,
                repo_name=repo_name,
                clone_url=final_clone_url,
                tracking_directory=None,
            )
            self._save_config(config)
            self.config = config

            console.print("\n✅ [bold green]Setup Complete![/bold green]")
            console.print(f"Repository: {clone_url}")
            console.print(
                "You can now use 'install-sync' to manage your software installations\n"
            )

            return config
        else:
            console.print("❌ Repository creation failed")
            return None

    def get_config(self) -> Optional[RepoConfig]:
        """Get current repository configuration."""
        return self.config
