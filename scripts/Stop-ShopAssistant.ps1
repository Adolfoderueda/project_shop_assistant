$ErrorActionPreference = 'Stop'
Stop-ScheduledTask -TaskName 'ShopAssistantLocal' -ErrorAction Stop
Write-Host 'Worker stopped; pending SQLite inbox/orders/outbox preserved.'
