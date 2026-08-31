#!/bin/bash
# 服务器基础环境配置脚本（幂等可重复执行）
set -e
echo "=== 硬件资源 ==="
nproc; free -h | head -2; df -h / | tail -1

echo "=== 隧道状态 ==="
if timeout 2 bash -c 'echo > /dev/tcp/127.0.0.1/1080' 2>/dev/null; then
  echo "隧道在线"
else
  echo "隧道离线（仅影响外网，USTC镜像不受影响）"
fi

echo "=== 1. apt 换 USTC 镜像源 ==="
if [ -f /etc/apt/sources.list.d/ubuntu.sources ] && ! grep -q mirrors.ustc.edu.cn /etc/apt/sources.list.d/ubuntu.sources; then
  cp /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources.bak
  sed -i 's|http://archive.ubuntu.com/ubuntu/|https://mirrors.ustc.edu.cn/ubuntu/|g; s|http://security.ubuntu.com/ubuntu/|https://mirrors.ustc.edu.cn/ubuntu/|g; s|http://[a-z.]*archive.ubuntu.com/ubuntu/|https://mirrors.ustc.edu.cn/ubuntu/|g' /etc/apt/sources.list.d/ubuntu.sources
  echo "已替换为 USTC 镜像"
else
  echo "已是 USTC 镜像或无需处理"
fi
grep -c mirrors.ustc.edu.cn /etc/apt/sources.list.d/ubuntu.sources || true

echo "=== 2. apt update ==="
apt-get update -qq 2>&1 | tail -3 || true

echo "=== 3. 安装系统依赖 ==="
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq gcc g++ bubblewrap util-linux postgresql postgresql-contrib python3-venv python3-pip unzip 2>&1 | tail -3

echo "=== 4. 版本确认 ==="
gcc --version | head -1
bwrap --version
psql --version
python3 --version

echo "=== 完成 ==="
