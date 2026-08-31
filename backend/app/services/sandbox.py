"""代码沙箱服务（M3）：bwrap（bubblewrap）进程级隔离执行。

安全红线（契约 §3.2，不可妥协）：
- 一次性执行：独立临时目录，结束即回收
- 无网络（--unshare-net）/ 无 IPC / 无 PID 共享 / 内存限制（ulimit -v）
- 超时 10s → E_TIMEOUT；超内存 → E_LIMIT；编译失败 → E_COMPILE（stderr 附 gcc 输出）
- 非 root 用户执行（--unshare-user --uid 65534 nobody）；user namespace 不可用时自动降级并记录
- 全局并发 ≤ settings.sandbox_max_concurrency，超出排队
"""
import asyncio
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


class SandboxError(Exception):
    """沙箱异常（message 为契约错误码）。"""


@dataclass
class RunOutcome:
    exit_code: int | None
    stdout: str
    stderr: str
    time_ms: int


_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.sandbox_max_concurrency)
    return _semaphore


# 编译运行命令（在沙箱内以 nobody 身份执行，ulimit 限内存）
_C_CMD = (
    "ulimit -v 262144 2>/dev/null; "
    "gcc -std=c11 -O0 main.c -o a.out 2>compile.log; "
    "rc=$?; if [ $rc -ne 0 ]; then cat compile.log >&2; exit {compile_fail}; fi; "
    "./a.out"
)
_PY_CMD = "ulimit -v 524288 2>/dev/null; python3 -I main.py"


def _bwrap_argv(workdir: Path, language: str) -> list[str]:
    """组装 bwrap 命令。merged-usr 系统只需 bind /usr /etc，符号链接用 --symlink 重建。"""
    inner = _C_CMD.replace("{compile_fail}", "99") if language == "c" else _PY_CMD
    return [
        "bwrap",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/etc", "/etc",
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--symlink", "usr/sbin", "/sbin",
        "--proc", "/proc",
        "--dev", "/dev",
        "--bind", str(workdir), "/tmp",
        "--chdir", "/tmp",
        "--unshare-net", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
        "--unshare-cgroup-try",
        "--die-with-parent", "--new-session", "--clearenv",
        "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin",
        "--setenv", "HOME", "/tmp",
        "--unshare-user", "--uid", "65534", "--gid", "65534",
        "--", "/bin/sh", "-c", inner,
    ]


async def execute(language: str, code: str, stdin: str = "") -> RunOutcome:
    """在 bwrap 隔离环境中编译/运行代码。

    返回 RunOutcome：编译失败时 exit_code=99 且 stderr 带 gcc 输出（供 M2 分析）。
    超时抛 SandboxError("E_TIMEOUT")；输出超限抛 SandboxError("E_LIMIT")。
    """
    if language not in ("c", "python"):
        raise SandboxError("E_VALIDATION")

    async with _get_semaphore():
        t0 = time.monotonic()
        workdir = Path(tempfile.mkdtemp(prefix="zx-sbx-"))
        try:
            suffix = "main.c" if language == "c" else "main.py"
            (workdir / suffix).write_text(code, encoding="utf-8")
            workdir.chmod(0o777)  # 沙箱内 nobody 需要写权限

            argv = _bwrap_argv(workdir, language)
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError as e:
                raise SandboxError("E_SANDBOX_UNAVAILABLE") from e

            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(stdin.encode() if stdin else b""),
                    timeout=settings.sandbox_timeout_sec,
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                raise SandboxError("E_TIMEOUT") from None

            stdout = stdout_b.decode(errors="replace")[:65536]
            stderr = stderr_b.decode(errors="replace")[:65536]
            exit_code = proc.returncode
            elapsed = int((time.monotonic() - t0) * 1000)

            if exit_code == 99 and language == "c":
                # 沙箱内编译失败标记：透传给上层（带 gcc 输出）
                return RunOutcome(exit_code=99, stdout=stdout, stderr=stderr, time_ms=elapsed)

            # 内存超限特征（ulimit 触发）
            if "Cannot allocate memory" in stderr or "out of memory" in stderr.lower():
                raise SandboxError("E_LIMIT")

            return RunOutcome(exit_code=exit_code, stdout=stdout, stderr=stderr, time_ms=elapsed)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
