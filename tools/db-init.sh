#!/bin/bash
# PostgreSQL 初始化：zhixue 库 + 契约表结构（幂等）
set -e

# 启动 PostgreSQL（云主机默认未启动）
systemctl enable --now postgresql 2>/dev/null || pg_ctlcluster 16 main start 2>/dev/null || true
sleep 1
systemctl is-active postgresql || true

# 创建数据库（幂等）
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='zhixue'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE zhixue"

# 建表（幂等）
sudo -u postgres psql -d zhixue <<'SQL'
CREATE TABLE IF NOT EXISTS kb (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  description TEXT DEFAULT '',
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
  id          TEXT PRIMARY KEY,
  kb_id       TEXT REFERENCES kb(id) ON DELETE CASCADE,
  filename    TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'parsing',
  chunk_count INT DEFAULT 0,
  error       TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
  id          TEXT PRIMARY KEY,
  doc_id      TEXT REFERENCES documents(id) ON DELETE CASCADE,
  seq         INT NOT NULL,
  content     TEXT NOT NULL,
  chapter     TEXT DEFAULT '',
  page        INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS conversations (
  id          TEXT PRIMARY KEY,
  kb_id       TEXT REFERENCES kb(id) ON DELETE CASCADE,
  title       TEXT DEFAULT '新对话',
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
  id              TEXT PRIMARY KEY,
  conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL,
  content         TEXT NOT NULL,
  attachments     JSONB DEFAULT '[]',
  citations       JSONB DEFAULT '[]',
  run             JSONB,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
SQL

# 应用账号（密码 zhixue，仅本机访问）
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='zhixue'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER zhixue WITH PASSWORD 'zhixue'"
sudo -u postgres psql -d zhixue -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO zhixue;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO zhixue;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO zhixue;"

echo "=== 表结构确认 ==="
sudo -u postgres psql -d zhixue -c "\dt"
echo "=== 完成 ==="
