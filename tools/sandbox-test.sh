#!/bin/bash
# bwrap 沙箱链路验证（不依赖 Python 环境，直接验证 bwrap+gcc 隔离链路）
set -e
WORK=$(mktemp -d /tmp/zx-sbx-test-XXXX)
chmod 777 "$WORK"
cd "$WORK"

run_bwrap() {
  bwrap \
    --ro-bind /usr /usr --ro-bind /etc /etc \
    --symlink usr/bin /bin --symlink usr/lib /lib \
    --symlink usr/lib64 /lib64 --symlink usr/sbin /sbin \
    --proc /proc --dev /dev \
    --bind "$WORK" /tmp --chdir /tmp \
    --unshare-net --unshare-pid --unshare-ipc --unshare-uts --unshare-cgroup-try \
    --die-with-parent --new-session --clearenv \
    --setenv PATH /usr/local/bin:/usr/bin:/bin --setenv HOME /tmp \
    --unshare-user --uid 65534 --gid 65534 \
    -- /bin/sh -c "$1"
}

echo "=== 测试1：正常 C 程序（hello + 计算）==="
cat > main.c <<'EOF'
#include <stdio.h>
int main(){ int s=0; for(int i=1;i<=100;i++) s+=i; printf("sum=%d\n", s); return 0; }
EOF
run_bwrap "ulimit -v 262144 2>/dev/null; gcc main.c -o a.out && ./a.out" && echo "PASS(exit=$?)"

echo "=== 测试2：段错误程序（exit_code=139）==="
cat > main.c <<'EOF'
int main(){ int *p = 0; *p = 1; return 0; }
EOF
run_bwrap "ulimit -v 262144 2>/dev/null; gcc main.c -o a.out && ./a.out" || echo "PASS(exit=$?，预期139)"

echo "=== 测试3：编译错误（应输出 gcc 报错）==="
cat > main.c <<'EOF'
int main(){ syntax error here }
EOF
run_bwrap "ulimit -v 262144 2>/dev/null; gcc main.c -o a.out 2>err.log; rc=\$?; cat err.log >&2; test \$rc -ne 0" || echo "PASS(exit=$?，编译失败且带报错)"

echo "=== 测试4：网络隔离验证（应失败）==="
run_bwrap "timeout 3 bash -c 'echo > /dev/tcp/1.2.3.4/80'" 2>/dev/null && echo "FAIL: 网络可达!" || echo "PASS: 无网络"

echo "=== 测试5：Python 程序 ==="
cat > main.py <<'EOF'
print("hello from sandbox")
import sys; print(sys.version.split()[0])
EOF
run_bwrap "python3 -I main.py" && echo "PASS"

echo "=== 测试6：超时（应被 timeout 终止）==="
cat > main.c <<'EOF'
int main(){ while(1); return 0; }
EOF
timeout 5 bwrap --ro-bind /usr /usr --ro-bind /etc /etc \
  --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --symlink usr/sbin /sbin \
  --proc /proc --dev /dev --bind "$WORK" /tmp --chdir /tmp \
  --unshare-net --unshare-pid --die-with-parent --new-session --clearenv \
  --setenv PATH /usr/bin:/bin --unshare-user --uid 65534 --gid 65534 \
  -- /bin/sh -c "gcc main.c -o loop.out && ./loop.out" 2>/dev/null && echo "FAIL: 未超时!" || echo "PASS: 已终止(exit=$?)"

echo "=== 测试7：root 权限验证（沙箱内应为 nobody）==="
run_bwrap "id" | grep -q "uid=65534(nobody)" && echo "PASS: nobody 身份" || echo "WARN: $(run_bwrap 'id')"

cd /; rm -rf "$WORK"
echo "=== 全部完成 ==="
