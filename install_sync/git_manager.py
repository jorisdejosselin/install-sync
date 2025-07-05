"""Git operations management."""

from pathlib import Path
from typing import List, Optional

from git import GitCommandError, Repo
from rich.console import Console

from .models import GitConfig

console = Console()


class GitManager:
    """Manages git operations for install-sync."""

    def __init__(self, repo_path: Path, config: GitConfig, debug_mode: bool = False):
        self.repo_path = repo_path
        self.config = config
        self.debug_mode = debug_mode
        self._repo: Optional[Repo] = None

    @property
    def repo(self) -> Repo:
        """Get git repository instance."""
        if self._repo is None:
            try:
                self._repo = Repo(self.repo_path)
            except GitCommandError:
                console.print(
                    "❌ Not a git repository. Run 'install-sync repo setup' first."
                )
                raise
        return self._repo

    def is_git_repo(self) -> bool:
        """Check if current directory is a git repository."""
        return (self.repo_path / ".git").exists()

    def init_repo(self) -> None:
        """Initialize git repository."""
        try:
            self._repo = Repo.init(self.repo_path)
            console.print("✅ Initialized git repository")
        except GitCommandError as e:
            console.print(f"❌ Failed to initialize git repository: {e}")
            raise

    def add_remote(self, remote_name: str, remote_url: str) -> None:
        """Add remote repository."""
        try:
            # Check if remote already exists
            existing_remote = None
            try:
                existing_remote = self.repo.remote(remote_name)
                existing_url = existing_remote.url
                if existing_url == remote_url:
                    console.print(
                        f"✅ Remote '{remote_name}' already exists with " "correct URL"
                    )
                    return
                else:
                    console.print(f"🔄 Updating remote '{remote_name}' URL...")
                    existing_remote.set_url(remote_url)
                    console.print(f"✅ Updated remote '{remote_name}': {remote_url}")
                    return
            except Exception:
                # Remote doesn't exist, continue to create it
                pass

            # Create new remote
            self.repo.create_remote(remote_name, remote_url)
            console.print(f"✅ Added remote '{remote_name}': {remote_url}")
        except GitCommandError as e:
            console.print(f"❌ Failed to add remote: {e}")
            raise

    def commit_changes(self, message: str) -> None:
        """Commit changes to git."""
        if not self.config.auto_commit:
            return

        try:
            # Add all changes
            self.repo.git.add(A=True)

            # Check if there are changes to commit
            if self.repo.is_dirty() or self.repo.untracked_files:
                self.repo.index.commit(message)
                console.print(f"✅ Committed changes: {message}")
            else:
                console.print("ℹ️  No changes to commit")
        except GitCommandError as e:
            console.print(f"❌ Failed to commit changes: {e}")
            raise

    def push_changes(
        self, remote_name: str = "origin", branch_name: str = "main"
    ) -> None:
        """Push changes to remote repository."""
        if not self.config.auto_push:
            return

        try:
            origin = self.repo.remote(remote_name)

            # Debug info: Show what we're pushing and where (only in debug mode)
            if self.debug_mode:
                console.print("📤 [bold]Git Push Debug Info:[/bold]")
                console.print(f"   • Local repository: {self.repo_path}")
                console.print(f"   • Remote name: {remote_name}")
                console.print(f"   • Remote URL: {origin.url}")
                console.print(f"   • Branch: {branch_name}")
                console.print(f"   • Working directory: {self.repo.working_dir}")

                # Show current branch and commit
                try:
                    current_branch = self.repo.active_branch.name
                    current_commit = self.repo.head.commit.hexsha[:8]
                    console.print(f"   • Current branch: {current_branch}")
                    console.print(f"   • Current commit: {current_commit}")
                except Exception:
                    console.print("   • Branch info: Unable to determine")

                # Show what files are in the repository
                try:
                    files_in_repo = list(self.repo_path.glob("*"))
                    non_git_files = [f.name for f in files_in_repo if f.name != ".git"]
                    console.print(f"   • Files in repo: {non_git_files}")
                except Exception:
                    console.print("   • Files in repo: Unable to list")

                console.print(f"🚀 Attempting to push to {origin.url}...")

            push_info = origin.push(branch_name)

            # Check if push was successful by examining push results
            success = False
            if push_info:
                push_result = push_info[0]
                if push_result.flags & push_result.ERROR:
                    console.print(f"❌ Push failed: {push_result.summary}")
                    raise GitCommandError("git push", "Push failed")
                elif push_result.flags & push_result.REJECTED:
                    console.print(f"❌ Push rejected: {push_result.summary}")
                    console.print(
                        "💡 [dim]You may need to pull changes first: "
                        "install-sync sync[/dim]"
                    )
                    raise GitCommandError("git push", "Push rejected")
                else:
                    success = True
            else:
                success = True

            if success:
                console.print(f"✅ Pushed changes to {remote_name}/{branch_name}")

        except GitCommandError as e:
            error_msg = str(e).lower()

            console.print(f"⚠️  [yellow]Push failed with error:[/yellow] {e}")

            # Check for specific push failure scenarios
            if (
                "fetch first" in error_msg
                or "non-fast-forward" in error_msg
                or "rejected" in error_msg
            ):
                console.print(
                    "🔄 [blue]Repository has diverged. "
                    "Attempting to sync and retry...[/blue]"
                )
                try:
                    # Try to pull/sync changes first
                    self.pull_changes(remote_name, branch_name)

                    # Retry the push
                    console.print("🔄 Retrying push after sync...")
                    retry_push_info = origin.push(branch_name)

                    # Check retry results
                    if retry_push_info:
                        retry_result = retry_push_info[0]
                        if retry_result.flags & (
                            retry_result.ERROR | retry_result.REJECTED
                        ):
                            console.print(
                                f"❌ Retry push failed: {retry_result.summary}"
                            )
                            console.print(
                                "💡 [dim]Manual intervention may be required[/dim]"
                            )
                        else:
                            console.print("✅ Push succeeded after sync!")
                            return
                    else:
                        console.print("✅ Push succeeded after sync!")
                        return

                except Exception as sync_error:
                    console.print(f"❌ Sync and retry failed: {sync_error}")
                    console.print(
                        "💡 [dim]You may need to resolve conflicts manually[/dim]"
                    )

            # Check for authentication/permission errors
            elif (
                "403" in error_msg
                or "denied" in error_msg
                or "authentication failed" in error_msg
                or "unauthorized" in error_msg
            ):
                console.print(f"❌ Authentication/Permission error: {e}")
                if "403" in error_msg or "denied" in error_msg:
                    console.print(
                        "🔑 [yellow]Permission denied during git push[/yellow]"
                    )
                    console.print(
                        "   • For GitLab: Ensure your token has "
                        "[cyan]api[/cyan] scope"
                    )
                    console.print(
                        "   • For GitHub: Ensure your token has "
                        "[cyan]repo[/cyan] scope"
                    )
                    console.print(
                        "   • You may need to regenerate your token with "
                        "proper permissions"
                    )
                elif "authentication" in error_msg or "unauthorized" in error_msg:
                    console.print(
                        "🔐 [yellow]Authentication failed during git push[/yellow]"
                    )
                    console.print("   • Your token may have expired")
                    console.print("   • Check if you have git credentials configured")
                raise
            else:
                # Other errors - try to verify if push actually succeeded
                try:
                    # Fetch to update our view of the remote
                    console.print("🔍 Verifying push status...")
                    origin.fetch()

                    # Compare local and remote commit hashes
                    local_commit = self.repo.head.commit.hexsha
                    try:
                        remote_commit = self.repo.refs[
                            f"{remote_name}/{branch_name}"
                        ].commit.hexsha
                        if local_commit == remote_commit:
                            console.print(
                                "✅ Push actually succeeded (stderr was just noise)"
                            )
                            return
                    except Exception:
                        pass

                    # If we can't verify, show warning but don't fail completely
                    console.print(f"⚠️  Push completed with warnings: {e}")
                    console.print(
                        "💡 [dim]Run 'install-sync repo status' to verify "
                        "sync status[/dim]"
                    )

                except Exception:
                    # If even fetch fails, just show the warning
                    console.print(
                        "⚠️  Push operation completed, but verification failed"
                    )
                    console.print(
                        "💡 [dim]Check your repository manually to verify "
                        "changes[/dim]"
                    )

    def pull_changes(
        self, remote_name: str = "origin", branch_name: str = "main"
    ) -> None:
        """Pull changes from remote repository."""
        try:
            origin = self.repo.remote(remote_name)

            # First fetch to get the latest remote refs
            origin.fetch()

            # Check if we have a local branch
            try:
                local_branch = self.repo.heads[branch_name]
            except IndexError:
                # Create local branch if it doesn't exist
                console.print(f"📝 Creating local branch '{branch_name}'...")
                # Create branch from remote
                remote_ref = self.repo.refs[f"{remote_name}/{branch_name}"]
                local_branch = self.repo.create_head(branch_name, remote_ref)
                local_branch.set_tracking_branch(remote_ref)
                self.repo.heads[branch_name].checkout()
                console.print(f"✅ Created and checked out branch '{branch_name}'")
                return

            # Set up tracking if not already set
            if not local_branch.tracking_branch():
                remote_ref = self.repo.refs[f"{remote_name}/{branch_name}"]
                local_branch.set_tracking_branch(remote_ref)
                console.print(
                    f"🔗 Set up tracking for {branch_name} -> "
                    f"{remote_name}/{branch_name}"
                )

            # Now pull changes
            origin.pull(branch_name)
            console.print(f"✅ Pulled changes from {remote_name}/{branch_name}")

        except GitCommandError as e:
            # Handle specific pull conflict scenarios
            error_msg = str(e).lower()
            if "merge conflict" in error_msg or "conflict" in error_msg:
                console.print(
                    "⚠️ Merge conflicts detected. Manual resolution required."
                )
                console.print(
                    "💡 [dim]Check your repository for conflicts and "
                    "resolve manually[/dim]"
                )
            elif "diverged" in error_msg:
                console.print(
                    "⚠️ Branches have diverged. Consider using --force-with-lease"
                )
                console.print(
                    "💡 [dim]Run 'git pull --rebase' manually to resolve[/dim]"
                )
            else:
                console.print(f"❌ Failed to pull changes: {e}")
            raise

    def get_status(self) -> str:
        """Get git status."""
        try:
            return self.repo.git.status()
        except GitCommandError as e:
            console.print(f"❌ Failed to get git status: {e}")
            return ""

    def get_commit_history(self, limit: int = 10) -> List[dict]:
        """Get recent commit history."""
        try:
            commits = []
            for commit in self.repo.iter_commits(max_count=limit):
                commits.append(
                    {
                        "hash": commit.hexsha[:8],
                        "message": commit.message.strip(),
                        "author": str(commit.author),
                        "date": commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            return commits
        except GitCommandError as e:
            console.print(f"❌ Failed to get commit history: {e}")
            return []
