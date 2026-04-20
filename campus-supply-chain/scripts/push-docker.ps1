#Requires -Version 5.1
<#
Build and push Docker images.

Examples:
  .\scripts\push-docker.ps1 -DockerUser "your-dockerhub-user"
  .\scripts\push-docker.ps1 -Registry "registry.example.com/namespace"
  .\scripts\push-docker.ps1 -DockerUser "your-user" -Tag "v1.0.0"
#>
param(
    [string] $DockerUser = "",
    [string] $Registry = "",
    [string] $RepoName = "campussupplychainsecurityplatform",
    [string] $Tag = "latest"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$prefix = $null
if ($Registry) {
    $prefix = $Registry.Trim().TrimEnd("/")
}
elseif ($DockerUser) {
    $prefix = $DockerUser.Trim()
}
if (-not $prefix) {
    Write-Error "Provide -DockerUser or -Registry."
}

# Single repository, two tags:
#   <prefix>/<repo>:backend-<tag>
#   <prefix>/<repo>:frontend-<tag>
$repo = $RepoName.Trim()
if (-not $repo) {
    Write-Error "RepoName cannot be empty."
}

$env:BACKEND_IMAGE = "${prefix}/${repo}:backend-${Tag}"
$env:FRONTEND_IMAGE = "${prefix}/${repo}:frontend-${Tag}"

Write-Host "Images to push:" -ForegroundColor Cyan
Write-Host "  $($env:BACKEND_IMAGE)"
Write-Host "  $($env:FRONTEND_IMAGE)"
Write-Host ""
Write-Host "If needed, login first: docker login" -ForegroundColor Yellow
Write-Host ""

docker compose build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose push
exit $LASTEXITCODE
