# Configura PATH correttamente leggendo dalle chiavi di registro (perché questa sessione non lo vede ancora)
$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$userPath     = [Environment]::GetEnvironmentVariable('Path', 'User')
$env:Path     = $machinePath + ';' + $userPath

Write-Host "*** Ho configurato il percorso di PostgreSQL per questa sessione ***" -ForegroundColor Cyan

# Apre una nuova finestra PowerShell interattiva con psql già pronto all'uso
Start-Process "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -WindowStyle Normal `
  -NoNewWindow `
  -ArgumentList "-NoProfile", "-Command", @"
    Write-Host '*** Digita ora la password di postgres e premi Enter quando richiesto ***' -ForegroundColor Green; 
    psql -U postgres;
"@