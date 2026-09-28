param([switch]$Consent)
$ErrorActionPreference = 'Stop'
if (-not $Consent) { throw 'Explicit local consent required: rerun with -Consent after reading docs/setup.md.' }
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$StartScript = (Resolve-Path (Join-Path $PSScriptRoot 'Start-ShopAssistant.ps1')).Path
if (-not (Test-Path -LiteralPath $Python)) { throw 'Install the local virtual environment first.' }
Push-Location $Root
try {
    & $Python -m shop_assistant doctor
    if ($LASTEXITCODE -ne 0) { throw 'Doctor failed; task not registered.' }
} finally { Pop-Location }
$Answer = Read-Host 'Register logon task for this signed-in user only? Type REGISTER'
if ($Answer -cne 'REGISTER') { throw 'Cancelled without scheduling.' }
$Identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $StartScript) -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $Identity
$Principal = New-ScheduledTaskPrincipal -UserId $Identity -LogonType Interactive -RunLevel LeastPrivilege
$Settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'ShopAssistantLocal' -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'Private dry-run shopping assistant after interactive logon' -ErrorAction Stop | Out-Null
Write-Host 'Task registered for next interactive user logon; not started now.'
