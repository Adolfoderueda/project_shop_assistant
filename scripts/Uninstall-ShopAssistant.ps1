param([switch]$Consent)
$ErrorActionPreference = 'Stop'
if (-not $Consent) { throw 'Explicit local consent required to unregister the task.' }
Unregister-ScheduledTask -TaskName 'ShopAssistantLocal' -Confirm:$false -ErrorAction Stop
Write-Host 'Task removed; private configuration, profiles and data were not deleted.'
