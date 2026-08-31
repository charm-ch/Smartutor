#!/usr/bin/env bash
# 补充验收：51MB 上传 → 413（用真实 KB）
set -u
TOKEN=$(grep '^API_TOKEN=' /opt/zhixue/backend/.env | cut -d= -f2)
KB=$(curl -s http://127.0.0.1:8000/api/kb | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
dd if=/dev/zero of=/tmp/big.pdf bs=1M count=51 2>/dev/null
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:8000/api/kb/$KB/documents" \
  -H "Authorization: Bearer $TOKEN" -F 'file=@/tmp/big.pdf;type=application/pdf')
rm -f /tmp/big.pdf
echo "51MB upload -> $code (expect 413)"
[ "$code" = "413" ] && echo PASS || echo FAIL
