# Fails the installer build if anything electron-builder packages could carry credentials.
# Checks every packaged source (package.json "files" + "extraResources"):
#   - no .env / *.env file is packaged (only env.example, whose secret values must be empty)
#   - no text file assigns a value to a PASSWORD / SECRET / TOKEN / API_KEY variable
# Only file paths and variable names are printed, never values.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

$Sources = @(
  (Join-Path $Root "electron"),
  (Join-Path $Root "package.json"),
  (Join-Path $Root "release\backend"),
  (Join-Path $Root "frontend\dist"),
  (Join-Path $Root ".env.example")
)
$TextExtensions = @(".env", ".example", ".json", ".js", ".cjs", ".mjs", ".txt", ".yml", ".yaml", ".ini", ".cfg", ".toml", ".html", ".map")
$SecretAssignment = '^\s*(?:export\s+)?([A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY)[A-Z0-9_]*)\s*[=:]\s*["'']?([^"''\s#]+)'

$problems = New-Object System.Collections.Generic.List[string]

foreach ($source in $Sources) {
  if (-not (Test-Path $source)) { continue }
  $files = if ((Get-Item $source).PSIsContainer) { Get-ChildItem $source -Recurse -File -Force } else { @(Get-Item $source) }
  foreach ($file in $files) {
    $name = $file.Name.ToLowerInvariant()
    $isEnvFile = $name -eq ".env" -or $name.EndsWith(".env") -or $name.StartsWith(".env.")
    if ($isEnvFile -and $name -ne ".env.example") {
      $problems.Add("packaged env file: $($file.FullName)")
      continue
    }
    if (-not ($isEnvFile -or $TextExtensions -contains $file.Extension.ToLowerInvariant())) { continue }
    if ($file.Length -gt 5MB) { continue }
    $lineNo = 0
    foreach ($line in [System.IO.File]::ReadLines($file.FullName)) {
      $lineNo++
      if ($line -match $SecretAssignment) {
        $problems.Add("value assigned to $($Matches[1]) in $($file.FullName):$lineNo")
      }
    }
  }
}

if ($problems.Count -gt 0) {
  Write-Host "Refusing to package: possible credentials in packaged files" -ForegroundColor Red
  $problems | ForEach-Object { Write-Host "  $_" }
  exit 1
}
Write-Host "Secret check passed: no credentials in packaged files"
