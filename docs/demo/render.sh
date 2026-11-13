#!/bin/sh
# Re-render docs/demo/demo.gif with VHS in Docker (nothing installed locally).
set -eu
cd "$(dirname "$0")/../.."
VHS_IMAGE=ghcr.io/charmbracelet/vhs:v0.12.1
arch=$(docker version --format '{{.Server.Arch}}')
version=$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//')
mkdir -p docs/demo/bin
GOOS=linux GOARCH="$arch" CGO_ENABLED=0 go build -trimpath \
  -ldflags "-s -w -X main.version=${version:-dev}" -o docs/demo/bin/install-sync ./cmd/install-sync
docker run --rm -v "$PWD:/vhs" "$VHS_IMAGE" docs/demo/demo.tape
rm -rf docs/demo/bin
# A broken demo (e.g. setup failed) renders as a tiny, mostly static GIF.
size=$(wc -c < docs/demo/demo.gif | tr -d ' ')
[ "$size" -gt 500000 ] || { echo "demo.gif is only $size bytes; the demo probably failed" >&2; exit 1; }
echo "✓ docs/demo/demo.gif ($size bytes)"
