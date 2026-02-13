$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    uv sync --python 3.12
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if (-not (Test-Path -LiteralPath 'apps/web/dist/index.html')) {
    Push-Location 'apps/web'
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
Write-Host 'ResolveDesk: http://localhost:8000'
& '.venv/Scripts/python.exe' -m uvicorn resolvedesk.api:app --host 127.0.0.1 --port 8000
