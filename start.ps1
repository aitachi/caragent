# miniagent 一键启动脚本（Windows PowerShell）
# 用法:
#   powershell -ExecutionPolicy Bypass -File .\start.ps1          # 安装依赖 + 启动 Web 界面
#   powershell -ExecutionPolicy Bypass -File .\start.ps1 -Mode cli # 终端交互模式
#   powershell -ExecutionPolicy Bypass -File .\start.ps1 -ApiKey sk-xxx
param(
    [string]$ApiKey = $env:MINIAGENT_API_KEY,
    [string]$Mode = "web",              # web | cli
    [int]$Port = 19120
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1) 必须在项目根目录（miniagent 包的父目录）运行
if (-not (Test-Path ".\miniagent\__main__.py")) {
    Write-Host "[错误] 请在 miniagent-main 项目根目录运行本脚本" -ForegroundColor Red
    exit 1
}

# 2) API key：参数 > 环境变量 > 本地 .env（不进 git）
if (-not $ApiKey -and (Test-Path ".\.env.local")) {
    Get-Content ".\.env.local" | ForEach-Object {
        if ($_ -match '^MINIAGENT_API_KEY\s*=\s*(.+)$') { $ApiKey = $Matches[1].Trim() }
    }
}
if (-not $ApiKey) {
    Write-Host "[警告] 未设置 API key（可先启动，但运行任务会报 MINIAGENT_API_KEY 未设置）" -ForegroundColor Yellow
    Write-Host "       三种设置方式: -ApiKey sk-xxx | 环境变量 `$env:MINIAGENT_API_KEY | .env.local 文件" -ForegroundColor Yellow
} else {
    $env:MINIAGENT_API_KEY = $ApiKey
}

# 3) 安装依赖（唯一第三方依赖 requests，已装则秒过）
Write-Host "[1/2] 检查/安装依赖..." -ForegroundColor Cyan
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Write-Host "[错误] 依赖安装失败" -ForegroundColor Red; exit 1 }

# 4) 启动
Write-Host "[2/2] 启动 miniagent ($Mode 模式)..." -ForegroundColor Cyan
if ($Mode -eq "cli") {
    python -m miniagent
} else {
    $env:MINIAGENT_WEB_PORT = "$Port"
    Write-Host ""
    Write-Host "  浏览器打开: http://127.0.0.1:$Port/" -ForegroundColor Green
    Write-Host "  停止服务:  Ctrl+C" -ForegroundColor Green
    Write-Host ""
    python -m miniagent.web
}
