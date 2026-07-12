$ErrorActionPreference = "Stop"

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment not found. Run: python -m venv .venv"
}

& $Python -m unittest discover -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed; build aborted." }

& $Python -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot "Annotator.spec")
if ($LASTEXITCODE -ne 0) { throw "Executable build failed." }

Write-Host "Build complete: $PSScriptRoot\dist\Annotator.exe"
