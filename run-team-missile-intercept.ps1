param(
    [int]$Port = 5174,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $repoRoot "team-missile-intercept\backend"
$commonInfoDir = Join-Path $repoRoot "team-missile-intercept\common-info"

if (-not (Test-Path -LiteralPath $backendDir)) {
    throw "Backend directory not found: $backendDir"
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $pythonCommand) {
    throw "Python was not found on PATH. Install Python and the backend requirements first."
}

$escapedBackendDir = $backendDir.Replace("'", "''")
$escapedPython = $pythonCommand.Source.Replace("'", "''")
$serverCommand = "`$env:PORT = '$Port'; Set-Location -LiteralPath '$escapedBackendDir'; & '$escapedPython' server.py"

$serverProcess = Start-Process -FilePath "powershell.exe" `
    -WorkingDirectory $backendDir `
    -ArgumentList @("-NoExit", "-Command", $serverCommand) `
    -PassThru

$browserOpened = $false
if (-not $NoBrowser) {
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/healthz" -TimeoutSec 1
            if ($response.StatusCode -eq 200) {
                Start-Process "http://127.0.0.1:$Port/" | Out-Null
                $browserOpened = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
}

Write-Host "Started the active demo backend in a new PowerShell window."
Write-Host "Backend PID: $($serverProcess.Id)"
Write-Host "Backend shell: $backendDir"
Write-Host "Common info hub: $commonInfoDir"
Write-Host "Browser URL: http://127.0.0.1:$Port/"
if (-not $NoBrowser -and -not $browserOpened) {
    Write-Host "The server may still be starting. Open the browser URL manually if needed."
}
