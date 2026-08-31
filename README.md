# 智学 · 课程级多智能体助教系统（MVP）

智能体赛道参赛项目。面向编程类课程的"答疑 + 溯源"闭环：上传课件 → 多轮问答 → 答案回源标注 → 代码沙箱运行 → 拍照提问。

## 技术栈

- 后端：Python FastAPI + LangGraph + Qdrant(或FAISS) + PostgreSQL
- 前端：Next.js + TailwindCSS（SSE 流式渲染），含 API 设置页（/settings）
- 沙箱：**bwrap（bubblewrap）进程隔离**（服务器无 Docker；见下方网络说明）
- 模型：USTC 大模型平台 API（https://api.llm.ustc.edu.cn/v1，OpenAI 兼容，Key 存服务端）

## 目录规范

```
backend/          Python 后端（FastAPI）
  app/main.py     入口：挂载路由 + CORS
  app/core/       配置（环境变量）
  app/api/        路由层（kb / conversations / execute / vision）
  app/schemas/    Pydantic 模型（与 docs/contracts.md 严格一致）
  app/services/   服务层（llm / rag / sandbox / vision）
frontend/         Next.js 前端
  app/            页面（聊天主界面）
  components/     组件（ChatMessage / CitationCard / CodeBlock / RunResultPanel）
  lib/            API 客户端与类型定义（types.ts 与契约一致）
docs/             contracts.md 接口契约（唯一数据契约来源，改接口必须先改这里）
```

## 模块分工（3人 × coding agent）

| 模块 | 归属 | 主要文件 |
|---|---|---|
| M1 知识库服务 | 成员A | `backend/app/services/rag.py`、`backend/app/api/kb.py` |
| M2 答疑 Agent | 成员B | `backend/app/api/conversations.py`、`backend/app/services/llm.py` |
| M3 代码沙箱 | 成员B | `backend/app/services/sandbox.py`、`backend/app/api/execute.py` |
| M4 视觉识别 | 成员B | `backend/app/services/vision.py`、`backend/app/api/vision.py` |
| M5 前端与会话 | 成员C | `frontend/**`、会话存储 |

> 服务层 stub 中标注了 `TODO(@Mx)` 的归属，各自认领后并行实现，联调只对齐接口契约。

## 本地运行

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # 填入学校 API 配置
uvicorn app.main:app --reload --port 8000
# API 文档: http://localhost:8000/docs
```

### 前端

```bash
cd frontend
npm install
copy .env.example .env.local    # 填入 NEXT_PUBLIC_API_BASE
npm run dev                     # http://localhost:3000
```

## 开发规范

1. **契约先行**：任何接口变更必须同步修改 `docs/contracts.md`，三端（后端/前端/文档）保持一致
2. **溯源必带出处**：Agent 回答引用必须出现在本次检索结果中，否则标注"待核实"（`verified: false`）
3. **沙箱安全红线**：一次性容器、无网络、内存/CPU 限制、超时 10s、非 root 用户，不可妥协
4. **验收里程碑**：
   - 第1周末：检索链路通（20问抽检命中率 ≥80%，流式回答）
   - 第2周末：演示主线通（贴代码→沙箱运行→修复建议+溯源卡片）
   - 第3周末：全功能通（拍照提问 + 会话持久化 + 移动端可用）
   - 第4周：打磨（录屏 + PPT + 演练 ×2 + 依赖冻结）

## 服务器网络状况（已实测 2026-08-19）

- 白名单防火墙：仅科大域可达（www.ustc.edu.cn / mirrors.ustc.edu.cn / api.llm.ustc.edu.cn 等），百度/GitHub/DockerHub 均不通
- **USTC 网络通（wlt）方案不可行**：服务器不在校园网链路（wlt.ustc.edu.cn 连接超时，网络侧按 IP 精确白名单拦截），无需再尝试
- **外网方案：SSH 反向隧道 + 本地代理（已打通 ✅）**
  - 一键启动：`powershell -ExecutionPolicy Bypass -File tools\start-tunnel.ps1`
  - 原理：本地跑 HTTP CONNECT 代理（tools/proxy.py）→ `ssh -R 1080:127.0.0.1:1080 match-server` 反向隧道 → 服务器流量经本机出网
  - 服务器已装 `/etc/profile.d/proxy.sh`：隧道在线时自动 export 代理，科大域（no_proxy）直连不走隧道；隧道离线自动跳过
  - **限制**：依赖本地机器在线；Docker Hub 本地也不可达（校园网限制），需镜像源或本地构建后传输
- 依赖获取优先走 **USTC 镜像站**（直连更快，无需隧道）：
  - pip：`-i https://pypi.mirrors.ustc.edu.cn/simple`
  - apt：编辑 `/etc/apt/sources.list` 指向 `mirrors.ustc.edu.cn/ubuntu/`
  - npm：`--registry https://mirrors.ustc.edu.cn/npm/`
  - GitHub release 二进制：`https://mirrors.ustc.edu.cn/github-release/`
- **服务器无 Docker** → 沙箱改用 bwrap（`apt install bubblewrap`）：`--unshare-net --unshare-pid --die-with-parent` + `timeout` + `ulimit` + 非 root 用户（详见 sandbox.py）
- LLM API 服务器可直接访问（api.llm.ustc.edu.cn 200），Key 配置走设置页（存服务端 data/settings.json）

## 比赛服务器

- SSH：`ssh match-server`（172.20.23.76:30000，Ubuntu 24.04，已配免密）
- 硬件：8核 / 15G 内存 / 293G 磁盘

### 服务器部署架构（已完成，2026-08-19 验收通过）

```
http://<服务器>:3000  →  zhixue-frontend (Next.js standalone, node server.js)
                        │ 同源代理 /api/* (rewrites)
                        ▼
http://<服务器>:8000  →  zhixue-backend (FastAPI + uvicorn)
                        ├─ PostgreSQL 16 (zhixue 库，5 张契约表)
                        ├─ FAISS 向量库 (per-KB 索引) + bge-small-zh-v1.5 本地 embedding
                        ├─ bwrap 沙箱（gcc 13 / python3.12，无网络/降权/超时）
                        └─ USTC LLM API (api.llm.ustc.edu.cn，Key 存服务端 data/settings.json)
```

### 运维命令速查

```bash
systemctl status zhixue-backend zhixue-frontend   # 服务状态
systemctl restart zhixue-backend                  # 重启后端
journalctl -u zhixue-backend -f                   # 后端日志
sudo -u postgres psql -d zhixue                    # 数据库
ls /opt/zhixue/data/uploads/                       # 上传的 PDF
```

### 部署目录

- 后端：`/opt/zhixue/backend`（venv + 代码 + .env）
- 前端：`/opt/zhixue/frontend-app`（standalone 产物，node server.js）
- 数据：`/opt/zhixue/data/`（uploads/ + faiss/ + settings.json）
- 沙箱/DB 依赖：bwrap / gcc / PostgreSQL 16（apt USTC 镜像安装）
- embedding 模型已缓存（HF_HUB_OFFLINE=1 离线模式，避免联网校验卡顿）

### 代码更新部署流程

- 后端：`tar + scp` 上传 backend/ → 解压到 `/opt/zhixue/backend` → `systemctl restart zhixue-backend`
- 前端：本地 `npm run build` → 打包 `.next/standalone`（含 static）→ 上传解压到 `/opt/zhixue/frontend-app` → `systemctl restart zhixue-frontend`

### 已验收项（2026-08-19，含浏览器端验证）

- ✅ PDF 上传→解析→向量化→检索（4 页测试课件 9 秒完成）
- ✅ bwrap 沙箱 7 项安全测试全过（正常/段错误/编译错误/无网络/Python/超时/降权）
- ✅ SSE 会话链路（会话创建/消息接口/历史持久化刷新恢复）
- ✅ 前端同源代理部署（首页/KB 接口 200）
- ✅ 浏览器端：首页 KB 下拉加载、知识库页（已解析徽章+块数）、设置页（USTC 预填项）、沙箱运行面板渲染（✗退出码139+Segmentation fault）、错误优雅降级（⚠️提示）
- ✅ 修复：前端 SSE 解析兼容 CRLF 行尾 + 流尾残留块；后端 RunResult.stderr 引用错误；代码特征检测按标记截取
- ✅ 检索质量抽检：20 问 Top-5 命中率 **20/20 = 100%**（验收标准 ≥80%，工具 tools/retrieval-eval.sh）
- ✅ 检索返回完整 content（LLM 上下文用全文，snippet 仅用于卡片展示）
- ⏳ LLM 流式回答：待在「⚙️ API 设置页」填入学校 API Key 后即可启用（SSE 管道已由 run/error 事件验证）

### 本地访问服务器前端

服务器 3000 端口未对外映射，本地验证需建 SSH 隧道：
`ssh -N -L 13300:127.0.0.1:3000 match-server` → http://localhost:13300

