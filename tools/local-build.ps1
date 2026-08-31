# 本地构建 standalone 前端（注入服务器同款 API_TOKEN），产物供上传 frontend-app
$ErrorActionPreference = "Stop"
Set-Location D:\Codefield\Smartutor\frontend

$line = (Get-Content D:\Codefield\Smartutor\.env.build-token.tmp | Where-Object { $_ -match '^API_TOKEN=' } | Select-Object -First 1)
$token = $line.Substring("API_TOKEN=".Length).Trim()
Write-Host "token length: $($token.Length)"

$env:NEXT_PUBLIC_API_TOKEN = $token
$env:BACKEND_URL = "http://127.0.0.1:8000"
$env:NEXT_TELEMETRY_DISABLED = "1"

npm run build
if ($LASTEXITCODE -ne 0) { Write-Error "build failed"; exit 1 }
Write-Host "build ok"
if (Test-Path .next\standalone\server.js) { Write-Host "standalone ok" } else { Write-Error "standalone missing"; exit 1 }
