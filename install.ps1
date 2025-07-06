# install-sync installation script for Windows
# Usage: iwr -useb https://raw.githubusercontent.com/joris/install-sync/main/install.ps1 | iex

param(
    [string]$InstallDir = "$env:USERPROFILE\.local\bin"
)

$ErrorActionPreference = "Stop"

# Configuration
$Repo = "joris/install-sync"
$BinaryName = "install-sync"

# Logging functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Detect platform
function Get-Platform {
    $os = "windows"
    $arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "386" }
    return "$os-$arch"
}

# Get latest release version
function Get-LatestVersion {
    Write-Info "Fetching latest release information..."
    
    try {
        $releaseUrl = "https://api.github.com/repos/$Repo/releases/latest"
        $response = Invoke-RestMethod -Uri $releaseUrl -Method Get
        $version = $response.tag_name
        
        if (-not $version) {
            throw "No version found in response"
        }
        
        Write-Info "Latest version: $version"
        return $version
    }
    catch {
        Write-Error "Failed to get latest version: $_"
        exit 1
    }
}

# Download and install binary
function Install-Binary {
    param(
        [string]$Version,
        [string]$Platform
    )
    
    $binaryName = "$BinaryName-$Platform.exe"
    $downloadUrl = "https://github.com/$Repo/releases/download/$Version/$binaryName"
    $tempFile = "$env:TEMP\$binaryName"
    $finalPath = "$InstallDir\$BinaryName.exe"
    
    Write-Info "Downloading $binaryName..."
    
    try {
        # Create install directory if it doesn't exist
        if (-not (Test-Path $InstallDir)) {
            New-Item -Path $InstallDir -ItemType Directory -Force | Out-Null
        }
        
        # Download binary
        Invoke-WebRequest -Uri $downloadUrl -OutFile $tempFile
        
        if (-not (Test-Path $tempFile)) {
            throw "Download failed - file not found"
        }
        
        # Move to install directory
        Move-Item -Path $tempFile -Destination $finalPath -Force
        
        Write-Success "Installed $BinaryName to $finalPath"
        return $finalPath
    }
    catch {
        Write-Error "Failed to download and install binary: $_"
        exit 1
    }
}

# Check if directory is in PATH
function Test-PathContains {
    param([string]$Directory)
    
    $pathArray = $env:PATH -split ';'
    return $pathArray -contains $Directory
}

# Add directory to PATH
function Add-ToPath {
    param([string]$Directory)
    
    if (Test-PathContains $Directory) {
        Write-Success "$Directory is already in your PATH"
        return
    }
    
    Write-Warning "$Directory is not in your PATH"
    Write-Info "Adding $Directory to your PATH..."
    
    try {
        # Get current user PATH
        $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
        
        # Add new directory if not already present
        if ($currentPath -notlike "*$Directory*") {
            $newPath = if ($currentPath) { "$currentPath;$Directory" } else { $Directory }
            [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
            
            # Update current session PATH
            $env:PATH = "$env:PATH;$Directory"
            
            Write-Success "Added $Directory to your PATH"
            Write-Info "You may need to restart your terminal for the change to take effect"
        }
    }
    catch {
        Write-Warning "Failed to add to PATH automatically: $_"
        Write-Info "Please manually add the following directory to your PATH:"
        Write-Host $Directory -ForegroundColor Cyan
    }
}

# Verify installation
function Test-Installation {
    param([string]$BinaryPath)
    
    if (Test-Path $BinaryPath) {
        Write-Success "Installation verified!"
        Write-Info "Run '$BinaryName --help' to get started"
        
        # Try to run the binary
        try {
            & $BinaryPath --version 2>$null
        }
        catch {
            # Ignore version check errors
        }
        
        return $true
    }
    else {
        Write-Error "Installation verification failed - binary not found at $BinaryPath"
        return $false
    }
}

# Main installation flow
function Main {
    Write-Info "Starting install-sync installation..."
    Write-Host ""
    
    $platform = Get-Platform
    Write-Info "Detected platform: $platform"
    
    $version = Get-LatestVersion
    $binaryPath = Install-Binary -Version $version -Platform $platform
    
    Add-ToPath $InstallDir
    
    if (Test-Installation $binaryPath) {
        Write-Host ""
        Write-Success "install-sync has been installed successfully!"
        Write-Info "Get started with: $BinaryName repo setup"
    }
    else {
        exit 1
    }
}

# Run main function
try {
    Main
}
catch {
    Write-Error "Installation failed: $_"
    exit 1
}