#!/usr/bin/env bash
# Harness 破坏性验收 2：LLM 端口断 3 秒自动恢复
# 用 iptables REJECT 阻断服务器出站到 LLM API（443）3 秒，
# 验证 llm.py 有界重试（指数退避 1s/2s）使请求自动恢复、用户侧无感。
set -u
BASE=http://127.0.0.1:8000
DIR=/tmp/harness-accept2
TOKEN=$(grep '^API_TOKEN=' /opt/zhixue/backend/.env | cut -d= -f2)
AUTH="Authorization: Bearer $TOKEN"
PY=/opt/zhixue/backend/.venv/bin/python
HOST=api.llm.ustc.edu.cn

echo "== 测试 2：iptables 断 LLM 端口 3s 重试恢复 =="
mkdir -p "$DIR"
IP=$(getent hosts "$HOST" | awk '{print $1; exit}')
[ -z "$IP" ] && { echo "DNS_FAIL"; exit 1; }
echo "LLM API: $HOST -> $IP"

RULE="-d $IP -p tcp --dport 443 -j REJECT --reject-with tcp-reset"
cleanup() {
  if iptables -C OUTPUT $RULE 2>/dev/null; then
    iptables -D OUTPUT $RULE && echo "[cleanup] 规则已移除"
  else
    echo "[cleanup] 规则不在（OK）"
  fi
}
trap cleanup EXIT

mk_conv() {
  curl -s -X POST "$BASE/api/conversations" -H "$AUTH" -H 'Content-Type: application/json' \
    -d '{}' | $PY -c 'import sys,json;print(json.load(sys.stdin)["conversation_id"])'
}
ask() {  # $1=conv_id $2=question $3=outfile
  curl -sN -m 90 -X POST "$BASE/api/conversations/$1/messages" -H "$AUTH" \
    -H 'Content-Type: application/json' -d "{\"content\":\"$2\"}" > "$3"
}
check_done() {  # $1=outfile $2=标签
  if grep -q '^event: done' "$1" && ! grep -q '^event: error' "$1"; then
    CHARS=$($PY -c "
import json
t=[]
ev=''
for line in open('$1',encoding='utf-8',errors='replace'):
    line=line.strip()
    if line.startswith('event:'): ev=line.split(':',1)[1].strip()
    elif line.startswith('data:') and ev=='token':
        try: t.append(json.loads(line[5:])['text'])
        except Exception: pass
print(len(''.join(t)))")
    echo "[$2] done 事件正常，回答 $CHARS 字"
    return 0
  fi
  echo "[$2] FAIL：无 done 事件或含 error"; return 1
}

CID=$(mk_conv)

# 基线：不阻断
T0=$(date +%s%3N)
ask "$CID" "用一句话说明什么是数列极限" "$DIR/sse-base.txt"
T1=$(date +%s%3N)
echo "基线延迟: $((T1-T0)) ms"
check_done "$DIR/sse-base.txt" "基线" || { echo "RESULT: FAIL（基线即失败）"; exit 1; }

# 阻断 3 秒后发起请求
iptables -A OUTPUT $RULE && echo "[block] 已阻断出站 443 -> $IP（3 秒）"
nohup bash -c "sleep 3; iptables -D OUTPUT $RULE" >/dev/null 2>&1 &
sleep 0.3
T0=$(date +%s%3N)
ask "$CID" "用一句话说明什么是函数连续" "$DIR/sse-block.txt"
T1=$(date +%s%3N)
echo "阻断期请求延迟: $((T1-T0)) ms（应比基线多约 3s，即重试恢复耗时）"
sleep 1  # 等 nohup 移除规则
cleanup
trap - EXIT

if check_done "$DIR/sse-block.txt" "阻断恢复"; then
  echo "RESULT: PASS — 端口断 3s 后请求自动恢复，用户侧拿到完整回答"
  exit 0
fi
echo "RESULT: FAIL — 重试未能恢复"
exit 1
