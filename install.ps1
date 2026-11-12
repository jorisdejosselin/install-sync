# Install the latest install-sync release on Windows.
#   irm https://raw.githubusercontent.com/jorisdejosselin/install-sync/main/install.ps1 | iex
# Options (environment): $env:INSTALL_SYNC_VERSION = 'v1.2.3'; $env:INSTALL_DIR = "$HOME\.local\bin"
$ErrorActionPreference = 'Stop'

$Repo = 'jorisdejosselin/install-sync'
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { Join-Path $HOME '.local\bin' }

$arch = switch ($env:PROCESSOR_ARCHITECTURE) {
    'AMD64' { 'amd64' }
    'ARM64' { 'arm64' }
    default { throw "unsupported architecture $env:PROCESSOR_ARCHITECTURE" }
}

$version = $env:INSTALL_SYNC_VERSION
if (-not $version) {
    $version = (Invoke-RestMethod -TimeoutSec 30 "https://api.github.com/repos/$Repo/releases/latest").tag_name
}
if (-not $version.StartsWith('v')) { throw "could not determine the latest version (got '$version')" }

$archive = "install-sync_$($version.Substring(1))_windows_$arch.zip"
$base = "https://github.com/$Repo/releases/download/$version"
$tmp = Join-Path ([IO.Path]::GetTempPath()) ([IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    Write-Host "→ downloading install-sync $version (windows/$arch)"
    Invoke-WebRequest -UseBasicParsing -TimeoutSec 300 "$base/$archive" -OutFile (Join-Path $tmp $archive)
    Invoke-WebRequest -UseBasicParsing -TimeoutSec 30 "$base/checksums.txt" -OutFile (Join-Path $tmp 'checksums.txt')

    $line = Get-Content (Join-Path $tmp 'checksums.txt') | Where-Object { $_ -match " $([regex]::Escape($archive))$" }
    if (-not $line) { throw "no checksum for $archive" }
    $expected = ($line -split ' ')[0]
    $actual = (Get-FileHash -Algorithm SHA256 (Join-Path $tmp $archive)).Hash.ToLower()
    if ($expected -ne $actual) { throw "checksum mismatch for $archive" }

    Expand-Archive -Path (Join-Path $tmp $archive) -DestinationPath $tmp -Force
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Copy-Item (Join-Path $tmp 'install-sync.exe') (Join-Path $InstallDir 'install-sync.exe') -Force
    $installed = & (Join-Path $InstallDir 'install-sync.exe') --version
    Write-Host "✓ installed $installed to $InstallDir"
} finally {
    Remove-Item -Recurse -Force $tmp
}

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($userPath -split ';') -notcontains $InstallDir) {
    [Environment]::SetEnvironmentVariable('Path', "$userPath;$InstallDir", 'User')
    Write-Host "✓ added $InstallDir to your user PATH (open a new terminal)"
}
Write-Host 'next: install-sync init --repo <manifest git url> --profile <name>'
