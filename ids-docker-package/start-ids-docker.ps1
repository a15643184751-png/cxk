$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::UTF8

$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$docsDir = Join-Path $packageRoot 'docs'
$snapshotPath = Join-Path $docsDir 'bootstrap-noise.latest.json'
$coreScript = Join-Path $packageRoot 'internal\configure-ids-core.ps1'
$forwardArgs = @($args)

New-Item -ItemType Directory -Force -Path $docsDir | Out-Null

function Has-Flag {
    param(
        [string[]]$Items,
        [string[]]$Candidates
    )

    foreach ($item in $Items) {
        foreach ($candidate in $Candidates) {
            if ($item -ieq $candidate) {
                return $true
            }
        }
    }

    return $false
}

function Write-Section {
    param(
        [string]$Title,
        [string]$Description = ''
    )

    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    Write-Host $Title -ForegroundColor Cyan
    if ($Description) {
        Write-Host $Description -ForegroundColor Gray
    }
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
}

function Write-NoiseLine {
    param(
        [int]$Index,
        [int]$Total,
        [string]$Label,
        [string]$State,
        [string]$Payload,
        [bool]$UseDefaults
    )

    $prefix = '[{0:d2}/{1:d2}]' -f $Index, $Total
    Write-Host ("{0} {1,-34} => {2,-10} :: {3}" -f $prefix, $Label, $State, $Payload) -ForegroundColor White
    if (-not $UseDefaults) {
        Start-Sleep -Milliseconds 90
    }
}

function New-HexToken {
    return ('0x{0}' -f ((Get-Random -Minimum 268435456 -Maximum 4294967295).ToString('X8')))
}

$useDefaults = Has-Flag -Items $forwardArgs -Candidates @('-UseDefaults', '--use-defaults')
$lines = @(
    @{ label = 'Edge telemetry uplink'; state = 'LOCKED'; payload = 'phase-bus=' + (New-HexToken) },
    @{ label = 'Carrier entropy balancer'; state = 'WARM'; payload = 'drift=' + (Get-Random -Minimum 3 -Maximum 18) + '.7ms' },
    @{ label = 'Northbound packet varnish'; state = 'PASS'; payload = 'layer-mask=amber/green' },
    @{ label = 'Session relay checksum'; state = 'SYNC'; payload = 'window=' + (Get-Random -Minimum 32 -Maximum 96) + ' slots' },
    @{ label = 'Pseudo control fabric'; state = 'OPEN'; payload = 'mesh-tag=relay-' + (Get-Random -Minimum 11 -Maximum 77) },
    @{ label = 'Spectral route envelope'; state = 'STABLE'; payload = 'segment=' + (Get-Random -Minimum 201 -Maximum 799) },
    @{ label = 'Shadow packet echo'; state = 'READY'; payload = 'ghost-copy=enabled' },
    @{ label = 'Auxiliary trust ribbon'; state = 'GREEN'; payload = 'token=' + (New-HexToken) },
    @{ label = 'Elastic ingress lantern'; state = 'IDLE'; payload = 'probe=soft-start' },
    @{ label = 'Vector corridor sampler'; state = 'TRACK'; payload = 'capture-ring=' + (Get-Random -Minimum 2 -Maximum 9) },
    @{ label = 'Fallback lattice shim'; state = 'MAP'; payload = 'bridge=node-' + (Get-Random -Minimum 3 -Maximum 18) },
    @{ label = 'Synthetic channel decor'; state = 'ORNATE'; payload = 'banner-seed=' + (Get-Random -Minimum 1001 -Maximum 9009) }
)

Write-Section -Title 'Edge Runtime Bootstrap Console' -Description 'Presentation bootstrap enabled. Decorative diagnostics will scroll first, then control will hand off to the compact deployment configurator.'

for ($i = 0; $i -lt $lines.Count; $i++) {
    $entry = $lines[$i]
    Write-NoiseLine -Index ($i + 1) -Total $lines.Count -Label $entry.label -State $entry.state -Payload $entry.payload -UseDefaults $useDefaults
}

$snapshot = [ordered]@{
    mode = 'bootstrap_noise'
    saved_at = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    forwarded_args = $forwardArgs
    handoff_target = 'internal/configure-ids-core.ps1'
    noise = $lines
}

[System.IO.File]::WriteAllText(
    $snapshotPath,
    ($snapshot | ConvertTo-Json -Depth 8),
    [System.Text.UTF8Encoding]::UTF8
)

Write-Host ''
Write-Host "Noise snapshot: $snapshotPath" -ForegroundColor DarkGray
Write-Host 'Switching to compact core deployment configurator...' -ForegroundColor Cyan
Write-Host ''

& powershell -ExecutionPolicy Bypass -File $coreScript @forwardArgs
exit $LASTEXITCODE
