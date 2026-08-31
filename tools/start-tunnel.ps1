# 一键启动外网隧道（本地代理 + SSH 反向隧道）
# 用法：powershell -ExecutionPolicy Bypass -File tools\start-tunnel.ps1
# 停止：Stop-Process -Id <两个PID>
$ErrorActionPreference = "Stop"

$pyPath = "D:\Anaconda\python.exe"
if (-not (Test-Path $pyPath)) { $pyPath = "python" }

$proxy = Start-Process -FilePath $pyPath `
    -ArgumentList "`"$PSScriptRoot\proxy.py`" 1080" `
    -WindowStyle Hidden -PassThru
Write-Host "[1/2] 本地代理已启动 (PID $($proxy.Id), 127.0.0.1:1080)"

Start-Sleep -Seconds 1

$ssh = Start-Process -FilePath "ssh" `
    -ArgumentList "-N -R 1080:127.0.0.1:1080 match-server" `
    -WindowStyle Hidden -PassThru
Write-Host "[2/2] SSH 反向隧道已建立 (PID $($ssh.Id))"
Write-Host ""
Write-Host "服务器外网可用。验证: ssh match-server 'curl -sI https://github.com'"
Write-Host "停止隧道: Stop-Process -Id $($proxy.Id),$($ssh.Id)"
