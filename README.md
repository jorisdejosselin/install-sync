# install-sync

Keep the software on each of your machines in line with a **git-tracked desired-state manifest**.
Set up a fresh laptop with one command, see what drifted, and let AI agents install tools
without having to know anything about git.

```sh
curl -fsSL https://raw.githubusercontent.com/jorisdejosselin/install-sync/main/install.sh | sh
install-sync init --repo git@gitlab.com:me/my-software.git --profile work
install-sync apply
```

- **Profiles by purpose**: `work`, `personal`, `gaming`, which can `include` shared sets like `base-cli`.
  A new laptop adopts an existing profile; machines are never recorded in the manifest.
- **Packages, not package-manager names**: profiles list `jq`, and the catalog says how to get it with
  brew, apt, winget, snap, npm or a script.
- **Git is invisible**: every command pulls first, and every change is committed and pushed.
- **Apply never uninstalls**. `diff` shows what is *missing*, *untracked* or *unavailable*.

See [CONTEXT.md](CONTEXT.md) for the vocabulary and [docs/adr](docs/adr) for the design decisions.

## Install

| OS | Command |
|---|---|
| macOS / Linux / WSL | `curl -fsSL https://raw.githubusercontent.com/jorisdejosselin/install-sync/main/install.sh \| sh` |
| Windows | `irm https://raw.githubusercontent.com/jorisdejosselin/install-sync/main/install.ps1 \| iex` |

Both install a single static binary to `~/.local/bin` (checksum-verified). Pin a version with
`INSTALL_SYNC_VERSION=v1.0.0`. From source: `go install github.com/jorisdejosselin/install-sync/cmd/install-sync@latest`.

## The manifest

A manifest is a folder in a git repo (its own repo, or a folder inside another one):

```
packages.yaml          # catalog: how to install each package
profiles/
  base-cli.yaml
  k8s.yaml
  work.yaml
  personal.yaml
```

A **profile** lists packages and the profiles it includes:

```yaml
# profiles/work.yaml
description: Work dev environment (WSL on the client laptop)
include: [base-cli, k8s]
packages:
  - azure-cli
  - terraform
  - md-to-pdf
```

The **catalog** holds a definition only where a package needs one. A package without a definition
(or a package manager without an entry) is tried under the package's own name with brew, apt, snap
or winget: the *implied definition*.

```yaml
# packages.yaml
packages:
  jq:
    winget: jqlang.jq                  # brew and apt find "jq" by name
  iterm2:
    brew: {cask: true}
  terraform:
    brew: hashicorp/tap/terraform
    apt:
      repo:                            # added once, before installing
        key: https://apt.releases.hashicorp.com/gpg
        source: deb [arch={arch} signed-by={keyring}] https://apt.releases.hashicorp.com {codename} main
    winget: Hashicorp.Terraform
  kubectl:
    snap: {classic: true}
    winget: Kubernetes.kubectl
  md-to-pdf:
    npm: md-to-pdf
    requires:                          # installed first, where that manager exists
      apt: [libnss3, libgbm1]
  k9s:
    script:                            # last resort; shown and confirmed before it runs
      install: |
        curl -fsSLo /tmp/k9s.deb https://github.com/derailed/k9s/releases/latest/download/k9s_linux_amd64.deb
        sudo apt-get install -y /tmp/k9s.deb
      check: command -v k9s            # required: exits 0 when installed
```

A full, real example lives in [examples/manifest](examples/manifest). JSON Schemas for editor
validation are in [schema/](schema); add a `# yaml-language-server: $schema=…` line at the top of a file.

> Write multi-line scripts as literal blocks (`|`). install-sync rewrites `packages.yaml` when it adds
> definitions; comments survive, but folded (`>`) blocks are joined into one line.

### Which package manager is used

Each machine has a **manager order**, by default:

| OS | Order |
|---|---|
| macOS | brew |
| Linux | apt, snap, script |
| Windows | winget |

npm is always tried last. For each package, the first package manager in the order that has an
entry (or finds it by name) wins. If the package is already installed with any of them, it counts as ok.
A package that nothing on this machine can install is *unavailable*: reported, never an error.

## The machine config

`~/.config/install-sync/config.yaml` is machine-local and never tracked. `init` writes it, or chezmoi templates it:

```yaml
profile: work
manifest: ~/.local/share/install-sync/manifest
managers: [apt, script]   # optional: override the manager order (e.g. no snap)
git:
  push: true              # optional: default true
```

Override its location with `INSTALL_SYNC_CONFIG`.

## Commands

| Command | What it does |
|---|---|
| `init --repo <url> --profile <name>` | Clone the manifest and set this machine's profile. `--manifest <dir>` uses an existing folder; `--create [--include a,b]` makes a new profile. |
| `apply [--yes] [--dry-run]` | Install everything missing. Never uninstalls. |
| `diff [--json]` | List missing / untracked / unavailable packages. |
| `add <pkg>... [--to <profile>] [--manager m --name n] [--cask] [--classic] [--no-install]` | Install here, add to a profile (default: this machine's), and commit and push. |
| `remove <pkg>... [--from <profile>] [--keep]` | Remove from the profile that lists it and uninstall here. Packages from included profiles need `--from`. Other machines are not touched. |
| `adopt [<name>... \| --all] [--to <profile>]` | Move untracked packages into a profile without reinstalling them. |
| `upgrade [<pkg>...]` | Upgrade installed profile packages to the newest version. |
| `status [--json]` | Profile, manifest path, package managers, git state. |
| `profiles [--json]` | Profiles, includes, package counts. |
| `validate [<dir>]` | Check a manifest (useful in the manifest repo's CI). |
| `migrate <config.json> --out <dir>` | Convert a v0 install log into a manifest. |

Global flags: `--offline` (no pull/push), `--no-push` (commit only).

### For scripts and AI agents

- Exit codes: `0` ok · `1` error · `2` drift found (`diff`) · `3` needs confirmation (a script install without `--yes`).
- `--json` on `diff`, `status` and `profiles`. Progress goes to stderr, results to stdout.
- No prompts without a terminal: script installs exit `3` instead of waiting for input.
- To install a tool, run `install-sync add <tool>`. If it is not found by name, the error says
  how to record a definition, e.g. `install-sync add jq --manager winget --name jqlang.jq`.

## Migrating from v0 (the Python version)

v0 kept a per-machine install log in `config.json`, keyed by a hash of the hostname. To move to v1:

```sh
install-sync migrate ~/package-tracking/config.json --out ./my-software
# reorganise ./my-software/profiles by purpose, fill in script installs, then:
cd my-software && git init && git add -A && git commit -m "feat: v1 manifest" && git push
install-sync init --repo <that repo> --profile <name>      # on each machine
install-sync adopt                                         # bring in what is untracked
```

The v0 source is kept at the `v0-python` tag.

## Development

```sh
go test -race ./...
go build -o install-sync ./cmd/install-sync
```

Releases: Conventional Commits on `main` → release-please opens a release PR → merging it tags a
release, and GoReleaser attaches binaries for linux/darwin/windows × amd64/arm64.

## License

MIT
