/**
 * 前端类型定义 — 与 docs/contracts.md 严格一致（v1 冻结版）
 * 后端改契约必须先改 docs/contracts.md，再同步本文件。
 */

/** 溯源条目：回答中 [n] 标记与 citations 一一对应（契约 §2.4） */
export interface Citation {
  index: number;
  doc_name: string;
  chapter: string;
  page: number;
  snippet: string;
  verified: boolean;
}

/** 沙箱运行结果（仅本轮触发沙箱时非空） */
export interface RunResult {
  code: string;
  output: string;
  exit_code: number | null;
  time_ms: number;
}

export interface Attachment {
  type: "image";
  url: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachments: Attachment[];
  citations: Citation[];
  run: RunResult | null;
  createdAt: string;
  /** [2026-08-31] Harness·Observability：done 事件带回的轨迹 ID */
  run_id?: string;
}

/** SSE 事件（契约 §2.2） */
export type SseEvent =
  | { event: "token"; data: { text: string } }
  | { event: "run"; data: RunResult }
  | { event: "citation"; data: { citations: Citation[] } }
  | { event: "done"; data: { message_id: string; run_id?: string } }
  | { event: "error"; data: { code: string; message: string; progress?: string; suggestion?: string } };

/** 错误响应（契约 §0） */
export interface ApiError {
  code: string;
  message: string;
}

/** 运行时 API 配置（USTC LLM 平台，Key 保存在服务端） */
export interface Settings {
  base_url: string;
  chat_model: string;
  vision_model: string;
  embedding_model: string;
  embedding_use_local: boolean;
  api_key_masked: string;
  has_api_key: boolean;
}

export interface SettingsPayload {
  base_url: string;
  api_key: string; // 空 = 保留旧值
  chat_model: string;
  vision_model: string;
  embedding_model: string;
  embedding_use_local: boolean;
}

export interface TestResult {
  ok: boolean;
  models: string[];
  message: string;
}

/** 知识库 */
export interface KB {
  id: string;
  name: string;
  description: string;
  created_at?: string;
}

export interface KBDoc {
  doc_id: string;
  filename: string;
  status: "parsing" | "parsed" | "failed";
  chunk_count: number;
  error?: string | null;
}

export interface KBDetail extends KB {
  docs: KBDoc[];
  chunk_count: number;
}

/** 模拟试卷 */
export interface MockExamRequest {
  kb_id: string;
  num_questions: number;
  difficulty: "easy" | "medium" | "hard";
  include_answers: boolean;
}

export interface MockExamResponse {
  exam: string;
  answers: string;
  analysis: string;
  task_id?: string;
}

/** [2026-08-31] Harness·Observability：单次答疑结构化轨迹 */
export interface AgentRunTrace {
  run_id: string;
  conversation_id: string;
  question: string;
  retrieved: { chunk_id: string; doc_name: string; score: number | null }[];
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  cited_ids: string[];
  error: string | null;
  created_at: string;
}

export interface RunStats {
  total: number;
  avg_latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  error_count: number;
}

/** 用户画像 */
export interface KnowledgePoint {
  name: string;
  mastery: number;
  frequency: number;
}

export interface UserProfileStatistics {
  total_questions: number;
  topics_covered: number;
  learning_style: string;
}

export interface UserProfileRequest {
  conversation_id: string;
}

export interface UserProfileResponse {
  knowledge_points: KnowledgePoint[];
  weak_points: string[];
  strong_points: string[];
  suggestions: string[];
  statistics: UserProfileStatistics;
  task_id?: string;
  parse_status?: "ok" | "retried_ok" | "failed";
  comparison?: MasteryComparison[];
}

/** [2026-08-31] Harness·Memory：增量画像对比 */
export interface MasteryComparison {
  name: string;
  previous_mastery: number;
  current_mastery: number;
}
