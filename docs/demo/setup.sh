#!/bin/sh
# Hidden part of the demo: runs inside the VHS container and builds a sandbox
# (a small manifest in a local bare "remote" repo). Never run this on a real machine.
# It is sourced into the demo shell, so it must not leave `set -e` behind:
# `install-sync diff` exits 2 when it finds drift.
set -e
export DEBIAN_FRONTEND=noninteractive
echo 'quiet "2";' > /etc/apt/apt.conf.d/99demo-quiet   # keep apt output short in the video
apt-get update >/dev/null && apt-get install -y git >/dev/null 2>&1
# Docker Desktop can take a moment to show a freshly built file in the mount.
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -f /vhs/docs/demo/bin/install-sync ] && break; sleep 1; done
install -m 0755 /vhs/docs/demo/bin/install-sync /usr/local/bin/install-sync

export GIT_AUTHOR_NAME=demo GIT_AUTHOR_EMAIL=demo@example.com
export GIT_COMMITTER_NAME=demo GIT_COMMITTER_EMAIL=demo@example.com
rm -rf /demo ~/.config/install-sync ~/.local/share/install-sync
mkdir -p /demo/seed/profiles && cd /demo/seed
cat > packages.yaml <<'YAML'
packages:
  jq:
    winget: jqlang.jq
  iterm2:
    brew: {cask: true}
YAML
cat > profiles/base-cli.yaml <<'YAML'
description: CLI tools wanted on every machine
packages:
  - git
  - curl
  - tree
YAML
cat > profiles/work.yaml <<'YAML'
description: Work dev environment
include:
  - base-cli
packages:
  - htop
  - iterm2
YAML
cat > profiles/personal.yaml <<'YAML'
include:
  - base-cli
packages:
  - spotify
YAML
git init -q -b main . && git add -A && git commit -qm "manifest"
git init -q --bare -b main /demo/my-software.git && git push -q /demo/my-software.git main
cd /vhs && rm -rf /demo/seed
set +e
export PS1='\[\e[38;5;141m\]$\[\e[0m\] '
clear
