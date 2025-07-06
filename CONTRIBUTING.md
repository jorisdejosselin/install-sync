# Contributing to install-sync

## Commit Message Format

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic semantic versioning and changelog generation.

### Commit Message Format

```
<type>: <description>

[optional body]

[optional footer(s)]
```

### Types

- **feat**: A new feature (triggers minor version bump)
- **fix**: A bug fix (triggers patch version bump)
- **perf**: A code change that improves performance (triggers patch version bump)
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **test**: Adding missing tests or correcting existing tests
- **build**: Changes that affect the build system or external dependencies
- **ci**: Changes to our CI configuration files and scripts
- **chore**: Other changes that don't modify src or test files

### Examples

```bash
feat: add Apple Silicon support for macOS binaries
fix: resolve Poetry import conflict on Windows
perf: optimize package installation speed
docs: update installation instructions
refactor: improve error handling in package managers
```

### Breaking Changes

For breaking changes, add `!` after the type and/or add `BREAKING CHANGE:` in the footer:

```bash
feat!: remove deprecated install command
# or
feat: add new configuration format

BREAKING CHANGE: The configuration file format has changed. See migration guide.
```

## Automatic Releases

- **Pull Requests**: Run tests only
- **Merge to Main**: Automatically analyzes commits and creates releases when needed
  - `feat:` commits trigger **minor** version bumps (0.1.0 → 0.2.0)
  - `fix:` and `perf:` commits trigger **patch** version bumps (0.1.0 → 0.1.1)
  - Breaking changes trigger **major** version bumps (0.1.0 → 1.0.0)

## Development Workflow

1. **Create Feature Branch**: `git checkout -b feat/my-feature`
2. **Make Changes**: Follow the coding standards
3. **Commit with Convention**: Use conventional commit messages
4. **Create Pull Request**: Tests will run automatically
5. **Merge to Main**: Release will be created automatically if needed

## Setup Git Message Template

To use the provided commit message template:

```bash
git config commit.template .gitmessage
```

This will help you write properly formatted commit messages.
