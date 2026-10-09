# Build FastAPI backend into release/backend/PrintingReconciliationAPI.exe (onedir)
# Requires: backend\.venv with dependencies + pyinstaller

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$OutDir = Join-Path $Root "release\backend"
$WorkDir = Join-Path $Root "release\pyinstaller-work"
$SpecDir = Join-Path $Root "packaging"

Write-Host "==> Building backend sidecar"
if (-not (Test-Path $VenvPython)) {
  throw "Python venv not found at $VenvPython"
}

& $VenvPython -m pip install -q "pyinstaller>=6.0"
if ($LASTEXITCODE -ne 0) { throw "Failed to install PyInstaller" }

# Clean previous outputs — incomplete _internal (missing base_library.zip) causes:
# "Failed to start embedded python interpreter!"
if (Test-Path $OutDir) {
  Remove-Item $OutDir -Recurse -Force
}
if (Test-Path $WorkDir) {
  Remove-Item $WorkDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
New-Item -ItemType Directory -Force -Path $SpecDir | Out-Null

# Seed printer.env for installer (backend-only; never shipped to renderer)
$PackagingEnv = Join-Path $SpecDir "printer.env"
$ProjectEnv = Join-Path $Root ".env"
$ExampleEnv = Join-Path $Root ".env.example"
if (Test-Path $ProjectEnv) {
  Copy-Item $ProjectEnv $PackagingEnv -Force
  Write-Host "Copied project .env -> packaging/printer.env (for first-run seed)"
} elseif (-not (Test-Path $PackagingEnv)) {
  Copy-Item $ExampleEnv $PackagingEnv -Force
  Write-Host "Created packaging/printer.env from .env.example (fill passwords before distributing)"
}

Push-Location $Backend
try {
  # --noupx: UPX-packed DLLs often fail on corporate PCs / Defender.
  # --console: false via --noconsole; keep windowless for Operations.
  & $VenvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --name "PrintingReconciliationAPI" `
    --onedir `
    --noconsole `
    --noupx `
    --distpath $OutDir `
    --workpath $WorkDir `
    --specpath $SpecDir `
    --paths $Backend `
    --contents-directory "_internal" `
    --hidden-import uvicorn.logging `
    --hidden-import uvicorn.loops `
    --hidden-import uvicorn.loops.auto `
    --hidden-import uvicorn.protocols `
    --hidden-import uvicorn.protocols.http `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.websockets `
    --hidden-import uvicorn.protocols.websockets.auto `
    --hidden-import uvicorn.lifespan `
    --hidden-import uvicorn.lifespan.on `
    --hidden-import uvicorn.lifespan.off `
    --hidden-import multipart `
    --hidden-import email.mime.multipart `
    --hidden-import sqlalchemy.dialects.sqlite `
    --hidden-import openpyxl `
    --hidden-import xlrd `
    --hidden-import pandas `
    --hidden-import pydantic `
    --hidden-import httpx `
    --collect-all uvicorn `
    --collect-all fastapi `
    --collect-all starlette `
    --collect-submodules api `
    --collect-submodules services `
    --collect-submodules models `
    --collect-submodules printers `
    "run_server.py"

  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

  # Flatten: electron expects resources/backend/PrintingReconciliationAPI.exe
  $Inner = Join-Path $OutDir "PrintingReconciliationAPI"
  if (Test-Path (Join-Path $Inner "PrintingReconciliationAPI.exe")) {
    Get-ChildItem $Inner | ForEach-Object {
      $dest = Join-Path $OutDir $_.Name
      if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
      Move-Item $_.FullName $dest -Force
    }
    Remove-Item $Inner -Recurse -Force -ErrorAction SilentlyContinue
  }

  $Exe = Join-Path $OutDir "PrintingReconciliationAPI.exe"
  $BaseZip = Join-Path $OutDir "_internal\base_library.zip"
  $PyDll = Join-Path $OutDir "_internal\python312.dll"
  if (-not (Test-Path $Exe)) {
    throw "Expected $Exe was not produced"
  }
  if (-not (Test-Path $PyDll)) {
    throw "Missing python312.dll in _internal - backend bundle is incomplete"
  }
  if (-not (Test-Path $BaseZip)) {
    throw "Missing base_library.zip in _internal - backend will fail with: Failed to start embedded python interpreter! Delete release\pyinstaller-work and retry."
  }

  $zipSize = (Get-Item $BaseZip).Length
  Write-Host "Backend OK: $Exe"
  Write-Host "  python312.dll + base_library.zip ($zipSize bytes) present"
}
finally {
  Pop-Location
}
