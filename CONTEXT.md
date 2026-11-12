# install-sync

A desired-state manifest for the software on your machines. Git holds what each kind of machine should have, and install-sync brings a machine in line with it, so a fresh laptop can be set up in one go.

## Language

**Manifest**:
The git-tracked folder (catalog plus profiles) describing the desired software state. It is the source of truth; what is actually installed on a machine is compared against it. It can live in its own repo or as a folder inside another repo (e.g. the chezmoi source).
_Avoid_: config.json, tracking data, install log

**Profile**:
A named, reusable set of desired packages for one purpose (e.g. `work`, `work-desktop`, `personal`), not for one OS. It outlives any single machine: a new laptop adopts an existing profile, and the profile is tweaked over time.
_Avoid_: machine profile, profile ID

**Include**:
A profile's reference to another profile whose packages it also wants (e.g. `work-laptop` includes `base-cli` and `k8s`). Shared tool sets are defined once and included, never copied.
_Avoid_: inherit, extend, layer

**Package**:
A tool referenced by its own name (e.g. `jq`, `kubectl`), independent of any OS or package manager. Profiles list packages, never manager-specific names.
_Avoid_: brew:jq, package ID, formula

**Definition**:
The description of how to install one package with each package manager (e.g. `jq: {brew: jq, apt: jq, winget: jqlang.jq}`), including any setup steps such as adding an apt repo, or a script fallback. A package whose name is the same everywhere needs no explicit definition.
_Avoid_: recipe, mapping, install method

**Implied definition**:
The definition assumed when the catalog has none: the package's name, installed with the machine's first package manager in manager order that has it.
_Avoid_: default definition, fallback

**Requires**:
Packages a definition depends on (per package manager), installed before it. Supporting libraries belong here, not in profiles (e.g. Chromium libs under `md-to-pdf`).
_Avoid_: dependencies, deps, prerequisites

**Catalog**:
The single file (`packages.yaml`) in the manifest that holds every definition. Profiles never contain definitions, only package names.
_Avoid_: registry, package database

**Package manager**:
A way of installing packages on a machine (brew, apt, winget, snap, npm, script, …). A machine resolves each package's definition against the package managers it has, in manager order.
_Avoid_: manager, installer, backend

**Manager order**:
The per-OS ranking of package managers used to pick one entry from a definition (default: macOS brew; Linux apt, snap, script; Windows winget). A machine config can override it.
_Avoid_: priority, preference

**Script**:
The package manager of last resort: an install command plus a required check command that tells whether the package is present. Script commands are shown and confirmed before they run.
_Avoid_: custom, manual install, curl install

**Check**:
The command that tells whether a script-installed package is present (e.g. `k9s version`).
_Avoid_: probe, test, verify

**Machine**:
One OS install that applies exactly one profile. A Windows host and its WSL distro are two machines, as are the two sides of a dual boot. Machines are short-lived compared to profiles, are never the place where the desired package list lives, and are not recorded in the manifest at all.
_Avoid_: host, profile

**Apply**:
Bringing a machine in line with its profile by installing what is missing. Apply never uninstalls anything.
_Avoid_: sync, bulk install, install --all

**Upgrade**:
Upgrading a machine's profile packages to the newest version each package manager offers. The manifest never records or pins versions.
_Avoid_: update, bump

**Diff**:
The comparison of a machine's profile against what is actually installed, grouping packages as missing, untracked or unavailable.
_Avoid_: status, drift report

**Missing**:
A package in the machine's profile that is not installed on the machine.

**Untracked**:
A package installed on the machine (as detected by its package manager) that is not in the machine's profile. Untracked packages are reported, never removed.
_Avoid_: orphan, extra, unmanaged

**Unavailable**:
A package in the machine's profile whose definition has no package manager usable on this machine.
_Avoid_: unsupported, skipped

**Adopt**:
Moving untracked packages into the machine's profile without reinstalling them.
_Avoid_: track, import

**Machine config**:
The machine-local, untracked file (`~/.config/install-sync/config.yaml`) that states which profile this machine applies and where the manifest is. It is set explicitly (`install-sync init`, or templated by chezmoi), never derived from hostname or hardware.
_Avoid_: global config, ~/.install-sync.config, profile ID
