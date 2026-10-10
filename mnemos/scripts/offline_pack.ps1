# 在本机（能正常上网）打包 MNEMOS 离线部署包
# 用法: powershell -ExecutionPolicy Bypass -File meclaw2\scripts\offline_pack.ps1

$ErrorActionPreference = "Stop"
$Meclaw2 = Split-Path $PSScriptRoot -Parent
$RepoRoot = Split-Path $Meclaw2 -Parent
$OutDir = Join-Path $Meclaw2 "offline"
$Wheels = Join-Path $OutDir "wheels"

New-Item -ItemType Directory -Force -Path $Wheels | Out-Null

Write-Host ">>> 下载 pip wheels 到 $Wheels"
python -m pip download -r (Join-Path $Meclaw2 "requirements.txt") -d $Wheels
python -m pip download -r (Join-Path $Meclaw2 "requirements-embedding.txt") -d $Wheels

Write-Host ""
Write-Host "完成。请连同以下目录一起拷到服务器:"
Write-Host "  $Meclaw2\offline\wheels\"
Write-Host "  $Meclaw2\.fastembed_cache\"
Write-Host "  $Meclaw2\          (整个项目，或至少 backend + web + data)"
Write-Host ""
Write-Host "服务器上执行 meclaw2/scripts/offline_install.sh"
