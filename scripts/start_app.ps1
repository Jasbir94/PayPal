param([switch]$CheckOnly, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

try { Set-Location -LiteralPath $projectRoot } catch {
  Write-Error "APP Shield project folder is unavailable: $projectRoot. Check that its drive is unlocked and the folder is accessible. No folders were recreated."
  exit 2
}

function Stop-Setup([string]$message, [int]$code = 2) {
  Write-Host "`nAPP Shield startup check failed: $message" -ForegroundColor Red
  exit $code
}

$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
  $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
  if (-not $pythonCommand) { $pythonCommand = Get-Command py.exe -ErrorAction SilentlyContinue }
  if (-not $pythonCommand) { Stop-Setup 'Python 3.11 or later is required. Install Python, then create .venv with: py -3 -m venv .venv' }
  $pythonExe = $pythonCommand.Source
}
$pythonVersionText = & $pythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
if ($LASTEXITCODE -ne 0) { Stop-Setup 'Python could not start. Repair the .venv or reinstall Python 3.11+.' }
$pythonVersion = [version]$pythonVersionText.Trim()
if ($pythonVersion -lt [version]'3.11') { Stop-Setup "Python 3.11 or later is required. Found $pythonVersionText." }
try { & $pythonExe -c 'import fastapi, uvicorn, pandas, sklearn' 2>$null } catch { Stop-Setup 'Backend dependencies are missing. Run: .venv\Scripts\python -m pip install -r backend\requirements.txt' }
if ($LASTEXITCODE -ne 0) { Stop-Setup 'Backend dependencies are missing. Run: .venv\Scripts\python -m pip install -r backend\requirements.txt' }

# Uvicorn needs asyncio to create a local socket pair on Windows. In restricted
# environments that operation can hang before Uvicorn emits any logs, so probe
# it with a bounded child process before starting the backend.
$asyncioProbeInfo = [System.Diagnostics.ProcessStartInfo]::new()
$asyncioProbeInfo.FileName = $pythonExe
$asyncioProbeInfo.Arguments = '-c "import asyncio; asyncio.run(asyncio.sleep(0))"'
$asyncioProbeInfo.UseShellExecute = $false
$asyncioProbeInfo.CreateNoWindow = $true
$asyncioProbeInfo.RedirectStandardError = $true
$asyncioProbe = [System.Diagnostics.Process]::new()
$asyncioProbe.StartInfo = $asyncioProbeInfo
try {
  [void]$asyncioProbe.Start()
  if (-not $asyncioProbe.WaitForExit(5000)) {
    $asyncioProbe.Kill()
    $asyncioProbe.WaitForExit()
    Stop-Setup 'Python asyncio startup timed out while creating its Windows socket pair. This environment is blocking a local socket operation; run APP Shield from an unrestricted local Windows session. No security settings were changed.'
  }
  $asyncioProbeError = $asyncioProbe.StandardError.ReadToEnd()
  if ($asyncioProbe.ExitCode -ne 0) {
    Stop-Setup "Python asyncio startup failed: $($asyncioProbeError.Trim())"
  }
} catch {
  Stop-Setup "Python asyncio startup check failed: $($_.Exception.Message)"
} finally {
  $asyncioProbe.Dispose()
}

$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $nodeCommand) { Stop-Setup 'Node.js is required. Install Node.js 20.19+ or 22.12+ and reopen this window.' }
$nodeExe = $nodeCommand.Source
$nodeVersionText = & $nodeExe -p 'process.versions.node'
$nodeVersion = [version]$nodeVersionText.Trim()
if (($nodeVersion.Major -lt 20) -or
    ($nodeVersion.Major -eq 20 -and $nodeVersion -lt [version]'20.19.0') -or
    $nodeVersion.Major -eq 21 -or
    ($nodeVersion.Major -eq 22 -and $nodeVersion -lt [version]'22.12.0')) {
  Stop-Setup "Node.js 20.19+ or 22.12+ is required for Vite. Found $nodeVersionText."
}
$viteEntry = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $viteEntry)) { Stop-Setup 'Frontend dependencies are missing. Run: cd frontend; npm ci' }

Write-Host "Python $pythonVersionText · Node.js $nodeVersionText"
Write-Host 'Checking or safely initializing the bundled synthetic demo data and baseline models…'
$initOutput = & $pythonExe -m scripts.initialize_demo 2>&1
if ($LASTEXITCODE -ne 0) {
  $initOutput | ForEach-Object { Write-Host $_ }
  Stop-Setup 'Demo data or baseline model files need repair. Existing partial files were preserved; see docs/TROUBLESHOOTING.md.'
}
$initOutput | ForEach-Object { Write-Host $_ }
if ($CheckOnly) { Write-Host 'Preflight passed. Start APP Shield by running start.bat.' -ForegroundColor Green; exit 0 }

$logDirectory = Join-Path $projectRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$apiOut = Join-Path $logDirectory 'api.out.log'
$apiErr = Join-Path $logDirectory 'api.err.log'
$webOut = Join-Path $logDirectory 'frontend.out.log'
$webErr = Join-Path $logDirectory 'frontend.err.log'

function Test-Listening([int]$port) {
  try { return [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction Stop | Select-Object -First 1) } catch { return $false }
}
function Wait-Http([string]$url, [int]$seconds = 60) {
  for ($i = 0; $i -lt $seconds; $i++) {
    try { $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2; if ($response.StatusCode -eq 200) { return $true } } catch { }
    Start-Sleep -Seconds 1
  }
  return $false
}

if (Test-Listening 8000) {
  if (-not (Wait-Http 'http://127.0.0.1:8000/ready' 2)) { Stop-Setup 'Port 8000 is already in use by a service that is not APP Shield-ready. Stop that service and retry.' }
  Write-Host 'Backend is already ready.'
} else {
  Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr | Out-Null
  if (-not (Wait-Http 'http://127.0.0.1:8000/ready')) {
    if (Test-Path $apiErr) { Get-Content $apiErr -Tail 25 | ForEach-Object { Write-Host $_ } }
    Stop-Setup 'The backend did not become ready. See logs\api.err.log and docs/TROUBLESHOOTING.md.'
  }
}

if (Test-Listening 5173) {
  if (-not (Wait-Http 'http://127.0.0.1:5173/')) { Stop-Setup 'Port 5173 is in use by an unresponsive frontend. Stop that service and retry.' }
  Write-Host 'Frontend is already responding.'
} else {
  $viteEntryArgument = '"' + $viteEntry + '"'
  Start-Process -FilePath $nodeExe -ArgumentList @($viteEntryArgument,'--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput $webOut -RedirectStandardError $webErr | Out-Null
  if (-not (Wait-Http 'http://127.0.0.1:5173/')) {
    if (Test-Path $webErr) { Get-Content $webErr -Tail 25 | ForEach-Object { Write-Host $_ } }
    Stop-Setup 'The frontend did not become ready. See logs\frontend.err.log and docs/TROUBLESHOOTING.md.'
  }
}

Write-Host "`nAPP Shield is ready:" -ForegroundColor Green
Write-Host '  Control center: http://127.0.0.1:5173/'
Write-Host '  API health:     http://127.0.0.1:8000/health'
Write-Host '  API docs:       http://127.0.0.1:8000/docs'
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5173/' }
