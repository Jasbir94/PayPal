$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonRoot = Join-Path $projectRoot '.venv\Scripts\'
$viteEntry = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
$targets = Get-CimInstance Win32_Process | Where-Object {
  ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($pythonRoot, [StringComparison]::OrdinalIgnoreCase) -and $_.CommandLine -match 'uvicorn backend\.app\.main:app') -or
  ($_.CommandLine -and $_.CommandLine.IndexOf($viteEntry, [StringComparison]::OrdinalIgnoreCase) -ge 0)
}
if (-not $targets) { Write-Host 'No APP Shield backend or frontend process is running.'; exit 0 }
foreach ($target in $targets) {
  Stop-Process -Id $target.ProcessId -Force
  Write-Host "Stopped APP Shield process $($target.ProcessId)."
}
