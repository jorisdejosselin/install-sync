#!/bin/sh
# Install the latest install-sync release on macOS or Linux.
#   curl -fsSL https://raw.githubusercontent.com/jorisdejosselin/install-sync/main/install.sh | sh
# Options (environment): INSTALL_SYNC_VERSION=v1.2.3  INSTALL_DIR=~/.local/bin
set -eu

REPO="jorisdejosselin/install-sync"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"

fail() { echo "install-sync: $*" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v tar >/dev/null 2>&1 || fail "tar is required"

case "$(uname -s)" in
  Linux) os=linux ;;
  Darwin) os=darwin ;;
  *) fail "unsupported OS $(uname -s); on Windows use install.ps1" ;;
esac
case "$(uname -m)" in
  x86_64|amd64) arch=amd64 ;;
  arm64|aarch64) arch=arm64 ;;
  *) fail "unsupported architecture $(uname -m)" ;;
esac

version="${INSTALL_SYNC_VERSION:-}"
if [ -z "$version" ]; then
  # The latest-release URL redirects to .../tag/<version>; no API token needed.
  url=$(curl -fsSLI --connect-timeout 5 -m 30 -o /dev/null -w '%{url_effective}' "https://github.com/$REPO/releases/latest")
  version="${url##*/}"
fi
case "$version" in v*) ;; *) fail "could not determine the latest version (got '$version')" ;; esac

archive="install-sync_${version#v}_${os}_${arch}.tar.gz"
base="https://github.com/$REPO/releases/download/$version"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "→ downloading install-sync $version ($os/$arch)"
curl -fsSL --connect-timeout 5 -m 300 -o "$tmp/$archive" "$base/$archive"
curl -fsSL --connect-timeout 5 -m 30 -o "$tmp/checksums.txt" "$base/checksums.txt"

expected=$(grep " $archive\$" "$tmp/checksums.txt" | cut -d' ' -f1)
[ -n "$expected" ] || fail "no checksum for $archive"
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$tmp/$archive" | cut -d' ' -f1)
else
  actual=$(shasum -a 256 "$tmp/$archive" | cut -d' ' -f1)
fi
[ "$expected" = "$actual" ] || fail "checksum mismatch for $archive"

tar -xzf "$tmp/$archive" -C "$tmp" install-sync
mkdir -p "$INSTALL_DIR"
install -m 0755 "$tmp/install-sync" "$INSTALL_DIR/install-sync"
echo "✓ installed $("$INSTALL_DIR/install-sync" --version) to $INSTALL_DIR"

case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *) echo "! $INSTALL_DIR is not on your PATH; add: export PATH=\"$INSTALL_DIR:\$PATH\"" ;;
esac
echo "next: install-sync init --repo <manifest git url> --profile <name>"
