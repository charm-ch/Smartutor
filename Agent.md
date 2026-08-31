# Agent.md — Smartutor 开发指南

> 本文档面向在本仓库工作的 AI 编码代理（以及新加入的人类开发者）。
> 它总结了 Smartutor 从立项到 MVP 验收全过程中的架构决策、环境约束与踩坑记录。
> **改动代码前请先读完本文，尤其是第 6 节"必守规则"——每一条都对应一次真实的生产事故。**

## 1. 项目是什么

Smartutor（中文名「智学」）是一个**课程级 AI 助教**：教师上传课件/历年真题 PDF 后，学生可以：

1. **带引用的答疑**——回答必须基于课程资料，引用标注 [1][2] 并附溯源卡片；
2. **代码沙箱**——Agent 生成的代码在 bwrap 隔离环境中真实运行并返回结果；
3. **视觉输入**——学生上传报错截图，模型提取代码与错误信息后辅助排查；
4. **模拟试卷**——基于上传的历年真题做风格分析，生成风格相似的新试卷（题目+详细答案）；
5. **学情画像**——分析用户会话历史，输出知识点掌握度、强弱点与针对性建议。

比赛场景：中国科大"智能体赛道"，MVP 已在生产服务器验收。

## 2. 技术栈与架构

| 层 | 技术 | 说明 |
|---|---|---|
| 后端 | FastAPI + uvicorn | `app/main.py` 入口，路由挂载 6 组 API |
| 数据库 | PostgreSQL 16 + psycopg3 异步池 | `app/db.py`，表结构见 `docs/contracts.md` |
| 向量检索 | FAISS (IndexFlatIP) + bge-small-zh-v1.5 | 本地 embedding，**必须离线模式** |
| PDF 解析 | PyMuPDF 优先 + OCR 兜底 | 双层策略，见第 6 节规则 4 |
| OCR | USTC `unlimited-ocr` 多模态模型 | `app/services/ocr.py`，PDF→图片→逐页识别 |
| LLM | USTC API（OpenAI 兼容接口） | `app/services/llm.py` 统一适配，Key 存 `data/settings.json` |
| 沙箱 | bwrap（bubblewrap） | 无 Docker，见第 7 节安全基线 |
| 前端 | Next.js (standalone) + TailwindCSS | SSE 流式渲染，Markdown+LaTeX |
| Agent | 单主 Agent + 工具编排 | 检索/沙箱/视觉 3 个工具，不上多智能体 |

**架构决策记录**：MVP 阶段坚持"单主 Agent + 3 工具"的轻量编排，明确放弃多智能体课堂编排——3-4 周工期下工程复杂度不匹配。二期若做"多 Agent 协作课堂"再重新评估。

## 3. 目录结构

```
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口：CORS + 路由挂载
│   │   ├── core/
│   │   │   ├── config.py    # 全部环境配置集中管理（pydantic-settings）
│   │   │   └── settings_store.py  # 运行时设置（API Key 等，落 data/settings.json）
│   │   ├── api/             # 路由层：kb / conversations / execute / vision / mock_exam / user_profile
│   │   ├── schemas/         # Pydantic 模型，与 api/ 一一对应
│   │   └── services/        # 服务层：llm / rag / sandbox / vision / ocr / mock_exam / user_profile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/                 # 页面：page.tsx(答疑) / mock-exam/ / user-profile/
│   ├── components/          # ChatMessage / CitationCard / CodeBlock / RunResultPanel
│   └── lib/                 # types.ts(契约类型) / api.ts(SSE 客户端)
├── docs/contracts.md        # 接口契约 v1（冻结版）：消息 JSON、SSE 事件、错误码、表结构
├── tools/                   # 服务器初始化/测试脚本（见第 9 节）
└── Agent.md
```

**扩展模式（新增一个 API 必须四处同步）**：
`api/` 新路由文件 → `schemas/` 对应 Pydantic 模型 → `services/` 服务层 → `main.py` 挂载路由；前端同步 `lib/types.ts` 类型 + `lib/api.ts` 请求函数 + 页面。三端契约以 `docs/contracts.md` 为准。

## 4. 开发环境与部署模式

项目采用**本地开发 + 服务器部署**两份拷贝：

- **本地源码**：`D:\Codefield\Smartutor`（Windows，PowerShell）
- **服务器**：`match-server`（SSH 别名，172.20.23.76:30000 → 云主机 22，root 免密），项目在 `/opt/zhixue/`
- **进程管理**：systemd —— `zhixue-backend`（uvicorn，8000 端口）、`zhixue-frontend`（node server.js，3000 端口）

**部署链路**：

```
改后端源码 → scp 到 /opt/zhixue/backend/app/... → systemctl restart zhixue-backend → systemctl is-active 验证
改前端源码 → scp 到 /opt/zhixue/frontend/ → 在该目录 next build（standalone）→ 产物进 frontend-app/ → restart zhixue-frontend
```

注意：服务器上 `/opt/zhixue/frontend/` 是源码，`/opt/zhixue/frontend-app/` 是 standalone 构建产物（**实际运行的是它**），`frontend-app.old/` 是回滚备份。后端无构建步骤，源码即运行码。

**本地预览生产环境**：`ssh -N -L 13300:127.0.0.1:3000 match-server` 后访问 `localhost:13300`。

**服务器网络约束（重要）**：防火墙按目标 IP 白名单，只放行 USTC 系域名（api.llm.ustc.edu.cn、mirrors.ustc.edu.cn 等）。**GitHub / PyPI / Docker Hub 均不可达**：
- 装依赖走 USTC 镜像源，不走隧道；
- 确需外网时用 SSH 反向隧道 + 本地代理（`tools/start-tunnel.ps1`）。

**PowerShell 注意**：语句分隔用 `;` 不是 `&&`；含引号/花括号的复杂命令不要内联，写成脚本文件 scp 上去执行（可绕过转义地狱，也便于复跑）。

## 5. 接口契约要点

完整契约见 `docs/contracts.md`（冻结版）。高频使用的部分：

**消息对象 JSON**：`id` / `role` / `content`（内嵌 [1][2] 引用标记）/ `citations[]`（index, doc_name, chapter, page, snippet, verified）/ `run`（code, output, exit_code, time_ms）。

**SSE 事件协议**：`token`（流式逐字）、`run`（代码运行结果）、`citation`（回答结束整体下发引用）、`done` / `error`。后端用 sse-starlette（**行尾是 \r\n**，见规则 1）。

**数据库核心表**：`kb` / `documents`（status: parsing|parsed|failed|reparsing，error 落库）/ `chunks`（含 embedding）/ `conversations` / `messages`（citations、run 存 jsonb）。

## 6. 必守规则（每条都对应一次真实事故）

1. **SSE 行尾是 CRLF**。sse-starlette 用 `\r\n\r\n` 分帧，前端解析必须 `split(/\r?\n\r?\n/)` 并处理流尾残留块，否则收不到任何 token。
2. **同步库不得直接在 async 函数里调用**。sentence-transformers 的 embedding 是同步阻塞的，必须 `asyncio.to_thread()` 包裹，否则整个事件循环卡死，SSE 全部停摆。
3. **embedding 模型必须离线**。环境变量 `HF_HUB_OFFLINE=1`——模型已缓存到本地，但 HF 库默认仍会尝试联网校验，在白名单网络下会挂起很久。
4. **PDF 解析走双层策略**：先 PyMuPDF 提文本，内容为空（扫描版）自动切 OCR。**所有外部模型输出入库前必须清洗 NUL (0x00) 字节**——PostgreSQL text 拒绝 NUL，OCR 输出混入空字节会让解析任务静默 failed。清洗统一走 `rag.py` 的 `_clean_text()`（`_split_text` 入口 + PyMuPDF 逐页提取处）。
5. **给 LLM 的检索结果必须是完整 content**。早期只发 300 字 snippet 导致答题质量差；snippet 仅用于前端溯源卡片展示。
6. **后台解析任务的失败原因必须落库**（documents.error 字段）。否则只能翻 journalctl 排查，成本极高。
7. **f-string 里写 JSON 示例要转义花括号**（`{{}}`），这是 user_profile 生成出过的语法错误。
8. **RunResult 的字段是 `output`**（stdout+stderr 合并），没有独立的 `stderr` 字段，新增消费方别再引用不存在的字段。
9. **API Key 不入库不入仓**。运行时 Key 存服务器 `data/settings.json`（已被 .gitignore 覆盖），源码里只有占位符。
10. **上传文件后核对字节数**。曾经 PowerShell 构造的 multipart 把 300KB 的 PDF 传成了 13 字节——文件类操作完成后验证大小。

## 7. 沙箱安全基线（不可妥协）

bwrap 隔离，以下参数缺一不可（`app/services/sandbox.py`）：

- `--unshare-net`（无网络）、`--uid 65534`（nobody，非 root）
- 超时 10s、内存 256MB、CPU 限额
- 一次性进程，运行完即销毁
- 因服务器访问不了 Docker Hub，**不要尝试改成 Docker 方案**，除非先解决镜像获取

改动沙箱代码后必须跑 `tools/sandbox-test.sh`（7 项安全测试全过才算过）。

## 8. 测试与验收工具

| 工具 | 用途 |
|---|---|
| `tools/ci-check.sh` | 一键回归：py_compile → validators 单测 → 沙箱测试 → 检索评测（[2026-08-31] 新增） |
| `tools/retrieval-eval.sh` | 检索质量评测（20 问基准，要求 100% 命中） |
| `tools/sandbox-test.sh` | 沙箱 7 项安全测试 |
| `tools/gen-courseware.sh` | 生成 8 章 C 语言测试课件 PDF |
| `tools/server-setup.sh` | 服务器初始化（依赖、数据库、systemd） |
| `tools/start-tunnel.ps1` | SSH 反向隧道（本地代理访问外网/前端） |
| `tools/hash-manifest.py` | 本地/服务器文件 MD5 清单一致性校验 |

**验收基线**（MVP 已达成，回归时不得低于）：检索 20 问 100% 命中；SSE 全链路（token/run/citation/done + 历史持久化）；5 套真题 PDF 全解析（48 chunks，含 3 个扫描版 OCR）；模拟卷生成含风格分析+题目+LaTeX 详细答案。

## 9. Git 约定

- 主分支 `main`，commit message 用英文祈使句，正文列功能点；
- `.gitignore` 已覆盖 `node_modules/`、`.next/`、`.env*`、`data/`、`uploads/`、`__pycache__/`——新增敏感或大体积产物时同步补充；
- 远程：`github.com/charm-ch/Smartutor`（SSH over 443 端口，见 `~/.ssh/config` 的 `Host github.com` 配置）。

## 10. 规则优先级（[2026-08-31] Harness·Guides）

冲突时的裁定顺序，从高到低：

1. **本项目规则**（本文件第 6/7 节 + `docs/contracts.md` 冻结契约）
2. **当前代码实际状态**（以 git main 为准，不以记忆/文档描述为准）
3. **会话临时指令**（用户当次要求，可临时覆盖第 3 级以下约定，但不得违反第 1 级）
4. **通用惯例**（各语言社区默认风格）

## 11. 棘轮流程（Ratchet：错误只许降，不许升）

同类错误出现 **三次** 即固化为结构性约束，不再依赖记忆与自觉：

1. **触发**：出现一次真实事故（报错/返工/数据损坏）；
2. **记录**：24h 内写入本文件第 6 节，格式：`编号. **一句话规则**。（事故一句话描述）`，标注日期与来源；
3. **加固**：优先转化为代码约束（校验器/类型/CI 检查），而不是仅靠遵守；
4. **清理**：每月一次通读第 6 节，删除相互矛盾或已被代码约束取代的条款。

> 已固化的结构性约束示例：NUL 清洗（规则 4 → `rag._clean_text()`）、Sensors 校验（2026-08-31 画像空输出事故 → `validators.py`）、写操作认证（2026-08-31 审计 → `core/auth.py`）、任务检查点（→ `task_state` 表）。

## 12. Harness 六层架构速查（[2026-08-31] 加固后）

| 层 | 落点 | 要点 |
|---|---|---|
| Guides | 本文件 | 规则必须追溯到真实事故，按棘轮流程维护 |
| Sensors | `app/services/validators.py` | LLM 输出 Schema 校验，失败重试 1 次再失败报错，禁止静默回退 |
| Loop | `app/services/llm.py` + `config.py` | 重试≤2 次指数退避；32k token/60s 预算；错误带 {stage, detail, suggestion} |
| Memory | `task_state` 表 | 长任务阶段检查点，>7 天自动清理；画像增量对比 |
| Permissions | `app/core/auth.py` | 写操作 Bearer Token（`API_TOKEN` 非空启用）；上传 413/415；删除需 confirm |
| Observability | `agent_runs` 表 + `/api/runs/*` | 每次答疑落检索块/得分/token/延迟；前端轨迹面板 |
