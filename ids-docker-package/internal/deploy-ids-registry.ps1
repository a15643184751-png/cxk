param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePrefix,
    [string]$Tag = 'latest',
    [switch]$SingleRepo,
    [switch]$UseDefaults,
    [switch]$SkipStart,
    [int]$ConsolePort,
    [int]$ApiPort,
    [int]$GatewayPort,
    [string]$FrontendIp,
    [int]$FrontendPort,
    [string]$BackendIp,
    [int]$BackendPort,
    [string]$DefaultSiteKey,
    [string]$DefaultSiteName,
    [string]$DisplaySiteLabel,
    [string]$DomainCode
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::UTF8

function Assert-LastExitCode {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptDir
$runtimeScript = Join-Path $scriptDir 'deploy-ids-runtime.ps1'
$composePath = Join-Path $packageRoot 'docker-compose.generated.yml'
$registryComposePath = Join-Path $packageRoot 'docker-compose.registry.generated.yml'

$invokeArgs = @('-ExecutionPolicy', 'Bypass', '-File', $runtimeScript, '-SkipStart')
if ($UseDefaults) { $invokeArgs += '-UseDefaults' }
foreach ($item in @(
    @{ Key = 'ConsolePort'; Value = $ConsolePort; Bound = $PSBoundParameters.ContainsKey('ConsolePort') },
    @{ Key = 'ApiPort'; Value = $ApiPort; Bound = $PSBoundParameters.ContainsKey('ApiPort') },
    @{ Key = 'GatewayPort'; Value = $GatewayPort; Bound = $PSBoundParameters.ContainsKey('GatewayPort') },
    @{ Key = 'FrontendIp'; Value = $FrontendIp; Bound = $PSBoundParameters.ContainsKey('FrontendIp') },
    @{ Key = 'FrontendPort'; Value = $FrontendPort; Bound = $PSBoundParameters.ContainsKey('FrontendPort') },
    @{ Key = 'BackendIp'; Value = $BackendIp; Bound = $PSBoundParameters.ContainsKey('BackendIp') },
    @{ Key = 'BackendPort'; Value = $BackendPort; Bound = $PSBoundParameters.ContainsKey('BackendPort') },
    @{ Key = 'DefaultSiteKey'; Value = $DefaultSiteKey; Bound = $PSBoundParameters.ContainsKey('DefaultSiteKey') },
    @{ Key = 'DefaultSiteName'; Value = $DefaultSiteName; Bound = $PSBoundParameters.ContainsKey('DefaultSiteName') },
    @{ Key = 'DisplaySiteLabel'; Value = $DisplaySiteLabel; Bound = $PSBoundParameters.ContainsKey('DisplaySiteLabel') },
    @{ Key = 'DomainCode'; Value = $DomainCode; Bound = $PSBoundParameters.ContainsKey('DomainCode') }
)) {
    if ($item.Bound) {
        $invokeArgs += "-$($item.Key)"
        $invokeArgs += [string]$item.Value
    }
}

& powershell @invokeArgs

if ($SingleRepo) {
    $runtimeImage = "${ImagePrefix}:runtime-$Tag"
    $frontendImage = "${ImagePrefix}:frontend-$Tag"
}
else {
    $runtimeImage = "$ImagePrefix-runtime:$Tag"
    $frontendImage = "$ImagePrefix-frontend:$Tag"
}

$composeContent = Get-Content -LiteralPath $composePath -Raw -Encoding UTF8
$composeContent = $composeContent -replace "ids-backend:`r?`n\s+build:`r?`n\s+context: \./ids-backend", "ids-backend:`n    image: $runtimeImage"
$composeContent = $composeContent -replace "ids-gateway:`r?`n\s+build:`r?`n\s+context: \./ids-backend", "ids-gateway:`n    image: $runtimeImage"
$composeContent = $composeContent -replace "ids-frontend:`r?`n\s+build:`r?`n\s+context: \./ids-frontend", "ids-frontend:`n    image: $frontendImage"
[System.IO.File]::WriteAllText($registryComposePath, $composeContent, [System.Text.UTF8Encoding]::UTF8)

Write-Host "拉取运行镜像: $runtimeImage" -ForegroundColor Cyan
docker pull $runtimeImage
Assert-LastExitCode 'docker pull runtime image'
Write-Host "拉取前端镜像: $frontendImage" -ForegroundColor Cyan
docker pull $frontendImage
Assert-LastExitCode 'docker pull frontend image'

docker compose --project-directory $packageRoot -f $registryComposePath config | Out-Null
Assert-LastExitCode 'docker compose config'
Write-Host "镜像部署编排文件: $registryComposePath" -ForegroundColor Gray

if ($SkipStart) {
    Write-Host '[info] 已生成 registry 部署编排文件并完成镜像拉取，未启动容器。' -ForegroundColor Yellow
    exit 0
}

docker compose --project-directory $packageRoot -f $registryComposePath up -d
Assert-LastExitCode 'docker compose up'
Write-Host '镜像部署完成。' -ForegroundColor Green
