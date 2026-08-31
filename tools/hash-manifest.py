"""生成指定范围文件的 MD5 清单，用于本地/服务器代码一致性核对。"""
import hashlib
import os
import sys

base = sys.argv[1]
scope = [
    "backend/app",
    "backend/requirements.txt",
    "backend/.env.example",
    "frontend/app",
    "frontend/components",
    "frontend/lib",
    "frontend/next.config.mjs",
    "frontend/package.json",
    "frontend/postcss.config.mjs",
    "frontend/tailwind.config.ts",
    "frontend/tsconfig.json",
    "docs",
    "tools",
    "README.md",
    "Agent.md",
]
SKIP_DIRS = {"__pycache__", "node_modules", ".next"}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


lines = []
for item in scope:
    p = os.path.join(base, item)
    if os.path.isfile(p):
        lines.append(f"{md5(p)}  {item}")
    elif os.path.isdir(p):
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in sorted(files):
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, base).replace("\\", "/")
                lines.append(f"{md5(fp)}  {rel}")

print("\n".join(sorted(lines)))
