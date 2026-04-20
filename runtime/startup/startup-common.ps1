function Refresh-SessionPath {
    $parts = @()

    foreach ($scope in @('Process', 'Machine', 'User')) {
        $pathValue = [Environment]::GetEnvironmentVariable('Path', $scope)
        if ([string]::IsNullOrWhiteSpace($pathValue)) {
            continue
        }

        foreach ($segment in ($pathValue -split ';')) {
            if ([string]::IsNullOrWhiteSpace($segment)) {
                continue
            }

            $normalized = $segment.Trim()
            if ($parts -notcontains $normalized) {
                $parts += $normalized
            }
        }
    }

    $env:Path = ($parts -join ';')
}

function Resolve-ExistingPath {
    param(
        [string]$Label,
        [string[]]$Candidates
    )

    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "$Label not found. Checked paths: $($Candidates -join ', ')"
}

function Resolve-CommandPath {
    param(
        [string]$Label,
        [string[]]$Candidates
    )

    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        $command = Get-Command $candidate -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command -and $command.Path) {
            return $command.Path
        }

        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Invoke-NativeCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $supportsNativePreference = $null -ne (Get-Variable -Name 'PSNativeCommandUseErrorActionPreference' -ErrorAction SilentlyContinue)

    if ($supportsNativePreference) {
        $previousNativePreference = $script:PSNativeCommandUseErrorActionPreference
        $script:PSNativeCommandUseErrorActionPreference = $false
    }

    $ErrorActionPreference = 'Continue'

    try {
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference

        if ($supportsNativePreference) {
            $script:PSNativeCommandUseErrorActionPreference = $previousNativePreference
        }
    }

    return [PSCustomObject]@{
        ExitCode = $exitCode
        Output = @($output)
    }
}

function Invoke-PythonTempScript {
    param(
        [string]$PythonCmd,
        [string]$ScriptBody,
        [string[]]$Arguments
    )

    $tempScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-" + [System.IO.Path]::GetRandomFileName() + '.py')

    try {
        Set-Content -LiteralPath $tempScriptPath -Value $ScriptBody -Encoding UTF8
        return Invoke-NativeCommand -FilePath $PythonCmd -Arguments (@($tempScriptPath) + $Arguments)
    } finally {
        if (Test-Path -LiteralPath $tempScriptPath) {
            Remove-Item -LiteralPath $tempScriptPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-VenvPythonPath {
    param([string]$VenvPath)

    foreach ($candidate in @(
        (Join-Path $VenvPath 'Scripts\python.exe'),
        (Join-Path $VenvPath 'Scripts\python')
    )) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Test-PythonCommand {
    param([string]$PythonCmd)

    if ([string]::IsNullOrWhiteSpace($PythonCmd) -or -not (Test-Path -LiteralPath $PythonCmd)) {
        return $false
    }

    $probeResult = Invoke-NativeCommand -FilePath $PythonCmd -Arguments @('-c', 'import sys; sys.exit(0)')
    return ($probeResult.ExitCode -eq 0)
}

function Ensure-VenvPython {
    param(
        [string]$BasePythonCmd,
        [string]$VenvPath,
        [string]$ServiceName
    )

    $existingPython = Get-VenvPythonPath -VenvPath $VenvPath
    if ($existingPython -and (Test-PythonCommand -PythonCmd $existingPython)) {
        return $existingPython
    }

    if ($existingPython) {
        Write-Host ("[setup] Existing Python environment for {0} is invalid, recreating..." -f $ServiceName) -ForegroundColor Yellow
        Remove-Item -LiteralPath $VenvPath -Recurse -Force -ErrorAction SilentlyContinue
    }

    New-Item -ItemType Directory -Force -Path $VenvPath | Out-Null
    Write-Host ("[setup] Creating isolated Python environment for {0}..." -f $ServiceName) -ForegroundColor Cyan

    $venvResult = Invoke-NativeCommand -FilePath $BasePythonCmd -Arguments @('-m', 'venv', $VenvPath)
    if ($venvResult.Output.Count -gt 0) {
        $venvResult.Output | ForEach-Object { Write-Host $_ }
    }

    if ($venvResult.ExitCode -ne 0) {
        throw "Failed to create virtual environment for $ServiceName."
    }

    $venvPython = Get-VenvPythonPath -VenvPath $VenvPath
    if (-not $venvPython) {
        throw "Virtual environment for $ServiceName was created but python executable was not found."
    }

    return $venvPython
}

function Install-WithWinget {
    param(
        [string]$Label,
        [string]$PackageId
    )

    $wingetCmd = Resolve-CommandPath -Label 'winget' -Candidates @('winget.exe', 'winget')
    if (-not $wingetCmd) {
        throw "Unable to auto-install $Label because winget is not available on this machine."
    }

    Write-Host ("[setup] Installing {0} with winget..." -f $Label) -ForegroundColor Cyan

    $arguments = @(
        'install',
        '--id', $PackageId,
        '-e',
        '--silent',
        '--accept-package-agreements',
        '--accept-source-agreements',
        '--disable-interactivity'
    )

    $process = Start-Process `
        -FilePath $wingetCmd `
        -ArgumentList $arguments `
        -Wait `
        -PassThru `
        -NoNewWindow

    if ($process.ExitCode -ne 0) {
        throw "winget failed to install $Label (exit code $($process.ExitCode))."
    }

    Refresh-SessionPath
}

function Ensure-CommandPath {
    param(
        [string]$Label,
        [string[]]$Candidates,
        [string]$WingetId
    )

    $resolved = Resolve-CommandPath -Label $Label -Candidates $Candidates
    if ($resolved) {
        return $resolved
    }

    if (-not [string]::IsNullOrWhiteSpace($WingetId)) {
        Install-WithWinget -Label $Label -PackageId $WingetId
        $resolved = Resolve-CommandPath -Label $Label -Candidates $Candidates
    }

    if ($resolved) {
        return $resolved
    }

    throw "$Label not found after automatic installation."
}

function Ensure-Pip {
    param([string]$PythonCmd)

    $probeScript = @'
import importlib.util
import sys

sys.exit(0 if importlib.util.find_spec("pip") else 1)
'@

    $probeResult = Invoke-PythonTempScript -PythonCmd $PythonCmd -ScriptBody $probeScript -Arguments @()
    if ($probeResult.ExitCode -eq 0) {
        return
    }

    Write-Host '[setup] Bootstrapping pip...' -ForegroundColor Cyan
    $ensurePipResult = Invoke-NativeCommand -FilePath $PythonCmd -Arguments @('-m', 'ensurepip', '--upgrade')
    if ($ensurePipResult.Output.Count -gt 0) {
        $ensurePipResult.Output | ForEach-Object { Write-Host $_ }
    }

    if ($ensurePipResult.ExitCode -ne 0) {
        throw 'Failed to bootstrap pip.'
    }
}

function Get-RequirementPackageNames {
    param([string]$RequirementsPath)

    $packages = foreach ($line in Get-Content -LiteralPath $RequirementsPath) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#') -or $trimmed.StartsWith('-')) {
            continue
        }

        $trimmed = $trimmed.Split(';')[0].Trim()
        $trimmed = [regex]::Replace($trimmed, '\[.*?\]', '')
        $name = [regex]::Split($trimmed, '[<>=!~ ]')[0].Trim()

        if (-not [string]::IsNullOrWhiteSpace($name)) {
            $name
        }
    }

    return @($packages | Select-Object -Unique)
}

function Test-PythonPackagesAvailable {
    param(
        [string]$PythonCmd,
        [string[]]$Packages
    )

    if (-not $Packages -or $Packages.Count -eq 0) {
        return $true
    }

    $probeScript = @'
import importlib.metadata
import re
import sys

def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()

required = [normalize(item) for item in sys.argv[1:] if item]
installed = {
    normalize(dist.metadata.get("Name", ""))
    for dist in importlib.metadata.distributions()
    if dist.metadata.get("Name")
}

missing = [name for name in required if name not in installed]
sys.exit(0 if not missing else 1)
'@

    $probeResult = Invoke-PythonTempScript -PythonCmd $PythonCmd -ScriptBody $probeScript -Arguments $Packages
    if ($probeResult.ExitCode -ne 0) {
        return $false
    }

    return $true
}

function Ensure-BackendDependencies {
    param(
        [string]$WorkDir,
        [string]$PythonCmd,
        [string]$ServiceName,
        [string]$VenvPath
    )

    $requirementsPath = Join-Path $WorkDir 'requirements.txt'
    if (-not (Test-Path -LiteralPath $requirementsPath)) {
        return
    }

    Ensure-Pip -PythonCmd $PythonCmd

    $packages = Get-RequirementPackageNames -RequirementsPath $requirementsPath
    $tempRequirementsPath = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-" + [System.IO.Path]::GetRandomFileName() + '.requirements.txt')

    try {
        $normalizedRequirements = Get-Content -LiteralPath $requirementsPath |
            Where-Object {
                $trimmed = $_.Trim()
                $trimmed -and -not $trimmed.StartsWith('#')
            }

        $dependencyHash = [System.BitConverter]::ToString(
            [System.Security.Cryptography.SHA256]::Create().ComputeHash(
                [System.Text.Encoding]::UTF8.GetBytes(($normalizedRequirements -join "`n"))
            )
        ).Replace('-', '').ToLowerInvariant()

        $markerPath = $null
        if (-not [string]::IsNullOrWhiteSpace($VenvPath)) {
            $markerPath = Join-Path $VenvPath '.codex-requirements.sha256'
            if ((Test-Path -LiteralPath $markerPath) -and ((Get-Content -LiteralPath $markerPath -Raw).Trim() -eq $dependencyHash)) {
                return
            }
        } elseif ($packages.Count -gt 0 -and (Test-PythonPackagesAvailable -PythonCmd $PythonCmd -Packages $packages)) {
            return
        }

        Write-Host ("[setup] Installing Python dependencies for {0}..." -f $ServiceName) -ForegroundColor Cyan
        Set-Content -LiteralPath $tempRequirementsPath -Value $normalizedRequirements -Encoding UTF8

        $installArgs = @(
            '-m', 'pip', 'install',
            '--disable-pip-version-check',
            '--no-input',
            '-r', $tempRequirementsPath
        )

        if ([string]::IsNullOrWhiteSpace($VenvPath)) {
            $installArgs += '--user'
        }

        $installResult = Invoke-NativeCommand -FilePath $PythonCmd -Arguments $installArgs
        if ($installResult.Output.Count -gt 0) {
            $installResult.Output | ForEach-Object { Write-Host $_ }
        }

        if ($installResult.ExitCode -ne 0) {
            throw "Failed to install backend dependencies for $ServiceName."
        }

        if ($markerPath) {
            Set-Content -LiteralPath $markerPath -Value $dependencyHash -Encoding ASCII
        }
    } finally {
        if (Test-Path -LiteralPath $tempRequirementsPath) {
            Remove-Item -LiteralPath $tempRequirementsPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Ensure-PlaywrightChromium {
    param(
        [string]$WorkDir,
        [string]$PythonCmd,
        [string]$ServiceName
    )

    $requirementsPath = Join-Path $WorkDir 'requirements.txt'
    if (-not (Test-Path -LiteralPath $requirementsPath)) {
        return
    }

    $usesPlaywright = Select-String -LiteralPath $requirementsPath -Pattern '^\s*playwright(\[.*\])?' -Quiet
    if (-not $usesPlaywright) {
        return
    }

    $browserRoot = Join-Path $env:LOCALAPPDATA 'ms-playwright'
    $hasChromium = @(Get-ChildItem -Path $browserRoot -Filter 'chromium-*' -ErrorAction SilentlyContinue).Count -gt 0
    if ($hasChromium) {
        return
    }

    Write-Host ("[setup] Installing Playwright Chromium for {0}..." -f $ServiceName) -ForegroundColor Cyan
    $playwrightResult = Invoke-NativeCommand -FilePath $PythonCmd -Arguments @('-m', 'playwright', 'install', 'chromium')
    if ($playwrightResult.Output.Count -gt 0) {
        $playwrightResult.Output | ForEach-Object { Write-Host $_ }
    }

    if ($playwrightResult.ExitCode -ne 0) {
        throw "Failed to install Playwright Chromium for $ServiceName."
    }
}

function Test-NpmDependenciesAvailable {
    param(
        [string]$WorkDir,
        [string]$NpmCmd
    )

    $nodeModulesPath = Join-Path $WorkDir 'node_modules'
    return (Test-Path -LiteralPath $nodeModulesPath)
}

function Ensure-FrontendDependencies {
    param(
        [string]$WorkDir,
        [string]$NpmCmd,
        [string]$ServiceName
    )

    $packageJsonPath = Join-Path $WorkDir 'package.json'
    if (-not (Test-Path -LiteralPath $packageJsonPath)) {
        return
    }

    if (Test-NpmDependenciesAvailable -WorkDir $WorkDir -NpmCmd $NpmCmd) {
        return
    }

    Write-Host ("[setup] Installing frontend dependencies for {0}..." -f $ServiceName) -ForegroundColor Cyan
    Push-Location $WorkDir
    try {
        $npmInstallResult = Invoke-NativeCommand -FilePath $NpmCmd -Arguments @('install', '--no-fund', '--no-audit')
        if ($npmInstallResult.Output.Count -gt 0) {
            $npmInstallResult.Output | ForEach-Object { Write-Host $_ }
        }

        if ($npmInstallResult.ExitCode -ne 0) {
            throw "Failed to install frontend dependencies for $ServiceName."
        }
    } finally {
        Pop-Location
    }
}

function Get-PortProcess {
    param([int]$Port)

    return Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
}

function Stop-PortProcess {
    param([int]$Port)

    $connection = Get-PortProcess -Port $Port
    if (-not $connection) {
        return
    }

    try {
        Stop-Process -Id $connection.OwningProcess -Force -ErrorAction Stop
        Start-Sleep -Seconds 1
    } catch {
        throw "Failed to stop process on port ${Port}: $($_.Exception.Message)"
    }
}

function Test-UrlReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        } catch {
        }

        Start-Sleep -Milliseconds 800
    }

    return $false
}

function Start-ServiceProcess {
    param(
        [hashtable]$Service,
        [bool]$ForceRestart,
        [string]$LogDir,
        [string]$PythonCmd,
        [string]$NpmCmd
    )

    if (-not (Test-Path -LiteralPath $Service.WorkDir)) {
        throw "Working directory not found: $($Service.WorkDir)"
    }

    if ($ForceRestart) {
        Stop-PortProcess -Port $Service.Port
    }

    $existing = Get-PortProcess -Port $Service.Port
    if ($existing) {
        Write-Host ("[skip] {0} already listening on {1} (pid={2})" -f $Service.Name, $Service.Port, $existing.OwningProcess) -ForegroundColor Yellow
        return $existing.OwningProcess
    }

    switch ($Service.DependencyType) {
        'frontend' {
            Ensure-FrontendDependencies -WorkDir $Service.WorkDir -NpmCmd $NpmCmd -ServiceName $Service.Name
        }
        'backend' {
            $servicePythonCmd = $PythonCmd
            $useBundledPyDeps = $Service.ContainsKey('PythonSitePackages') `
                -and -not [string]::IsNullOrWhiteSpace($Service.PythonSitePackages) `
                -and (Test-Path -LiteralPath $Service.PythonSitePackages)

            if (-not $useBundledPyDeps -and $Service.ContainsKey('VenvPath') -and -not [string]::IsNullOrWhiteSpace($Service.VenvPath)) {
                $servicePythonCmd = Ensure-VenvPython -BasePythonCmd $PythonCmd -VenvPath $Service.VenvPath -ServiceName $Service.Name
            }

            $Service.FilePath = $servicePythonCmd

            if (-not $useBundledPyDeps) {
                Ensure-BackendDependencies -WorkDir $Service.WorkDir -PythonCmd $servicePythonCmd -ServiceName $Service.Name -VenvPath $Service.VenvPath
            } else {
                $pythonPathEntries = @($Service.WorkDir, $Service.PythonSitePackages)
                if ($env:PYTHONPATH) {
                    $pythonPathEntries += $env:PYTHONPATH
                }
                if (-not $Service.ContainsKey('StartupEnv') -or $null -eq $Service.StartupEnv) {
                    $Service.StartupEnv = @{}
                }
                $Service.StartupEnv['PYTHONPATH'] = (@($pythonPathEntries | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique) -join ';')
            }

            if ($Service.ContainsKey('RequiresPlaywright') -and $Service.RequiresPlaywright) {
                Ensure-PlaywrightChromium -WorkDir $Service.WorkDir -PythonCmd $servicePythonCmd -ServiceName $Service.Name
            }
        }
    }

    $stdoutPath = Join-Path $LogDir ($Service.LogBase + '.log')
    $stderrPath = Join-Path $LogDir ($Service.LogBase + '.err.log')

    $originalEnv = @{}
    try {
        if ($Service.ContainsKey('StartupEnv') -and $null -ne $Service.StartupEnv) {
            foreach ($envKey in $Service.StartupEnv.Keys) {
                $originalEnv[$envKey] = [Environment]::GetEnvironmentVariable($envKey, 'Process')
                [Environment]::SetEnvironmentVariable($envKey, [string]$Service.StartupEnv[$envKey], 'Process')
            }
        }

        $proc = Start-Process `
            -FilePath $Service.FilePath `
            -ArgumentList $Service.Args `
            -WorkingDirectory $Service.WorkDir `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -WindowStyle Hidden `
            -PassThru
    } finally {
        foreach ($envKey in $originalEnv.Keys) {
            [Environment]::SetEnvironmentVariable($envKey, $originalEnv[$envKey], 'Process')
        }
    }

    Write-Host ("[start] {0} on {1} (pid={2})" -f $Service.Name, $Service.Port, $proc.Id) -ForegroundColor Cyan
    return $proc.Id
}
