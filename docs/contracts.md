# 「智学」MVP 接口契约 v1（冻结版）

> 本文档是**唯一数据契约来源**。任何接口变更必须先改这里，再改代码。
> 三端对齐：后端 `schemas/`、前端 `lib/types.ts`、本文档必须保持一致。

## 0. 通用约定

- 基础路径：`/api`
- 请求/响应均 JSON（文件上传除外）
- 时间字段：ISO 8601 UTC（如 `2026-08-19T08:00:00Z`）
- 错误响应统一格式：

```json
{
  "detail": {
    "code": "E_NOT_FOUND",
    "message": "知识库不存在",
    "params": {}
  }
}
```

### 错误码表

| 错误码 | 含义 | 触发场景 |
|---|---|---|
| `E_VALIDATION` | 参数校验失败 | 必填缺失/格式错误 |
| `E_NOT_FOUND` | 资源不存在 | kb/doc/conversation 不存在 |
| `E_PARSE_FAILED` | 文档解析失败 | PDF 损坏/加密 |
| `E_EMPTY_KB` | 知识库无可用块 | 检索前未上传或解析未完成 |
| `E_RETRIEVAL_FAILED` | 检索失败 | 向量库异常 |
| `E_TIMEOUT` | 超时 | 沙箱运行超时 / LLM 超时 |
| `E_LIMIT` | 超资源限制 | 沙箱超内存 |
| `E_COMPILE` | 编译失败 | 沙箱编译错误（`stderr` 附错误信息） |
| `E_LLM` | 模型调用失败 | API 网关错误/限流 |
| `E_VISION` | 视觉识别失败 | 图片无效/模型不可用 |
| `E_SANDBOX_UNAVAILABLE` | 沙箱不可用 | Docker 未启动/容器拉取失败 |
| `E_INTERNAL` | 内部错误 | 未分类异常（附 `trace_id`） |

## 1. KB 组：知识库管理（M1）

### 1.1 创建知识库

```
POST /api/kb
```

请求：

```json
{ "name": "C语言程序设计", "description": "翁恺C语言 + 谭浩强教材" }
```

响应 `200`：

```json
{ "id": "kb_01", "name": "C语言程序设计", "description": "...", "created_at": "..." }
```

### 1.2 上传文档（multipart/form-data）

```
POST /api/kb/{kb_id}/documents
```

字段：`file`（PDF，≤50MB）

响应 `202`（异步解析）：

```json
{ "doc_id": "doc_101", "status": "parsing" }
```

### 1.3 查询文档状态

```
GET /api/kb/{kb_id}/documents/{doc_id}
```

响应 `200`：

```json
{
  "doc_id": "doc_101",
  "status": "parsed",
  "filename": "C程序设计-第8章-指针.pdf",
  "chunk_count": 156,
  "error": null
}
```

`status` ∈ `parsing | parsed | failed`；`failed` 时 `error` 为错误码（如 `E_PARSE_FAILED`）。

### 1.4 查询知识库详情

```
GET /api/kb/{kb_id}
```

响应 `200`：

```json
{
  "id": "kb_01",
  "name": "C语言程序设计",
  "docs": [
    { "doc_id": "doc_101", "filename": "C程序设计-第8章-指针.pdf", "status": "parsed", "chunk_count": 156 }
  ],
  "chunk_count": 1560
}
```

### 1.5 删除知识库

```
DELETE /api/kb/{kb_id}   → 204
```

## 2. MSG 组：会话与答疑（M2，核心）

### 2.1 创建会话

```
POST /api/conversations
```

请求：

```json
{ "kb_id": "kb_01" }
```

响应 `200`：

```json
{ "conversation_id": "conv_001" }
```

### 2.2 发送消息（SSE 流式）

```
POST /api/conversations/{cid}/messages
```

请求：

```json
{
  "content": "为什么这段代码会段错误？",
  "attachments": [ { "type": "image", "url": "https://..." } ]
}
```

`attachments` 可空数组。`type=image` 时后端调用 M4 视觉识别后再进入答疑。

响应：`text/event-stream`，事件顺序约定：

| 事件 | data 格式 | 说明 |
|---|---|---|
| `token` | `{"text": "..."}` | 回答逐字流式输出（可多个） |
| `run` | `{"code": "...", "output": "...", "exit_code": 1, "time_ms": 120}` | 沙箱运行结果（0 或 1 次） |
| `citation` | `{"citations": [...]}` | 溯源列表（结束前一次性下发） |
| `done` | `{"message_id": "msg_502"}` | 消息完成 |
| `error` | `{"code": "E_TIMEOUT", "message": "..."}` | 流程中断 |

前端收到 `done` 或 `error` 后结束流。`error` 后不再有事件。

### 2.3 会话历史

```
GET /api/conversations/{cid}/messages
```

响应 `200`：

```json
{
  "messages": [
    {
      "id": "msg_501",
      "role": "user",
      "content": "为什么这段代码会段错误？",
      "attachments": [],
      "citations": [],
      "run": null,
      "created_at": "..."
    },
    {
      "id": "msg_502",
      "role": "assistant",
      "content": "段错误通常是指针越界…[1] 修复建议…[2]",
      "attachments": [],
      "citations": [
        {
          "index": 1,
          "doc_name": "C程序设计-第8章-指针.pdf",
          "chapter": "第8章 指针",
          "page": 12,
          "snippet": "当指针指向非法内存地址时访问即触发段错误……",
          "verified": true
        },
        {
          "index": 2,
          "doc_name": "C程序设计-第8章-指针.pdf",
          "chapter": "第8章 指针",
          "page": 15,
          "snippet": "……应在使用前检查指针是否为 NULL",
          "verified": true
        }
      ],
      "run": { "code": "int main(){...}", "output": "Segmentation fault", "exit_code": 139, "time_ms": 120 },
      "created_at": "..."
    }
  ]
}
```

### 2.4 消息对象与溯源规范（硬性要求）

- `content` 中的引用标记使用 `[n]`（n 为 citations 数组的 `index`），**回答中出现的引用必须存在于 citations 中**；
- `citations[].verified`：引用块存在于本次检索结果中为 `true`；Agent 声称引用但检索未命中时为 `false`（前端渲染"待核实"样式）；
- `run`：仅当本轮触发了代码沙箱时非空；
- `page`：来源 PDF 页码；`chapter`：来源章节（来自文件名或文档结构，允许空字符串）。

## 3. EXEC 组：代码沙箱（M3）

### 3.1 执行代码

```
POST /api/execute
```

请求：

```json
{
  "language": "c",
  "code": "#include <stdio.h>\nint main(){int *p=0; *p=1; return 0;}",
  "stdin": ""
}
```

`language` ∈ `c | python`。

响应 `200`：

```json
{
  "run_id": "run_001",
  "exit_code": 139,
  "stdout": "",
  "stderr": "",
  "time_ms": 120
}
```

### 3.2 沙箱约束（安全红线）

- 一次性容器，请求结束即销毁；`--network=none`；`--memory=256m`；`--cpus=0.5`
- 超时 10s → `E_TIMEOUT`；超内存 → `E_LIMIT`；编译失败 → `E_COMPILE`（`stderr` 附 gcc 输出）
- 容器内以非 root 用户执行；镜像：`gcc:13`、`python:3.11-slim`（禁止 `latest`）
- 同一时刻全局并发 ≤ 3，超出排队

## 4. VISION 组：视觉识别（M4）

### 4.1 识别截图

```
POST /api/vision/analyze
```

请求：

```json
{ "image_url": "https://..." }
```

响应 `200`：

```json
{
  "text": "（模型识别的全部文本）",
  "code": "int main(){ int a[5]; a[10]=1; }",
  "error": "Segmentation fault (core dumped)"
}
```

`code` / `error` 为从截图中结构化提取的结果，允许 `null`（无法提取时仅返回 `text`）。

## 5. SETTINGS 组：API 配置（USTC LLM 平台）

> 遵循平台文档（llm.ustc.edu.cn）建议：**API Key 保存在服务端**（`data/settings.json`），前端只读脱敏值，测试连接由后端代理发起。默认 Base URL：`https://api.llm.ustc.edu.cn/v1`（OpenAI 兼容）。

### 5.1 读取生效配置（脱敏）

```
GET /api/settings
```

响应 `200`：

```json
{
  "base_url": "https://api.llm.ustc.edu.cn/v1",
  "chat_model": "deepseek-v4-flash",
  "vision_model": "",
  "embedding_model": "bge-m3",
  "embedding_use_local": true,
  "api_key_masked": "sk-****abcd",
  "has_api_key": true
}
```

### 5.2 保存配置

```
POST /api/settings
```

请求（`api_key` 为空字符串 = 保留旧值）：

```json
{
  "base_url": "https://api.llm.ustc.edu.cn/v1",
  "api_key": "sk-...",
  "chat_model": "deepseek-v4-flash",
  "vision_model": "",
  "embedding_model": "bge-m3",
  "embedding_use_local": true
}
```

响应：同 `GET /api/settings`。配置优先级：环境变量(.env) 为默认 → settings.json 运行时覆盖。

### 5.3 测试连接（不保存）

```
POST /api/settings/test
```

请求：

```json
{ "base_url": "https://api.llm.ustc.edu.cn/v1", "api_key": "sk-..." }
```

响应 `200`：

```json
{ "ok": true, "models": ["deepseek-v4-flash", "..."], "message": "连接成功，共 N 个模型" }
```

后端代理请求 `{base_url}/models` 拉取模型列表；401/403/404/429 映射为友好错误信息。

## 6. 数据库表结构（PostgreSQL）

```sql
CREATE TABLE kb (
  id          TEXT PRIMARY KEY,          -- kb_01
  name        TEXT NOT NULL,
  description TEXT DEFAULT '',
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE documents (
  id          TEXT PRIMARY KEY,          -- doc_101
  kb_id       TEXT REFERENCES kb(id),
  filename    TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'parsing',  -- parsing|parsed|failed
  chunk_count INT DEFAULT 0,
  error       TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chunks (                    -- 向量可存 Qdrant，元数据落此表
  id          TEXT PRIMARY KEY,
  doc_id      TEXT REFERENCES documents(id),
  seq         INT NOT NULL,
  content     TEXT NOT NULL,
  chapter     TEXT DEFAULT '',
  page        INT DEFAULT 0
);

CREATE TABLE conversations (
  id          TEXT PRIMARY KEY,          -- conv_001
  kb_id       TEXT REFERENCES kb(id),
  title       TEXT DEFAULT '新对话',
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE messages (
  id          TEXT PRIMARY KEY,          -- msg_501
  conversation_id TEXT REFERENCES conversations(id),
  role        TEXT NOT NULL,             -- user|assistant
  content     TEXT NOT NULL,
  attachments JSONB DEFAULT '[]',
  citations   JSONB DEFAULT '[]',
  run         JSONB,
  created_at  TIMESTAMPTZ DEFAULT now()
);
```

## 7. 检索质量验收标准（M1 完成判定）

- 上传 3 份课程材料后，用 20 个真实知识点问题抽检，**检索命中率 ≥ 80%**（命中 = 检索结果 Top-5 内含可支撑答案的块）；
- 检索接口（内部）返回块必须含 `doc_name / chapter / page / snippet` 四元组，缺一视为脏数据。

## 8. 变更记录

| 日期 | 版本 | 变更人 | 说明 |
|---|---|---|---|
| 2026-08-19 | v1.0 | 方案讨论 | 冻结版 |
| 2026-08-19 | v1.1 | 团队 | 新增 SETTINGS 组（USTC LLM 平台配置，Key 存服务端） |
