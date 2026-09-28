$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Install the local virtual environment first.' }
Set-Location -LiteralPath $Root
& $Python -m shop_assistant run
exit $LASTEXITCODE
