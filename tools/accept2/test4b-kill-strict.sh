#!/usr/bin/env bash
# Harness 破坏性验收 4（严格版）：直接 kill -9 主进程，验证崩溃 + 重启 + 检查点
set -u
BASE=http://127.0.0.1:8000
DIR=/tmp/harness-accept2
TOKEN=$(grep '^API_TOKEN=' /opt/zhixue/backend/.env | cut -d= -f2)
AUTH="Authorization: Bearer $TOKEN"
PY=/opt/zhixue/backend/.venv/bin/python
PSQL="sudo -u postgres psql -t -A zhixue -c"

echo "== 测试 4（严格版）：kill -9 主进程 =="
PID1=$(systemctl show -p MainPID --value zhixue-backend)
echo "backend PID before: $PID1"

BEFORE=$($PSQL "SELECT coalesce(max(updated_at),'1970-01-01')::text FROM task_state WHERE kind='user_profile'")
curl -s -m 150 -X POST "$BASE/api/user-profile" -H "$AUTH" \
  -H 'Content-Type: application/json' -d "{\"conversation_id\":\"conv_c4643fbcc9bf\"}" \
  > "$DIR/profile-killed2.json" &
CURL_PID=$!

TASK_ID=""
for i in $(seq 1 30); do
  TASK_ID=$($PSQL "SELECT task_id FROM task_state WHERE kind='user_profile' AND status='running' AND updated_at > '$BEFORE' ORDER BY updated_at DESC LIMIT 1")
  [ -n "$TASK_ID" ] && break
  sleep 0.5
done
[ -z "$TASK_ID" ] && { echo "NO_TASK_SEEN"; kill "$CURL_PID" 2>/dev/null; exit 1; }
STAGE=$($PSQL "SELECT stage FROM task_state WHERE task_id='$TASK_ID'")
echo "task_id=$TASK_ID stage=$STAGE（检查点已落库，LLM 分析进行中）"

sleep 1
kill -9 "$PID1" && echo "[kill] 已 kill -9 $PID1（模拟进程崩溃）"
kill "$CURL_PID" 2>/dev/null
sleep 2

STATE=$(systemctl is-active zhixue-backend)
echo "service state after kill: $STATE（SIGKILL 后应非 active 或自动重启中）"
PID2=$(systemctl show -p MainPID --value zhixue-backend)
if [ "$PID2" = "$PID1" ] || [ -z "$PID2" ] || [ "$PID2" = "0" ]; then
  systemctl start zhixue-backend
  echo "[restart] systemctl start 已执行"
fi
for i in $(seq 1 40); do
  curl -s -m 2 http://127.0.0.1:8000/health 2>/dev/null | grep -q ok && { echo "health ok"; break; }
  sleep 1
done
PID3=$(systemctl show -p MainPID --value zhixue-backend)
echo "backend PID after restart: $PID3（应 != $PID1，证明进程确实换新）"

echo "--- 重启后查询任务进度 ---"
HTTP=$(curl -s -o "$DIR/task-after2.json" -w '%{http_code}' "$BASE/api/runs/tasks/$TASK_ID")
echo "GET /api/runs/tasks/$TASK_ID -> HTTP $HTTP"
cat "$DIR/task-after2.json"; echo

if [ "$HTTP" = "200" ] && [ "$PID3" != "$PID1" ]; then
  $PY -c "
import json
d=json.load(open('$DIR/task-after2.json',encoding='utf-8'))
assert d.get('status') and d.get('stage'), d
print('RESULT: PASS — 进程确实被 kill 并换新（%s -> %s），检查点持久化可查，stage=%s' % ('$PID1','$PID3',d.get('stage')))
" && exit 0
fi
echo "RESULT: FAIL"
exit 1
