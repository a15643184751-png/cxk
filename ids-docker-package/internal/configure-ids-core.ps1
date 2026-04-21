param(
    [ValidateSet('local', 'registry')]
    [string]$DeployMode,
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
    [string]$DomainCode,
    [string]$ImagePrefix,
    [string]$ImageTag = 'latest',
    [switch]$SingleRepo
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $scriptDir
$localScript = Join-Path $scriptDir 'deploy-ids-runtime.ps1'
$registryScript = Join-Path $scriptDir 'deploy-ids-registry.ps1'

function Write-Section {
    param(
        [string]$Title,
        [string]$Description = ''
    )

    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor DarkGreen
    Write-Host $Title -ForegroundColor Green
    if ($Description) {
        Write-Host $Description -ForegroundColor Gray
    }
    Write-Host ('=' * 72) -ForegroundColor DarkGreen
}

function Prompt-Text {
    param(
        [string]$Label,
        [string]$Default = '',
        [switch]$AllowEmpty
    )

    if ($UseDefaults) {
        return [string]$Default
    }

    while ($true) {
        $suffix = if ([string]::IsNullOrWhiteSpace($Default)) { '' } else { " [$Default]" }
        $value = Read-Host "$Label$suffix"
        if ([string]::IsNullOrWhiteSpace($value)) {
            if ($AllowEmpty) {
                return ''
            }
            if (-not [string]::IsNullOrWhiteSpace($Default)) {
                return $Default
            }
            Write-Host 'Please enter a value.' -ForegroundColor Yellow
            continue
        }
        return $value.Trim()
    }
}

function Prompt-Port {
    param(
        [string]$Label,
        [int]$Default
    )

    if ($UseDefaults) {
        return [int]$Default
    }

    while ($true) {
        $value = Read-Host "$Label [$Default]"
        if ([string]::IsNullOrWhiteSpace($value)) {
            return [int]$Default
        }

        $parsed = 0
        if ([int]::TryParse($value.Trim(), [ref]$parsed) -and $parsed -ge 1 -and $parsed -le 65535) {
            return $parsed
        }

        Write-Host 'Port must be an integer between 1 and 65535.' -ForegroundColor Yellow
    }
}

function Prompt-Choice {
    param(
        [string]$Label,
        [string[]]$Options,
        [string]$Default
    )

    if ($UseDefaults) {
        return $Default
    }

    $choiceText = $Options -join '/'
    while ($true) {
        $value = Read-Host "$Label [$Default] ($choiceText)"
        if ([string]::IsNullOrWhiteSpace($value)) {
            return $Default
        }

        $candidate = $value.Trim().ToLowerInvariant()
        foreach ($option in $Options) {
            if ($candidate -eq $option.ToLowerInvariant()) {
                return $option
            }
        }

        Write-Host "Please choose one of: $choiceText" -ForegroundColor Yellow
    }
}

function Prompt-Bool {
    param(
        [string]$Label,
        [bool]$Default
    )

    if ($UseDefaults) {
        return $Default
    }

    $hint = if ($Default) { 'Y/n' } else { 'y/N' }
    while ($true) {
        $value = Read-Host "$Label [$hint]"
        if ([string]::IsNullOrWhiteSpace($value)) {
            return $Default
        }

        switch ($value.Trim().ToLowerInvariant()) {
            'y' { return $true }
            'yes' { return $true }
            '1' { return $true }
            'n' { return $false }
            'no' { return $false }
            '0' { return $false }
            default { Write-Host 'Please enter y or n.' -ForegroundColor Yellow }
        }
    }
}

$resolvedDeployMode = if ($PSBoundParameters.ContainsKey('DeployMode')) {
    $DeployMode
}
elseif ($PSBoundParameters.ContainsKey('ImagePrefix')) {
    'registry'
}
else {
    'local'
}

$resolvedDeployMode = Prompt-Choice -Label 'Deployment mode' -Options @('local', 'registry') -Default $resolvedDeployMode

$consolePortValue = if ($PSBoundParameters.ContainsKey('ConsolePort')) { $ConsolePort } else { 5175 }
$apiPortValue = if ($PSBoundParameters.ContainsKey('ApiPort')) { $ApiPort } else { 8170 }
$gatewayPortValue = if ($PSBoundParameters.ContainsKey('GatewayPort')) { $GatewayPort } else { 8188 }
$frontendIpValue = if ($PSBoundParameters.ContainsKey('FrontendIp')) { $FrontendIp } else { '127.0.0.1' }
$frontendPortValue = if ($PSBoundParameters.ContainsKey('FrontendPort')) { $FrontendPort } else { 5173 }
$backendIpValue = if ($PSBoundParameters.ContainsKey('BackendIp')) { $BackendIp } else { '127.0.0.1' }
$backendPortValue = if ($PSBoundParameters.ContainsKey('BackendPort')) { $BackendPort } else { 8166 }
$defaultSiteKeyValue = if ($PSBoundParameters.ContainsKey('DefaultSiteKey')) { $DefaultSiteKey } else { 'campus_supply_chain' }
$defaultSiteNameValue = if ($PSBoundParameters.ContainsKey('DefaultSiteName')) { $DefaultSiteName } else { '校园供应链' }
$displaySiteLabelValue = if ($PSBoundParameters.ContainsKey('DisplaySiteLabel')) { $DisplaySiteLabel } else { '校园供应链主站' }
$domainCodeValue = if ($PSBoundParameters.ContainsKey('DomainCode')) { $DomainCode } else { 'Campus-Link-A' }

Write-Section -Title 'Core Deployment Config' -Description 'Only the parameters that actually affect ports, upstream targets and deployment source are shown here.'
$consolePortValue = Prompt-Port -Label 'IDS console port' -Default $consolePortValue
$apiPortValue = Prompt-Port -Label 'IDS API port' -Default $apiPortValue
$gatewayPortValue = Prompt-Port -Label 'IDS gateway port' -Default $gatewayPortValue
$frontendIpValue = Prompt-Text -Label 'Frontend upstream IP' -Default $frontendIpValue
$frontendPortValue = Prompt-Port -Label 'Frontend upstream port' -Default $frontendPortValue
$backendIpValue = Prompt-Text -Label 'Backend upstream IP' -Default $backendIpValue
$backendPortValue = Prompt-Port -Label 'Backend upstream port' -Default $backendPortValue
$defaultSiteKeyValue = Prompt-Text -Label 'Default site key' -Default $defaultSiteKeyValue
$defaultSiteNameValue = Prompt-Text -Label 'Default site name' -Default $defaultSiteNameValue
$displaySiteLabelValue = Prompt-Text -Label 'Display site label' -Default $displaySiteLabelValue
$domainCodeValue = Prompt-Text -Label 'Domain code' -Default $domainCodeValue

if ($resolvedDeployMode -eq 'registry') {
    $imagePrefixValue = if ($PSBoundParameters.ContainsKey('ImagePrefix')) { $ImagePrefix } else { '' }
    $imageTagValue = if ($PSBoundParameters.ContainsKey('ImageTag')) { $ImageTag } else { 'latest' }
    $singleRepoValue = if ($PSBoundParameters.ContainsKey('SingleRepo')) { [bool]$SingleRepo } else { $true }

    Write-Section -Title 'Registry Image Source' -Description 'Provide only the real image location. Everything else stays on defaults unless you override it.'
    $imagePrefixValue = Prompt-Text -Label 'Registry image prefix' -Default $imagePrefixValue
    if ([string]::IsNullOrWhiteSpace($imagePrefixValue)) {
        throw 'Registry image prefix is required when deployment mode is registry.'
    }
    $imageTagValue = Prompt-Text -Label 'Registry image tag' -Default $imageTagValue
    $singleRepoValue = Prompt-Bool -Label 'Use single-repo layout' -Default $singleRepoValue

    Write-Host ''
    Write-Host "Deploy mode: $resolvedDeployMode" -ForegroundColor White
    Write-Host "Image prefix: $imagePrefixValue" -ForegroundColor White
    Write-Host "Image tag: $imageTagValue" -ForegroundColor White

    $invokeParams = @{
        ImagePrefix = $imagePrefixValue
        Tag = $imageTagValue
        UseDefaults = $true
        ConsolePort = $consolePortValue
        ApiPort = $apiPortValue
        GatewayPort = $gatewayPortValue
        FrontendIp = $frontendIpValue
        FrontendPort = $frontendPortValue
        BackendIp = $backendIpValue
        BackendPort = $backendPortValue
        DefaultSiteKey = $defaultSiteKeyValue
        DefaultSiteName = $defaultSiteNameValue
        DisplaySiteLabel = $displaySiteLabelValue
        DomainCode = $domainCodeValue
    }
    if ($SkipStart) {
        $invokeParams.SkipStart = $true
    }
    if ($singleRepoValue) {
        $invokeParams.SingleRepo = $true
    }

    & $registryScript @invokeParams
}
else {
    Write-Host ''
    Write-Host "Deploy mode: $resolvedDeployMode" -ForegroundColor White
    Write-Host 'Build source: local Docker build context' -ForegroundColor White

    $invokeParams = @{
        UseDefaults = $true
        ConsolePort = $consolePortValue
        ApiPort = $apiPortValue
        GatewayPort = $gatewayPortValue
        FrontendIp = $frontendIpValue
        FrontendPort = $frontendPortValue
        BackendIp = $backendIpValue
        BackendPort = $backendPortValue
        DefaultSiteKey = $defaultSiteKeyValue
        DefaultSiteName = $defaultSiteNameValue
        DisplaySiteLabel = $displaySiteLabelValue
        DomainCode = $domainCodeValue
    }
    if ($SkipStart) {
        $invokeParams.SkipStart = $true
    }

    & $localScript @invokeParams
}
