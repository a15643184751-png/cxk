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

$idsRoot = Resolve-ExistingPath -Label 'ids-standalone' -Candidates @(
    (Join-Path $root 'ids-standalone'),
    'D:\ids\ids-standalone'
)

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = [string]$line
        $trimmed = $trimmed.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#') -or -not $trimmed.Contains('=')) {
            continue
        }
        $name, $value = $trimmed.Split('=', 2)
        if ($name.Trim() -ne $Key) {
            continue
        }
        return $value.Trim().Trim('"').Trim("'")
    }

    return $null
}

function Test-IsLocalUrl {
    param([string]$Url)

    if (-not $Url) {
        return $true
    }

    try {
        $uri = [Uri]$Url
    } catch {
        return $true
    }

    $hostValue = [string]$uri.Host
    $hostValue = $hostValue.ToLowerInvariant()
    return $hostValue -in @('localhost', '127.0.0.1', '0.0.0.0', '::1')
}

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

$idsEnvPath = Join-Path $idsRoot 'ids-backend\.env'
$gatewayDefaultPort = Get-EnvValue -Path $idsEnvPath -Key 'IDS_GATEWAY_DEFAULT_PORT'
$gatewayFrontendUpstream = Get-EnvValue -Path $idsEnvPath -Key 'IDS_GATEWAY_FRONTEND_BASE_URL'
$gatewayBackendUpstream = Get-EnvValue -Path $idsEnvPath -Key 'IDS_GATEWAY_BACKEND_BASE_URL'
$gatewayPortMapJson = Get-EnvValue -Path $idsEnvPath -Key 'IDS_GATEWAY_PORT_MAP'
$remoteGatewayMode =
    (($gatewayFrontendUpstream) -and (-not (Test-IsLocalUrl -Url $gatewayFrontendUpstream))) -or
    (($gatewayBackendUpstream) -and (-not (Test-IsLocalUrl -Url $gatewayBackendUpstream)))

if (-not $gatewayDefaultPort) {
    $gatewayDefaultPort = '8188'
}

$gatewayDefaultPortNumber = 8188
[void][int]::TryParse($gatewayDefaultPort, [ref]$gatewayDefaultPortNumber)

$gatewayPortMappings = @()
if ($gatewayPortMapJson) {
    try {
        $parsedGatewayPortMap = ConvertFrom-Json -InputObject $gatewayPortMapJson -Depth 8
        if ($parsedGatewayPortMap -is [System.Collections.IEnumerable] -and -not ($parsedGatewayPortMap -is [string])) {
            foreach ($item in $parsedGatewayPortMap) {
                if ($null -eq $item) {
                    continue
                }
                $gatewayPortMappings += $item
            }
        } elseif ($parsedGatewayPortMap) {
            $gatewayPortMappings += $parsedGatewayPortMap
        }
    } catch {
        Write-Host "[warn] IDS_GATEWAY_PORT_MAP is not valid JSON and will be ignored." -ForegroundColor Yellow
    }
}

if (-not $remoteGatewayMode) {
    $campusRoot = Resolve-ExistingPath -Label 'CampusSupplyChainSecurityPlatform' -Candidates @(
        (Join-Path $root 'CampusSupplyChainSecurityPlatform'),
        (Join-Path $root 'gongyinglian\workspace\CampusSupplyChainSecurityPlatform'),
        'D:\ids\CampusSupplyChainSecurityPlatform',
        'D:\ids\gongyinglian\workspace\CampusSupplyChainSecurityPlatform'
    )
}

$logDir = Join-Path $root 'runtime\startup-logs\campus-ids'
$bundledPythonRoot = Join-Path $root 'runtime\tools\python311'
$bundledNodeRoot = Join-Path $root 'runtime\tools\nodejs'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$services = @(
    @{
        Name = 'IDS Gateway'
        Port = $gatewayDefaultPortNumber
        WorkDir = Join-Path $idsRoot 'ids-backend'
        FilePath = 'python'
        DependencyType = 'backend'
        VenvPath = Join-Path $root 'runtime\venvs\ids-backend'
        PythonSitePackages = Join-Path $root 'runtime\pydeps\ids-backend'
        Args = @('-m', 'uvicorn', 'app.gateway_main:app', '--host', '0.0.0.0', '--port', [string]$gatewayDefaultPortNumber)
        HealthUrl = "http://127.0.0.1:$gatewayDefaultPortNumber/gateway/health"
        LogBase = "ids-gateway-$gatewayDefaultPortNumber"
    }
)

foreach ($gatewayPortMapping in $gatewayPortMappings) {
    $mappingPortText = [string]$gatewayPortMapping.ingress_port
    $mappingPort = 0
    if (-not [int]::TryParse($mappingPortText, [ref]$mappingPort) -or $mappingPort -le 0) {
        continue
    }
    if ($mappingPort -eq $gatewayDefaultPortNumber) {
        continue
    }

    $mappingName = [string]$gatewayPortMapping.display_name
    if (-not $mappingName) {
        $mappingName = [string]$gatewayPortMapping.site_key
    }
    if (-not $mappingName) {
        $mappingName = "Gateway-$mappingPort"
    }

    $services += @{
        Name = "IDS Gateway [$mappingName]"
        Port = $mappingPort
        WorkDir = Join-Path $idsRoot 'ids-backend'
        FilePath = 'python'
        DependencyType = 'backend'
        VenvPath = Join-Path $root 'runtime\venvs\ids-backend'
        PythonSitePackages = Join-Path $root 'runtime\pydeps\ids-backend'
        Args = @('-m', 'uvicorn', 'app.gateway_main:app', '--host', '0.0.0.0', '--port', [string]$mappingPort)
        HealthUrl = "http://127.0.0.1:$mappingPort/gateway/health"
        LogBase = "ids-gateway-$mappingPort"
    }
}

if (-not $remoteGatewayMode) {
    $services += @(
        @{
            Name = 'Campus Frontend'
            Port = 5173
            WorkDir = Join-Path $campusRoot 'frontend'
            FilePath = 'npm.cmd'
            DependencyType = 'frontend'
            Args = @('run', 'dev', '--', '--host', '0.0.0.0', '--port', '5173')
            HealthUrl = 'http://127.0.0.1:5173'
            LogBase = 'campus-frontend-5173'
        },
        @{
            Name = 'Campus Backend'
            Port = 8166
            WorkDir = Join-Path $campusRoot 'backend'
            FilePath = 'python'
            DependencyType = 'backend'
            VenvPath = Join-Path $root 'runtime\venvs\campus-backend'
            PythonSitePackages = Join-Path $root 'runtime\pydeps\campus-backend'
            Args = @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8166')
            HealthUrl = 'http://127.0.0.1:8166/api/health'
            LogBase = 'campus-backend-8166'
        }
    )
}

$services += @(
    @{
        Name = 'IDS Frontend'
        Port = 5175
        WorkDir = Join-Path $idsRoot 'ids-frontend'
        FilePath = 'npm.cmd'
        DependencyType = 'frontend'
        Args = @('run', 'dev', '--', '--host', '0.0.0.0', '--port', '5175')
        HealthUrl = 'http://127.0.0.1:5175'
        LogBase = 'ids-frontend-5175'
    },
    @{
        Name = 'IDS Backend'
        Port = 8170
        WorkDir = Join-Path $idsRoot 'ids-backend'
        FilePath = 'python'
        DependencyType = 'backend'
        VenvPath = Join-Path $root 'runtime\venvs\ids-backend'
        PythonSitePackages = Join-Path $root 'runtime\pydeps\ids-backend'
        Args = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8170')
        HealthUrl = 'http://127.0.0.1:8170/api/health'
        LogBase = 'ids-backend-8170'
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
Write-Host '=== Campus + IDS Startup ===' -ForegroundColor Green
Write-Host ''
if ($remoteGatewayMode) {
    Write-Host "[info] Remote gateway mode detected. Campus local services will be skipped." -ForegroundColor Cyan
    Write-Host "       Frontend upstream: $gatewayFrontendUpstream" -ForegroundColor Cyan
    Write-Host "       Backend upstream:  $gatewayBackendUpstream" -ForegroundColor Cyan
    Write-Host ''
}

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
Write-Host 'Campus site and IDS are ready.' -ForegroundColor Green
Write-Host ("IDS Gateway:     http://127.0.0.1:{0}" -f $gatewayDefaultPortNumber)
foreach ($gatewayPortMapping in $gatewayPortMappings) {
    $mappingPortText = [string]$gatewayPortMapping.ingress_port
    $mappingPort = 0
    if (-not [int]::TryParse($mappingPortText, [ref]$mappingPort) -or $mappingPort -le 0) {
        continue
    }
    if ($mappingPort -eq $gatewayDefaultPortNumber) {
        continue
    }
    $mappingName = [string]$gatewayPortMapping.display_name
    if (-not $mappingName) {
        $mappingName = [string]$gatewayPortMapping.site_key
    }
    if (-not $mappingName) {
        $mappingName = "gateway-$mappingPort"
    }
    Write-Host ("IDS Gateway {0}: http://127.0.0.1:{1}" -f $mappingName, $mappingPort)
}
if (-not $remoteGatewayMode) {
    Write-Host 'Campus Frontend: http://127.0.0.1:5173'
    Write-Host 'Campus Backend:  http://127.0.0.1:8166/api/health'
} else {
    Write-Host "Gateway Frontend Upstream: $gatewayFrontendUpstream"
    Write-Host "Gateway Backend Upstream:  $gatewayBackendUpstream"
}
Write-Host 'IDS Frontend:    http://127.0.0.1:5175'
Write-Host 'IDS Backend:     http://127.0.0.1:8170/api/health'

$detectedIpv4Addresses = @(Get-LocalIpv4Addresses)
if ($detectedIpv4Addresses.Count -gt 0) {
    Write-Host ''
    Write-Host 'Detected machine IPv4 addresses:' -ForegroundColor Cyan
    foreach ($ipAddress in $detectedIpv4Addresses) {
        Write-Host ("  {0}" -f $ipAddress)
    }
    Write-Host ''
    Write-Host 'Example external access URLs:' -ForegroundColor Cyan
    Write-Host ("  Campus gateway -> http://{0}:{1}" -f $detectedIpv4Addresses[0], $gatewayDefaultPortNumber)
    foreach ($gatewayPortMapping in $gatewayPortMappings) {
        $mappingPortText = [string]$gatewayPortMapping.ingress_port
        $mappingPort = 0
        if (-not [int]::TryParse($mappingPortText, [ref]$mappingPort) -or $mappingPort -le 0) {
            continue
        }
        if ($mappingPort -eq $gatewayDefaultPortNumber) {
            continue
        }
        $mappingName = [string]$gatewayPortMapping.display_name
        if (-not $mappingName) {
            $mappingName = [string]$gatewayPortMapping.site_key
        }
        if (-not $mappingName) {
            $mappingName = "gateway-$mappingPort"
        }
        Write-Host ("  {0} -> http://{1}:{2}" -f $mappingName, $detectedIpv4Addresses[0], $mappingPort)
    }
    Write-Host ("  IDS console    -> http://{0}:5175" -f $detectedIpv4Addresses[0])
}
