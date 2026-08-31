#!/usr/bin/env bash
# 部署辅助：生成 API_TOKEN 并写入后端 .env 与前端 .env.local（幂等：已存在则复用）
set -euo pipefail

ENV_FILE=/opt/zhixue/backend/.env
LOCAL_ENV=/opt/zhixue/frontend/.env.local

if grep -q '^API_TOKEN=' "$ENV_FILE"; then
  TOKEN=$(grep '^API_TOKEN=' "$ENV_FILE" | cut -d= -f2)
else
  TOKEN=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
  echo "API_TOKEN=$TOKEN" >> "$ENV_FILE"
fi
printf 'NEXT_PUBLIC_API_TOKEN=%s\n' "$TOKEN" > "$LOCAL_ENV"
echo "token-configured (length=${#TOKEN})"
node -v
npm -v
ls /opt/zhixue/frontend/node_modules/.bin/next >/dev/null 2>&1 && echo next-in-src-yes || echo next-in-src-no
