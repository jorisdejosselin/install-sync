# Personal Access Token Setup Guide

This guide provides detailed instructions for creating Personal Access Tokens (PAT) for GitHub and GitLab to use with install-sync.

## Why Do I Need a Token?

install-sync needs to create a repository on your behalf to store your package tracking data. Personal Access Tokens are secure ways to authenticate with Git platforms without using your password.

## GitHub Token Setup

### Step-by-Step Instructions

1. **Navigate to GitHub Settings**
   - Go to [GitHub Personal Access Tokens](https://github.com/settings/tokens)
   - Or: GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)

2. **Generate New Token**
   - Click **"Generate new token"**
   - Select **"Generate new token (classic)"**

3. **Configure Token Settings**
   - **Note**: Enter a descriptive name like "install-sync repository creation"
   - **Expiration**: Choose based on your security preferences:
     - 30 days (recommended for security)
     - 90 days
     - Custom date
     - No expiration (not recommended)

4. **Select Required Scopes**

   **For Private Repositories (Recommended):**
   - ✅ **`repo`** - Full control of private repositories
     - This automatically includes:
       - `repo:status` - Access commit status
       - `repo_deployment` - Access deployment status
       - `public_repo` - Access public repositories
       - `repo:invite` - Access repository invitations
       - `security_events` - Read and write security events

   **For Public Repositories Only:**
   - ✅ **`public_repo`** - Access public repositories

5. **Generate and Save**
   - Click **"Generate token"**
   - **⚠️ Copy the token immediately** - you won't see it again!
   - Store it securely (password manager recommended)

### Required Permissions Explained

| Scope | Purpose | Needed For |
|-------|---------|------------|
| `repo` | Full repository access | Creating private repos, pushing code |
| `public_repo` | Public repository access | Creating public repos only |
| `repo:status` | Commit status access | Repository management |
| `repo_deployment` | Deployment status | Repository management |

## GitLab Token Setup

### Step-by-Step Instructions

1. **Navigate to GitLab Settings**
   - Go to [GitLab Personal Access Tokens](https://gitlab.com/-/profile/personal_access_tokens)
   - Or: GitLab → User Settings → Access Tokens

2. **Create New Token**
   - Click **"Add new token"**

3. **Configure Token Settings**
   - **Token name**: Enter descriptive name like "install-sync repository creation"
   - **Expiration date**: Choose based on security preferences:
     - 30 days (recommended)
     - 90 days
     - Custom date
     - No expiration (not recommended)

4. **Select Required Scopes**

   **Recommended (Full Access):**
   - ✅ **`api`** - Complete read/write access to the API
     - This includes repository creation, management, and git push/pull operations
     - **IMPORTANT**: This is the only scope that provides all necessary permissions

   **⚠️ Common Issue - Insufficient Permissions:**
   If you only select minimal scopes, you may encounter push failures:
   - ❌ **`read_api`** + **`write_repository`** - May work for existing repos but insufficient for full setup
   - ❌ **`read_repository`** + **`write_repository`** - Cannot create repositories

   **Why `api` scope is required:**
   - Creates repositories via GitLab API
   - Enables git push operations to the repository
   - Provides access to project settings and management

5. **Create and Save**
   - Click **"Create personal access token"**
   - **⚠️ Copy the token immediately** - you won't see it again!
   - Store it securely

### Required Scopes Explained

| Scope | Purpose | Needed For |
|-------|---------|------------|
| `api` | Complete API access | Creating repos, managing projects |
| `read_api` | Read API access | Reading project information |
| `write_repository` | Repository write access | Pushing code changes |
| `read_repository` | Repository read access | Accessing repository data |

## Security Best Practices

### Token Management
- 🔐 **Use password managers** to store tokens securely
- ⏰ **Set expiration dates** - tokens should expire to limit exposure
- 🔄 **Rotate tokens regularly** - create new ones before old ones expire
- 🗑️ **Delete unused tokens** immediately
- 👀 **Monitor token usage** in platform settings

### install-sync Security
- ✅ **Tokens are used only once** during repository setup
- ✅ **Tokens are NOT stored** by install-sync
- ✅ **Repositories default to private** for your security
- ✅ **No sensitive data** is tracked beyond package names and dates

### What install-sync Does With Your Token
1. **Repository Creation**: Creates a new repository with your chosen name
2. **Initial Setup**: Adds README and basic configuration
3. **Immediate Disposal**: Token is discarded after setup completion

### What install-sync Does NOT Do
- ❌ Store or cache your token
- ❌ Access other repositories
- ❌ Modify existing repositories
- ❌ Access personal information
- ❌ Perform any actions beyond repository creation

## Troubleshooting

### Token Creation Issues

**"Insufficient permissions" error:**
- Ensure you selected the correct scopes (`repo` for GitHub, `api` for GitLab)
- For organizations, you may need owner permissions

**Token not working:**
- Verify the token was copied correctly (no extra spaces)
- Check if the token has expired
- Ensure your account has permission to create repositories

**Setup hangs during git push (common with GitLab):**
- This usually means insufficient token permissions
- GitLab: Ensure you selected **`api`** scope, not just `write_repository`
- GitHub: Ensure you selected **`repo`** scope
- The repository may be created successfully, but git operations fail
- You can manually configure git later if needed

**"Remote origin already exists" error:**
- This happens when running setup multiple times
- The improved version now handles this gracefully
- Update to the latest version or run `install-sync repo fix`
- The setup will update the remote URL if it differs

**Repository already exists:**
- install-sync now automatically detects existing repositories
- You'll be prompted to choose: rename, delete, or cancel
- Deletion is permanent and cannot be undone
- Renaming suggests safe alternatives like `repo-name-v2`

**"Error lines received while fetching" but operation succeeds:**
- This is normal Git behavior - stderr output doesn't mean failure
- install-sync now properly distinguishes between warnings and errors
- If you see "✅ Push completed successfully" the operation worked
- This commonly happens with GitLab and some Git configurations

**Push fails with "fetch first" message:**
- Happens when remote repository has initial commits (auto-generated README)
- install-sync now automatically syncs with remote before pushing
- New repositories are created empty to prevent this issue
- For existing repositories, run `install-sync repo fix` to resolve

**Organization repositories:**
- Some organizations restrict token usage
- You may need to enable SSO for the token
- Contact your organization admin if needed

### Platform-Specific Issues

**GitHub:**
- Enable SSO if your organization requires it
- Check if your organization allows personal access tokens
- Ensure you're not hitting rate limits

**GitLab:**
- Verify you have Developer role or higher in your namespace
- Check if your GitLab instance has restrictions on token creation
- For GitLab.com vs self-hosted instances, ensure correct URL

## Alternative: SSH Keys

If you prefer not to use tokens, you can:
1. Set up SSH keys with your Git platform
2. Use `install-sync repo setup` to create the repository structure
3. Manually create the repository on GitHub/GitLab
4. Add the remote manually: `git remote add origin git@github.com:username/repo.git`

However, using tokens with install-sync provides the most seamless experience.

## Token Rotation

When your token expires:
1. Create a new token following the same steps
2. You don't need to re-run `install-sync repo setup`
3. Future git operations will use your configured git credentials
4. Only repository creation requires the token

## Support

If you encounter issues:
- Check the [troubleshooting section](README.md#troubleshooting) in the main README
- Verify your platform's token documentation:
  - [GitHub Token Documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
  - [GitLab Token Documentation](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)
- Open an issue on the install-sync repository
