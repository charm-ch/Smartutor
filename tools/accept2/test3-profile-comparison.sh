#!/usr/bin/env bash
# Harness 破坏性验收 3：二次生成画像 → 历史掌握度对比（Memory 增量 merge）
set -u
BASE=http://127.0.0.1:8000
DIR=/tmp/harness-accept2
TOKEN=$(grep '^API_TOKEN=' /opt/zhixue/backend/.env | cut -d= -f2)
AUTH="Authorization: Bearer $TOKEN"
PY=/opt/zhixue/backend/.venv/bin/python
PSQL="sudo -u postgres psql -t -A zhixue -c"

echo "== 测试 3：二次画像历史对比 =="
mkdir -p "$DIR"

CID=$($PSQL "SELECT conversation_id FROM messages WHERE role='user' GROUP BY conversation_id HAVING count(*)>=1 ORDER BY max(created_at) DESC LIMIT 1")
[ -z "$CID" ] && { echo "NO_CONVERSATION"; exit 1; }
echo "conv_id=$CID"

run_profile() {  # $1=outfile
  curl -s -m 150 -X POST "$BASE/api/user-profile" -H "$AUTH" \
    -H 'Content-Type: application/json' -d "{\"conversation_id\":\"$CID\"}" > "$1"
}

echo "--- 第一次生成（建立基线画像）---"
run_profile "$DIR/profile-1.json"
$PY -c "
import json
d=json.load(open('$DIR/profile-1.json',encoding='utf-8'))
print('task_id:',d.get('task_id'),'| parse_status:',d.get('parse_status'),'| comparison:',len(d.get('comparison',[])),'| 知识点:',len(d.get('knowledge_points',[])))
" || { echo "PROFILE1_FAIL"; cat "$DIR/profile-1.json" | head -c 400; exit 1; }

echo "--- 第二次生成（应含 comparison 历史对比）---"
run_profile "$DIR/profile-2.json"
N=$($PY -c "
import json,sys
try:
    d=json.load(open('$DIR/profile-2.json',encoding='utf-8'))
except Exception:
    print(-1); raise SystemExit
c=d.get('comparison')
if c is None: print(-2)
else:
    print(len(c))
    for x in c:
        print(f\"  {x.get('name')}: {x.get('previous_mastery')} -> {x.get('current_mastery')}\", file=sys.stderr)
" | head -1)

if [ "$N" = "-2" ]; then
  echo "RESULT: FAIL — 响应缺少 comparison 字段"
  head -c 400 "$DIR/profile-2.json"; exit 1
fi
if [ "$N" = "-1" ]; then
  echo "RESULT: FAIL — 响应非合法 JSON"
  head -c 400 "$DIR/profile-2.json"; exit 1
fi
if [ "$N" = "0" ]; then
  echo "RESULT: WARN — comparison 字段存在但为空（两次生成知识点命名未重叠），重试一次"
  run_profile "$DIR/profile-3.json"
  N=$($PY -c "
import json,sys
d=json.load(open('$DIR/profile-3.json',encoding='utf-8'))
c=d.get('comparison',[])
print(len(c))
for x in c: print(f\"  {x.get('name')}: {x.get('previous_mastery')} -> {x.get('current_mastery')}\", file=sys.stderr)
" | head -1)
fi

if [ "$N" -gt 0 ] 2>/dev/null; then
  echo "RESULT: PASS — 响应含 $N 条历史掌握度对比（旧值 vs 新值）"
  exit 0
fi
echo "RESULT: FAIL — comparison 仍为空"
exit 1
