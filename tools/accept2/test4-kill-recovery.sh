#!/usr/bin/env bash
# Harness 破坏性验收 4：画像生成中途 SIGKILL 后端 → 重启后 task_state 检查点可查
set -u
BASE=http://127.0.0.1:8000
DIR=/tmp/harness-accept2
TOKEN=$(grep '^API_TOKEN=' /opt/zhixue/backend/.env | cut -d= -f2)
AUTH="Authorization: Bearer $TOKEN"
PY=/opt/zhixue/backend/.venv/bin/python
PSQL="sudo -u postgres psql -t -A zhixue -c"

echo "== 测试 4：画像中途 kill 后端恢复 =="
mkdir -p "$DIR"

CID=$($PSQL "SELECT conversation_id FROM messages WHERE role='user' GROUP BY conversation_id HAVING count(*)>=1 ORDER BY max(created_at) DESC LIMIT 1")
[ -z "$CID" ] && { echo "NO_CONVERSATION"; exit 1; }
echo "conv_id=$CID"

# 记录 kill 前最新检查点时间，避免误取历史任务
BEFORE=$($PSQL "SELECT coalesce(max(updated_at),'1970-01-01')::text FROM task_state WHERE kind='user_profile'")
echo "before=$BEFORE"

# 后台发起画像生成
curl -s -m 150 -X POST "$BASE/api/user-profile" -H "$AUTH" \
  -H 'Content-Type: application/json' -d "{\"conversation_id\":\"$CID\"}" \
  > "$DIR/profile-killed.json" &
CURL_PID=$!

# 轮询等待新任务的第一个检查点（fetch_history 在 LLM 调用前落库）
TASK_ID=""
for i in $(seq 1 30); do
  TASK_ID=$($PSQL "SELECT task_id FROM task_state WHERE kind='user_profile' AND status='running' AND updated_at > '$BEFORE' ORDER BY updated_at DESC LIMIT 1")
  [ -n "$TASK_ID" ] && break
  sleep 0.5
done
if [ -z "$TASK_ID" ]; then
  echo "NO_TASK_SEEN — 检查点未落库"
  kill "$CURL_PID" 2>/dev/null
  exit 1
fi
STAGE=$($PSQL "SELECT stage FROM task_state WHERE task_id='$TASK_ID'")
echo "task_id=$TASK_ID（已落检查点 stage=$STAGE，任务运行中）"

sleep 1  # 让其进入 LLM 分析阶段（analyze 未完成）
systemctl kill -s SIGKILL zhixue-backend
echo "[kill] 后端已 SIGKILL（模拟崩溃）"
kill "$CURL_PID" 2>/dev/null
sleep 1

systemctl start zhixue-backend
echo "[restart] 重启后端，等待 health..."
for i in $(seq 1 40); do
  curl -s -m 2 http://127.0.0.1:8000/health 2>/dev/null | grep -q ok && { echo "health ok"; break; }
  sleep 1
done

echo "--- 重启后查询任务进度 ---"
HTTP=$(curl -s -o "$DIR/task-after.json" -w '%{http_code}' "$BASE/api/runs/tasks/$TASK_ID")
echo "GET /api/runs/tasks/$TASK_ID -> HTTP $HTTP"
head -c 600 "$DIR/task-after.json"; echo

if [ "$HTTP" = "200" ]; then
  OK=$($PY -c "
import json
d=json.load(open('$DIR/task-after.json',encoding='utf-8'))
ok = d.get('status') in ('running','done','failed') and bool(d.get('stage'))
print('1' if ok else '0')")
  if [ "$OK" = "1" ]; then
    echo "RESULT: PASS — 崩溃后检查点持久化，重启可查已完成阶段"
    exit 0
  fi
fi
echo "RESULT: FAIL — 重启后无法查到任务进度"
exit 1
