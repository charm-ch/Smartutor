"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import ChatMessage from "@/components/ChatMessage";
import { createConversation, listKbs, listMessages, streamMessage } from "@/lib/api";
import type { Citation, KB, Message, RunResult } from "@/lib/types";

const CONV_KEY = "zhixue_conversation_id";

export default function Home() {
  const [kbs, setKbs] = useState<KB[]>([]);
  const [kbId, setKbId] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  };

  // 初始化：KB 列表 + 恢复会话
  useEffect(() => {
    listKbs()
      .then((list) => {
        setKbs(list);
        if (list.length > 0) setKbId(list[0].id);
      })
      .catch((e) => setNotice(`后端未连接：${e.message}（请先启动后端或在设置页配置）`));

    const savedConv = localStorage.getItem(CONV_KEY) || "";
    if (savedConv) {
      setConversationId(savedConv);
      listMessages(savedConv)
        .then((msgs) => msgs.length > 0 && setMessages(msgs))
        .catch(() => localStorage.removeItem(CONV_KEY));
    }
  }, []);

  const ensureConversation = async (): Promise<string> => {
    if (conversationId) return conversationId;
    const targetKb = kbId || kbs[0]?.id || "";
    const { conversation_id } = await createConversation(targetKb);
    setConversationId(conversation_id);
    localStorage.setItem(CONV_KEY, conversation_id);
    return conversation_id;
  };

  const newConversation = () => {
    localStorage.removeItem(CONV_KEY);
    setConversationId("");
    setMessages([]);
  };

  const send = async () => {
    const content = input.trim();
    if (!content || loading) return;
    setInput("");
    setLoading(true);
    setNotice("");

    const userMsg: Message = {
      id: `local_${Date.now()}`,
      role: "user",
      content,
      attachments: [],
      citations: [],
      run: null,
      createdAt: new Date().toISOString(),
    };
    const assistantMsg: Message = { ...userMsg, id: `assistant_${Date.now()}`, role: "assistant", content: "" };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    scrollToBottom();

    try {
      const cid = await ensureConversation();
      await streamMessage(cid, content, [], (ev) => {
        switch (ev.event) {
          case "token":
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, content: last.content + ev.data.text };
              return next;
            });
            scrollToBottom();
            break;
          case "run":
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, run: ev.data as RunResult };
              return next;
            });
            break;
          case "citation":
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, citations: ev.data.citations as Citation[] };
              return next;
            });
            break;
          case "error":
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              const suffix = ev.data.suggestion ? `\n💡 ${ev.data.suggestion}` : "";
              next[next.length - 1] = {
                ...last,
                content: last.content || `⚠️ ${ev.data.message}（${ev.data.code}）${suffix}`,
              };
              return next;
            });
            break;
          case "done":
            // [2026-08-31] Harness·Observability：记录 run_id，供轨迹面板查询
            if (ev.data.run_id) {
              const rid = ev.data.run_id;
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                next[next.length - 1] = { ...last, run_id: rid };
                return next;
              });
            }
            break;
          default:
            break;
        }
      });
    } catch (e) {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        next[next.length - 1] = {
          ...last,
          content: `⚠️ 请求失败：${e instanceof Error ? e.message : String(e)}`,
        };
        return next;
      });
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  };

  return (
    <main className="flex h-full flex-col max-w-3xl mx-auto">
      <header className="flex items-center justify-between px-4 py-3 border-b bg-white">
        <div className="flex items-center gap-2 min-w-0">
          <h1 className="font-semibold text-lg shrink-0">智学 · 课程级智能助教</h1>
          <select
            value={kbId}
            onChange={(e) => setKbId(e.target.value)}
            className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-600 max-w-40"
          >
            {kbs.length === 0 && <option value="">（无知识库）</option>}
            {kbs.map((kb) => (
              <option key={kb.id} value={kb.id}>{kb.name}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs px-2 py-1 rounded-full bg-green-50 text-green-600 border border-green-200">MVP</span>
          <Link href="/kb" className="text-xs px-2.5 py-1.5 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-50">
             知识库
          </Link>
          <Link href="/mock-exam" className="text-xs px-2.5 py-1.5 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-50">
            📝 模拟试卷
          </Link>
          <Link href="/user-profile" className="text-xs px-2.5 py-1.5 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-50">
            📊 学习画像
          </Link>
          <Link href="/settings" className="text-xs px-2.5 py-1.5 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-50">
            ⚙️ API
          </Link>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {notice && (
          <div className="mb-3 rounded-lg bg-orange-50 border border-orange-200 text-orange-700 text-sm p-3">{notice}</div>
        )}
        {messages.length === 0 && !notice && (
          <div className="text-center text-gray-400 mt-24">
            <p className="text-xl mb-2">📚 上传课件，随时提问</p>
            <p className="text-sm">
              试试：「为什么这段代码会段错误？」并粘贴代码
              <br />
              或直接提问：「指针和数组有什么区别？」
            </p>
          </div>
        )}
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      <footer className="border-t bg-white p-3">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && send()}
            placeholder="输入问题，或粘贴代码…"
            disabled={loading}
            className="flex-1 rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="rounded-xl bg-primary px-5 py-2.5 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-40"
          >
            {loading ? "思考中…" : "发送"}
          </button>
        </div>
        <div className="mt-1.5 flex items-center justify-between">
          <p className="text-[11px] text-gray-400">
            答案引用自课程资料，标注 [n] 可查看出处 · 代码在隔离沙箱中运行
          </p>
          {conversationId && (
            <button onClick={newConversation} className="text-[11px] text-blue-500 hover:text-blue-700">
              ＋ 新对话
            </button>
          )}
        </div>
      </footer>
    </main>
  );
}
