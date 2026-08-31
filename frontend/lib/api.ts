/**
 * API 客户端：SSE 流式对话（契约 §2.2）+ 会话/知识库接口封装。
 * 所有后端调用必须经过本模块，组件内禁止直接 fetch。
 */
import type {
  AgentRunTrace,
  Citation,
  KB,
  KBDetail,
  Message,
  MockExamRequest,
  MockExamResponse,
  RunResult,
  RunStats,
  Settings,
  SettingsPayload,
  SseEvent,
  TestResult,
  UserProfileRequest,
  UserProfileResponse,
} from "./types";

/*
 * 同源部署：默认走相对路径（由 next.config.mjs 的 rewrites 代理到后端）。
 * 仅独立部署前端时才需要设置 NEXT_PUBLIC_API_BASE。
 *
 * [2026-08-31] Harness·Permissions：写操作需 Bearer Token（NEXT_PUBLIC_API_TOKEN，
 * 未配置时不携带，由后端 api_token 留空时同步放行）。
 */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? "";

function authHeaders(): Record<string, string> {
  return API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...authHeaders() },
    ...init,
  });
  if (!res.ok) {
    let detail: { code?: string; message?: string; stage?: string; detail?: string; suggestion?: string } = {};
    try {
      detail = (await res.json()).detail ?? {};
    } catch {
      /* 忽略解析失败 */
    }
    const parts = [detail.detail, detail.suggestion, detail.message, detail.code]
      .filter(Boolean) as string[];
    throw new Error(parts.join("｜") || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

/** 读取生效配置（脱敏） */
export function getSettings() {
  return request<Settings>("/api/settings");
}

/** 保存配置（api_key 为空 = 保留旧值） */
export function saveSettings(payload: SettingsPayload) {
  return request<Settings>("/api/settings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** 测试连接并获取模型列表（不保存） */
export function testConnection(baseUrl: string, apiKey: string) {
  return request<TestResult>("/api/settings/test", {
    method: "POST",
    body: JSON.stringify({ base_url: baseUrl, api_key: apiKey }),
  });
}

/** 知识库列表 */
export function listKbs() {
  return request<KB[]>("/api/kb");
}

/** 创建知识库 */
export function createKb(name: string, description = "") {
  return request<KB>("/api/kb", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

/** 知识库详情（含文档列表） */
export function getKbDetail(kbId: string) {
  return request<KBDetail>(`/api/kb/${kbId}`);
}

/** 上传 PDF（异步解析） */
export async function uploadDocument(kbId: string, file: File) {
  const res = await fetch(`${API_BASE}/api/kb/${kbId}/documents`, {
    method: "POST",
    headers: authHeaders(),
    body: (() => {
      const fd = new FormData();
      fd.append("file", file);
      return fd;
    })(),
  });
  if (!res.ok) throw new Error(`上传失败 HTTP ${res.status}`);
  return res.json();
}

/** 删除知识库（Harness·Permissions：需 confirm 确认，不可逆操作） */
export function deleteKb(kbId: string) {
  return request<void>(`/api/kb/${kbId}?confirm=${encodeURIComponent(kbId)}`, {
    method: "DELETE",
  });
}

/** 生成模拟试卷 */
export function createMockExam(payload: MockExamRequest) {
  return request<MockExamResponse>("/api/mock-exam", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** 生成用户画像 */
export function createUserProfile(payload: UserProfileRequest) {
  return request<UserProfileResponse>("/api/user-profile", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** 创建会话（绑定知识库） */
export function createConversation(kbId: string) {
  return request<{ conversation_id: string }>("/api/conversations", {
    method: "POST",
    body: JSON.stringify({ kb_id: kbId }),
  });
}

/** 会话历史（契约 §2.3） */
export async function listMessages(conversationId: string): Promise<Message[]> {
  const data = await request<{ messages: Message[] }>(
    `/api/conversations/${conversationId}/messages`
  );
  return data.messages;
}

/** [2026-08-31] Harness·Observability：查询单次答疑结构化轨迹 */
export function getRunTrace(runId: string) {
  return request<AgentRunTrace>(`/api/runs/${runId}/trace`);
}

/** 查询近 N 次答疑平均延迟与 token 消耗 */
export function getRunStats(limit = 20) {
  return request<RunStats>(`/api/runs/stats?limit=${limit}`);
}

/**
 * 发送消息并消费 SSE 事件流（契约 §2.2）。
 * 事件顺序约定：token → (run)? → citation → done | error
 * onEvent 回调在浏览器主线程之外被调用，注意用函数式 setState。
 */
export async function streamMessage(
  conversationId: string,
  content: string,
  attachments: { type: "image"; url: string }[],
  onEvent: (ev: SseEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ content, attachments }),
    signal,
  });
  if (!res.ok || !res.body) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body.detail?.message ?? message;
    } catch {
      /* 忽略 */
    }
    throw new Error(message);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE 以空行分隔事件块（兼容 \r\n 与 \n 两种行尾）
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const ev = parseSseBlock(block);
      if (ev) onEvent(ev);
    }
  }

  // 流结束后处理残留的最后一个事件块
  if (buffer.trim()) {
    const ev = parseSseBlock(buffer);
    if (ev) onEvent(ev);
  }
}

/** 解析单个 SSE 块（event: xxx\r?\ndata: {...}） */
function parseSseBlock(block: string): SseEvent | null {
  let event = "message";
  let data = "";
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    const parsed = JSON.parse(data);
    switch (event) {
      case "token":
        return { event: "token", data: { text: parsed.text } };
      case "run":
        return { event: "run", data: parsed as RunResult };
      case "citation":
        return { event: "citation", data: { citations: parsed.citations as Citation[] } };
      case "done":
        return { event: "done", data: { message_id: parsed.message_id, run_id: parsed.run_id } };
      case "error":
        return {
          event: "error",
          data: {
            code: parsed.code,
            message: parsed.message,
            progress: parsed.progress,
            suggestion: parsed.suggestion,
          },
        };
      default:
        return null;
    }
  } catch {
    return null;
  }
}
