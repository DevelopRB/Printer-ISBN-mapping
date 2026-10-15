# Publishes a new version to GitHub Releases; installed apps pick it up automatically.
#
#   npm run release              -> 1.2.3 -> 1.2.4
#   npm run release -- minor     -> 1.2.3 -> 1.3.0
#   npm run release -- major     -> 1.2.3 -> 2.0.0
#
# Needs a GitHub token (repo "Contents: Read and write") in the GH_TOKEN environment variable.
# The token is only used by electron-builder to upload; it is never packaged into the app.

param(
  [ValidateSet("patch", "minor", "major")]
  [string]$Bump = "patch"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $env:GH_TOKEN) {
  $userToken = [Environment]::GetEnvironmentVariable("GH_TOKEN", "User")
  if ($userToken) { $env:GH_TOKEN = $userToken }
}
if (-not $env:GH_TOKEN) {
  Write-Host "GH_TOKEN is not set. Create a GitHub token and save it once with:" -ForegroundColor Red
  Write-Host '  [Environment]::SetEnvironmentVariable("GH_TOKEN", "<your token>", "User")'
  Write-Host "Then open a new terminal and run the release again."
  exit 1
}

$versionFiles = @("package.json", "package-lock.json")
$originals = @{}
foreach ($f in $versionFiles) { $originals[$f] = [System.IO.File]::ReadAllText((Join-Path $Root $f)) }

function Restore-Version {
  foreach ($f in $versionFiles) { [System.IO.File]::WriteAllText((Join-Path $Root $f), $originals[$f]) }
}

function Invoke-Step([string]$Label, [scriptblock]$Command) {
  Write-Host "`n== $Label ==" -ForegroundColor Cyan
  & $Command
  if ($LASTEXITCODE -ne 0) {
    Restore-Version
    Write-Host "`nRelease failed at: $Label. Version number was restored; nothing was published." -ForegroundColor Red
    exit 1
  }
}

$oldVersion = (Get-Content package.json -Raw | ConvertFrom-Json).version
Invoke-Step "Bump version ($Bump)" { npm version $Bump --no-git-tag-version | Out-Null }
$newVersion = (Get-Content package.json -Raw | ConvertFrom-Json).version
Write-Host "Version $oldVersion -> $newVersion"

Invoke-Step "Build frontend + backend" { npm run build }
Invoke-Step "Secret check" { npm run check:secrets }
Invoke-Step "Build installer and publish to GitHub Releases" { npx electron-builder --win nsis --x64 --publish always }

Write-Host "`nPublished version $newVersion." -ForegroundColor Green
Write-Host "Team apps will download it automatically and offer 'Restart Now' (or install when closed)."
Write-Host "Save the version bump in git:"
Write-Host "  git add package.json package-lock.json"
Write-Host "  git commit -m `"Release v$newVersion`""
Write-Host "  git push"
