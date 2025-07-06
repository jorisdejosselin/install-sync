#!/bin/bash
set -e

# install-sync installation script
# Usage: curl -sSL https://raw.githubusercontent.com/joris/install-sync/main/install.sh | bash

REPO="joris/install-sync"
BINARY_NAME="install-sync"
INSTALL_DIR="$HOME/.local/bin"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect OS and architecture
detect_platform() {
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)

    case "$os" in
        linux*)
            OS="linux"
            ;;
        darwin*)
            OS="darwin"
            ;;
        *)
            log_error "Unsupported operating system: $os"
            exit 1
            ;;
    esac

    case "$arch" in
        x86_64|amd64)
            ARCH="amd64"
            ;;
        arm64|aarch64)
            ARCH="arm64"
            ;;
        *)
            log_error "Unsupported architecture: $arch"
            if [ "$OS" = "darwin" ]; then
                log_info "Falling back to arm64 for macOS"
                ARCH="arm64"
            else
                log_info "Falling back to amd64"
                ARCH="amd64"
            fi
            ;;
    esac

    PLATFORM="${OS}-${ARCH}"
    log_info "Detected platform: $PLATFORM"
}

# Get latest release version
get_latest_version() {
    log_info "Fetching latest release information..."

    local release_url="https://api.github.com/repos/$REPO/releases/latest"

    if command -v curl >/dev/null 2>&1; then
        VERSION=$(curl -s "$release_url" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    elif command -v wget >/dev/null 2>&1; then
        VERSION=$(wget -qO- "$release_url" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    else
        log_error "Neither curl nor wget found. Please install one of them."
        exit 1
    fi

    if [ -z "$VERSION" ]; then
        log_error "Failed to get latest version"
        exit 1
    fi

    log_info "Latest version: $VERSION"
}

# Download and install binary
install_binary() {
    local binary_name="${BINARY_NAME}-${PLATFORM}"
    local download_url="https://github.com/$REPO/releases/download/$VERSION/$binary_name"
    local temp_file="/tmp/$binary_name"

    log_info "Downloading $binary_name..."

    if command -v curl >/dev/null 2>&1; then
        curl -sL "$download_url" -o "$temp_file"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$download_url" -O "$temp_file"
    fi

    if [ ! -f "$temp_file" ]; then
        log_error "Failed to download binary"
        exit 1
    fi

    # Create install directory if it doesn't exist
    mkdir -p "$INSTALL_DIR"

    # Move binary to install directory
    mv "$temp_file" "$INSTALL_DIR/$BINARY_NAME"
    chmod +x "$INSTALL_DIR/$BINARY_NAME"

    log_success "Installed $BINARY_NAME to $INSTALL_DIR/$BINARY_NAME"
}

# Check if binary is in PATH
check_path() {
    if [[ ":$PATH:" == *":$INSTALL_DIR:"* ]]; then
        log_success "$INSTALL_DIR is already in your PATH"
    else
        log_warning "$INSTALL_DIR is not in your PATH"
        log_info "Add the following line to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
        echo "export PATH=\"$INSTALL_DIR:\$PATH\""
        echo ""
        log_info "Or run this command to add it temporarily:"
        echo "export PATH=\"$INSTALL_DIR:\$PATH\""
    fi
}

# Verify installation
verify_installation() {
    if [ -x "$INSTALL_DIR/$BINARY_NAME" ]; then
        log_success "Installation verified!"
        log_info "Run '$BINARY_NAME --help' to get started"

        # Try to run the binary if it's in PATH
        if command -v "$BINARY_NAME" >/dev/null 2>&1; then
            echo ""
            "$BINARY_NAME" --version 2>/dev/null || true
        fi
    else
        log_error "Installation verification failed"
        exit 1
    fi
}

# Main installation flow
main() {
    log_info "Starting install-sync installation..."
    echo ""

    detect_platform
    get_latest_version
    install_binary
    check_path
    verify_installation

    echo ""
    log_success "install-sync has been installed successfully!"
    log_info "Get started with: $BINARY_NAME repo setup"
}

# Run main function
main "$@"
