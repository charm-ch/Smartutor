#!/usr/bin/env bash
# Harness 验收脚本（阶段 2/3/5 验收标准的 API 部分）
set -uo pipefail
cd /opt/zhixue
TOKEN=$(grep '^API_TOKEN=' backend/.env | cut -d= -f2)
BASE=http://127.0.0.1:8000/api
PASS=0; FAIL=0
chk() { # chk <name> <expected> <actual>
  if [ "$2" = "$3" ]; then PASS=$((PASS+1)); echo "PASS: $1 ($3)"; else FAIL=$((FAIL+1)); echo "FAIL: $1 (expect $2, got $3)"; fi
}

# 1) Permissions：无 token 写操作 → 401
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST $BASE/kb -H 'Content-Type: application/json' -d '{"name":"__acc_test"}')
chk "POST without token -> 401" 401 "$code"

# 2) 带 token 写操作 → 200
code=$(curl -s -o /tmp/acc_kb.json -w '%{http_code}' -X POST $BASE/kb -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"name":"__acc_test","description":"acceptance"}')
chk "POST with token -> 200" 200 "$code"
KB_ID=$(python3 -c "import json;print(json.load(open('/tmp/acc_kb.json'))['id'])" 2>/dev/null || echo "")

# 3) 读操作无 token → 200
code=$(curl -s -o /dev/null -w '%{http_code}' $BASE/kb)
chk "GET without token -> 200" 200 "$code"

# 4) 上传 .txt → 415
echo "fake" > /tmp/acc.txt
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST $BASE/kb/$KB_ID/documents -H "Authorization: Bearer $TOKEN" -F "file=@/tmp/acc.txt;type=text/plain")
chk "upload txt -> 415" 415 "$code"

# 5) 删除不带 confirm → 400
code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE $BASE/kb/$KB_ID -H "Authorization: Bearer $TOKEN")
chk "DELETE without confirm -> 400" 400 "$code"

# 6) 删除带 confirm → 204
code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "$BASE/kb/$KB_ID?confirm=$KB_ID" -H "Authorization: Bearer $TOKEN")
chk "DELETE with confirm -> 204" 204 "$code"

# 7) runs/stats 可访问（读）
code=$(curl -s -o /tmp/acc_stats.json -w '%{http_code}' "$BASE/runs/stats?limit=5")
chk "GET /runs/stats -> 200" 200 "$code"
cat /tmp/acc_stats.json; echo

# 8) tasks 查询不存在任务 → 404（路由存在性验证）
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/runs/tasks/task_nonexistent")
chk "GET /runs/tasks/<none> -> 404" 404 "$code"

# 9) 答疑 SSE：拿 run_id → trace 还原
CONV=$(curl -s -X POST $BASE/conversations -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"kb_id":""}' | python3 -c "import sys,json;print(json.load(sys.stdin)['conversation_id'])")
SSE=$(curl -s -N -m 90 -X POST $BASE/conversations/$CONV/messages -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"content":"什么是指针？","attachments":[]}')
RUN_ID=$(echo "$SSE" | grep '^data:' | grep run_id | python3 -c "import sys,json; line=[l for l in sys.stdin if 'run_id' in l][0]; print(json.loads(line[5:])['run_id'])" 2>/dev/null || echo "")
if [ -n "$RUN_ID" ]; then
  PASS=$((PASS+1)); echo "PASS: SSE done carried run_id ($RUN_ID)"
  curl -s "$BASE/runs/$RUN_ID/trace" > /tmp/acc_trace.json
  python3 -c "
import json
t = json.load(open('/tmp/acc_trace.json'))
assert t['run_id'] == '$RUN_ID', 'run_id mismatch'
assert 'latency_ms' in t and 'prompt_tokens' in t and 'retrieved' in t
print('PASS: trace fields complete (retrieved=%d, latency=%dms, ptok=%s)' % (len(t['retrieved']), t['latency_ms'], t['prompt_tokens']))
" && PASS=$((PASS+1)) || { FAIL=$((FAIL+1)); echo "FAIL: trace validation"; }
else
  FAIL=$((FAIL+1)); echo "FAIL: SSE done did not carry run_id"
  echo "$SSE" | tail -5
fi

echo ""
echo "=== 验收结果：$PASS 通过, $FAIL 失败 ==="
exit $FAIL
