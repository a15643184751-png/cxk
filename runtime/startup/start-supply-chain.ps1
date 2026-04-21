param(
    [switch]$ForceRestart
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$launcherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeRoot = Split-Path -Parent $launcherDir
$root = Split-Path -Parent $runtimeRoot
$helperPath = Join-Path $launcherDir 'startup-common.ps1'
if (-not (Test-Path -LiteralPath $helperPath)) {
    throw "Startup helper not found: $helperPath"
}

. $helperPath

function Get-LocalIpv4Addresses {
    try {
        return @(
            Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
                Where-Object {
                    $_.IPAddress -and
                    $_.IPAddress -notmatch '^127\.' -and
                    $_.IPAddress -notmatch '^169\.254\.'
                } |
                Select-Object -ExpandProperty IPAddress -Unique
        )
    } catch {
        return @()
    }
}

$campusRoot = Resolve-ExistingPath -Label 'CampusSupplyChainSecurityPlatform' -Candidates @(
    (Join-Path $root 'campus-supply-chain'),
    (Join-Path $root 'CampusSupplyChainSecurityPlatform'),
    (Join-Path $root 'gongyinglian\workspace\CampusSupplyChainSecurityPlatform'),
    'D:\ids\CampusSupplyChainSecurityPlatform',
    'D:\ids\gongyinglian\workspace\CampusSupplyChainSecurityPlatform'
)

$logDir = Join-Path $root 'runtime\startup-logs\supply-chain'
$bundledPythonRoot = Join-Path $root 'runtime\tools\python311'
$bundledNodeRoot = Join-Path $root 'runtime\tools\nodejs'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$services = @(
    @{
        Name = 'Supply Chain Frontend'
        Port = 5173
        WorkDir = Join-Path $campusRoot 'frontend'
        FilePath = 'npm.cmd'
        DependencyType = 'frontend'
        Args = @('run', 'dev', '--', '--host', '0.0.0.0', '--port', '5173')
        HealthUrl = 'http://127.0.0.1:5173'
        LogBase = 'supply-chain-frontend-5173'
    },
    @{
        Name = 'Supply Chain Backend'
        Port = 8166
        WorkDir = Join-Path $campusRoot 'backend'
        FilePath = 'python'
        DependencyType = 'backend'
        VenvPath = Join-Path $root 'runtime\venvs\campus-backend'
        PythonSitePackages = Join-Path $root 'runtime\pydeps\campus-backend'
        Args = @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8166')
        HealthUrl = 'http://127.0.0.1:8166/api/health'
        LogBase = 'supply-chain-backend-8166'
    }
)

Refresh-SessionPath

$pythonCmd = Ensure-CommandPath -Label 'python' -Candidates @(
    (Join-Path $bundledPythonRoot 'python.exe'),
    (Join-Path $bundledPythonRoot 'python'),
    'python.exe',
    'python',
    'py.exe',
    'py'
) -WingetId 'Python.Python.3.12'

$npmCmd = Ensure-CommandPath -Label 'npm' -Candidates @(
    (Join-Path $bundledNodeRoot 'npm.cmd'),
    (Join-Path $bundledNodeRoot 'npm.ps1'),
    'npm.cmd',
    (Join-Path $env:ProgramFiles 'nodejs\npm.cmd'),
    (Join-Path ${env:ProgramFiles(x86)} 'nodejs\npm.cmd'),
    (Join-Path $env:APPDATA 'npm\npm.cmd'),
    'npm',
    'npm.ps1',
    (Join-Path $env:ProgramFiles 'nodejs\npm.ps1'),
    (Join-Path ${env:ProgramFiles(x86)} 'nodejs\npm.ps1'),
    (Join-Path $env:APPDATA 'npm\npm.ps1')
) -WingetId 'OpenJS.NodeJS.LTS'

foreach ($service in $services) {
    if ($service.FilePath -eq 'python') {
        $service.FilePath = $pythonCmd
    } elseif ($service.FilePath -eq 'npm.cmd') {
        $service.FilePath = $npmCmd
    }
}

Write-Host ''
Write-Host '=== Supply Chain Startup ===' -ForegroundColor Green
Write-Host ''

$summary = foreach ($service in $services) {
    $procId = Start-ServiceProcess -Service $service -ForceRestart:$ForceRestart -LogDir $logDir -PythonCmd $pythonCmd -NpmCmd $npmCmd
    $healthy = Test-UrlReady -Url $service.HealthUrl -TimeoutSeconds 40
    [PSCustomObject]@{
        Name = $service.Name
        Port = $service.Port
        Url = $service.HealthUrl
        Pid = $procId
        Healthy = $healthy
    }
}

Write-Host ''
Write-Host '=== Service Status ===' -ForegroundColor Green
$summary | Sort-Object Port | Format-Table -AutoSize

$failed = @($summary | Where-Object { -not $_.Healthy })
if ($failed.Count -gt 0) {
    Write-Host ''
    Write-Host '[warn] Some services did not become healthy. Check logs under:' -ForegroundColor Yellow
    Write-Host "       $logDir" -ForegroundColor Yellow
    exit 1
}

Write-Host ''
Write-Host 'Supply chain site is ready.' -ForegroundColor Green
Write-Host 'Frontend: http://127.0.0.1:5173'
Write-Host 'Backend:  http://127.0.0.1:8166/api/health'

$detectedIpv4Addresses = @(Get-LocalIpv4Addresses)
if ($detectedIpv4Addresses.Count -gt 0) {
    Write-Host ''
    Write-Host 'Detected machine IPv4 addresses:' -ForegroundColor Cyan
    foreach ($ipAddress in $detectedIpv4Addresses) {
        Write-Host ("  {0}" -f $ipAddress)
    }
    Write-Host ''
    Write-Host 'Example external access URLs:' -ForegroundColor Cyan
    Write-Host ("  Supply Chain Frontend -> http://{0}:5173" -f $detectedIpv4Addresses[0])
    Write-Host ("  Supply Chain Backend  -> http://{0}:8166/api/health" -f $detectedIpv4Addresses[0])
}
