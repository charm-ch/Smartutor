"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { createKb, deleteKb, getKbDetail, listKbs, uploadDocument } from "@/lib/api";
import type { KB, KBDetail } from "@/lib/types";

/** 知识库管理：列表 / 创建 / 上传 PDF（状态自动轮询）/ 删除 */
export default function KbPage() {
  const [kbs, setKbs] = useState<KB[]>([]);
  const [selected, setSelected] = useState<KBDetail | null>(null);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshList = useCallback(async () => {
    try {
      const list = await listKbs();
      setKbs(list);
      return list;
    } catch (e) {
      setError(`读取知识库列表失败：${e instanceof Error ? e.message : String(e)}`);
      return [];
    }
  }, []);

  const refreshDetail = useCallback(async (kbId: string) => {
    try {
      setSelected(await getKbDetail(kbId));
    } catch (e) {
      setError(`读取详情失败：${e instanceof Error ? e.message : String(e)}`);
    }
  }, []);

  useEffect(() => {
    refreshList().then((list) => {
      if (list.length > 0) refreshDetail(list[0].id);
    });
  }, [refreshList, refreshDetail]);

  // 有文档解析中时轮询
  useEffect(() => {
    const parsing = selected?.docs.some((d) => d.status === "parsing");
    if (parsing && selected) {
      const kbId = selected.id;
      pollRef.current = setInterval(() => refreshDetail(kbId), 3000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [selected, refreshDetail]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setBusy(true);
    setError("");
    try {
      const kb = await createKb(newName.trim());
      setNewName("");
      await refreshList();
      await refreshDetail(kb.id);
    } catch (e) {
      setError(`创建失败：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const handleUpload = async (file: File) => {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await uploadDocument(selected.id, file);
      await refreshDetail(selected.id);
    } catch (e) {
      setError(`上传失败：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleDelete = async (kbId: string) => {
    if (!confirm("确定删除该知识库及其全部文档？")) return;
    try {
      await deleteKb(kbId);
      const list = await refreshList();
      setSelected(list.length > 0 ? await getKbDetail(list[0].id) : null);
    } catch (e) {
      setError(`删除失败：${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const statusBadge = (s: string) =>
    s === "parsed" ? (
      <span className="text-xs text-green-600 bg-green-50 border border-green-200 rounded px-1.5 py-0.5">已解析</span>
    ) : s === "parsing" ? (
      <span className="text-xs text-blue-600 bg-blue-50 border border-blue-200 rounded px-1.5 py-0.5">解析中…</span>
    ) : (
      <span className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-1.5 py-0.5">失败</span>
    );

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold">知识库管理</h1>
            <p className="text-xs text-gray-400 mt-0.5">
              上传课程 PDF（命名规范：书名-第N章-章节名.pdf），自动解析入库
            </p>
          </div>
          <Link href="/" className="text-sm text-blue-600 border border-blue-200 rounded-lg px-3 py-1.5 hover:bg-blue-50">
            ← 返回对话
          </Link>
        </header>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm p-3">{error}</div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* 左：知识库列表 */}
          <div className="bg-white rounded-2xl border border-gray-200 p-4">
            <div className="flex gap-2 mb-3">
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                placeholder="新知识库名称，如：C语言程序设计"
                className="flex-1 min-w-0 rounded-lg border border-gray-300 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleCreate}
                disabled={busy || !newName.trim()}
                className="rounded-lg bg-primary text-white text-sm px-3 py-1.5 disabled:opacity-40"
              >
                创建
              </button>
            </div>
            <div className="space-y-1.5">
              {kbs.length === 0 && <p className="text-sm text-gray-400 py-4 text-center">暂无知识库</p>}
              {kbs.map((kb) => (
                <div
                  key={kb.id}
                  className={`flex items-center justify-between rounded-lg border px-3 py-2 cursor-pointer text-sm ${
                    selected?.id === kb.id ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:bg-gray-50"
                  }`}
                  onClick={() => refreshDetail(kb.id)}
                >
                  <span className="truncate">{kb.name}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(kb.id); }}
                    className="text-gray-300 hover:text-red-500 ml-2 shrink-0"
                    title="删除"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* 右：文档管理 */}
          <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 p-4">
            {!selected ? (
              <p className="text-sm text-gray-400 py-12 text-center">选择或创建一个知识库</p>
            ) : (
              <>
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h2 className="font-medium">{selected.name}</h2>
                    <p className="text-xs text-gray-400">共 {selected.chunk_count} 个知识块</p>
                  </div>
                  <div>
                    <input ref={fileRef} type="file" accept=".pdf" hidden onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])} />
                    <button
                      onClick={() => fileRef.current?.click()}
                      disabled={busy}
                      className="rounded-lg bg-primary text-white text-sm px-4 py-2 disabled:opacity-40"
                    >
                      📄 上传 PDF
                    </button>
                  </div>
                </div>
                <div className="space-y-2">
                  {selected.docs.length === 0 && (
                    <p className="text-sm text-gray-400 py-8 text-center">暂无文档，点击右上角上传</p>
                  )}
                  {selected.docs.map((doc) => (
                    <div key={doc.doc_id} className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2">
                      <span className="text-sm truncate">{doc.filename}</span>
                      <div className="flex items-center gap-2 shrink-0">
                        {doc.chunk_count > 0 && <span className="text-xs text-gray-400">{doc.chunk_count} 块</span>}
                        {statusBadge(doc.status)}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
