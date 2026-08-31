"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import CitationCard from "./CitationCard";
import RunResultPanel from "./RunResultPanel";
import { getRunTrace } from "@/lib/api";
import type { AgentRunTrace, Message } from "@/lib/types";

/**
 * [2026-08-31] Harness·Observability：推理轨迹折叠面板。
 * 展示检索块列表（含得分）、token 用量、延迟，引用编号 [n] 与检索块一一对应。
 */
function TracePanel({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  const [trace, setTrace] = useState<AgentRunTrace | null>(null);
  const [err, setErr] = useState("");

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && !trace && !err) {
      getRunTrace(runId)
        .then(setTrace)
        .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
    }
  };

  if (!open) {
    return (
      <button
        onClick={toggle}
        className="mt-2 text-xs text-gray-400 hover:text-blue-500"
      >
        ▸ 查看推理轨迹
      </button>
    );
  }

  return (
    <div className="mt-2 rounded-lg border border-gray-200 bg-gray-50 p-2 text-xs">
      <button onClick={toggle} className="text-gray-400 hover:text-blue-500">
        ▾ 收起轨迹
      </button>
      {err && <p className="mt-1 text-orange-600">轨迹加载失败：{err}</p>}
      {trace && (
        <div className="mt-1 space-y-1">
          <div className="text-gray-500">
            延迟 {(trace.latency_ms / 1000).toFixed(1)}s ·
            prompt {trace.prompt_tokens} tok ·
            completion {trace.completion_tokens} tok
          </div>
          {trace.retrieved.length > 0 ? (
            <ul className="space-y-0.5">
              {trace.retrieved.map((r, i) => (
                <li key={`${r.chunk_id}-${i}`} className="text-gray-600">
                  [{i + 1}] 《{r.doc_name}》
                  {r.score != null && (
                    <span className="text-gray-400">（score {r.score.toFixed(3)}）</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-400">本轮未检索到课程资料</p>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * 自定义 Markdown 组件：增强标题、列表、代码块的显示效果
 */
const markdownComponents: Record<string, React.ComponentType<any>> = {
  // 标题：加粗 + 增大字号 + 顶部间距
  h1: ({ children }: { children: React.ReactNode }) => (
    <h1 className="text-xl font-bold mt-4 mb-2 text-gray-900">{children}</h1>
  ),
  h2: ({ children }: { children: React.ReactNode }) => (
    <h2 className="text-lg font-bold mt-3 mb-2 text-gray-900">{children}</h2>
  ),
  h3: ({ children }: { children: React.ReactNode }) => (
    <h3 className="text-base font-bold mt-2 mb-1 text-gray-900">{children}</h3>
  ),
  // 段落：增加底部间距
  p: ({ children }: { children: React.ReactNode }) => (
    <p className="mb-2 leading-relaxed">{children}</p>
  ),
  // 无序列表：自定义样式
  ul: ({ children }: { children: React.ReactNode }) => (
    <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>
  ),
  // 有序列表：自定义样式
  ol: ({ children }: { children: React.ReactNode }) => (
    <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>
  ),
  // 列表项：增加间距
  li: ({ children }: { children: React.ReactNode }) => (
    <li className="ml-2">{children}</li>
  ),
  // 代码块：深色背景 + 等宽字体
  code: ({ className, children, ...props }: { className?: string; children: React.ReactNode }) => {
    const isInline = !className;
    return isInline ? (
      <code className="bg-gray-100 text-red-600 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
        {children}
      </code>
    ) : (
      <code className={`block bg-gray-900 text-gray-100 p-3 rounded-lg overflow-x-auto text-sm font-mono ${className}`} {...props}>
        {children}
      </code>
    );
  },
  // 预格式化文本（代码块容器）
  pre: ({ children }: { children: React.ReactNode }) => (
    <pre className="my-2 rounded-lg overflow-hidden">{children}</pre>
  ),
  // 强调：加粗
  strong: ({ children }: { children: React.ReactNode }) => (
    <strong className="font-bold text-gray-900">{children}</strong>
  ),
  // 斜体
  em: ({ children }: { children: React.ReactNode }) => (
    <em className="italic">{children}</em>
  ),
  // 引用块
  blockquote: ({ children }: { children: React.ReactNode }) => (
    <blockquote className="border-l-4 border-gray-300 pl-3 py-1 my-2 text-gray-600 italic">
      {children}
    </blockquote>
  ),
};

/**
 * 单条消息渲染：用户消息（右侧）/ 助手消息（左侧，含 Markdown + 溯源 + 运行结果）。
 */
export default function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser ? "bg-primary text-white" : "bg-white border border-gray-200"
        }`}
      >
        {message.attachments.map((att, i) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={i}
            src={att.url}
            alt="附件"
            className="mb-2 max-h-48 rounded-lg border border-gray-300"
          />
        ))}
        <div className={`text-[15px] leading-relaxed ${isUser ? "" : "markdown-body"}`}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
          >
            {message.content}
          </ReactMarkdown>
        </div>
        {message.run && <RunResultPanel run={message.run} />}
        {!isUser && message.run_id && <TracePanel runId={message.run_id} />}
        {message.citations.length > 0 && (
          <div className="mt-3 border-t border-gray-100 pt-2">
            <div className="text-xs text-gray-400 mb-1">参考资料</div>
            {message.citations.map((c) => (
              <CitationCard key={c.index} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
