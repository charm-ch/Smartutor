-- Harness 新增表（幂等）：应用用户无 schema public 建表权限，由 postgres 超管预建
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    question TEXT NOT NULL,
    retrieved JSONB DEFAULT '[]',
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    cited_ids JSONB DEFAULT '[]',
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS task_state (
    task_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    ref_id TEXT,
    status TEXT NOT NULL,
    stage TEXT DEFAULT '',
    payload JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_conv ON agent_runs (conversation_id);
