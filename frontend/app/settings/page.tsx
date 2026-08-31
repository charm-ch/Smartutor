"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getSettings, saveSettings, testConnection } from "@/lib/api";
import type { Settings, TestResult } from "@/lib/types";

/**
 * API 配置页（USTC LLM 平台适配）：
 * - 默认 Base URL: https://api.llm.ustc.edu.cn/v1（OpenAI 兼容）
 * - 测试连接：后端代理请求 /models 拉取可用模型列表（Key 不落前端）
 * - 保存：Key 写入服务端 data/settings.json
 */
export default function SettingsPage() {
  const [baseUrl, setBaseUrl] = useState("https://api.llm.ustc.edu.cn/v1");
  const [apiKey, setApiKey] = useState("");
  const [chatModel, setChatModel] = useState("deepseek-v4-flash");
  const [visionModel, setVisionModel] = useState("");
  const [embeddingModel, setEmbeddingModel] = useState("bge-m3");
  const [embeddingLocal, setEmbeddingLocal] = useState(true);
  const [masked, setMasked] = useState("");
  const [hasKey, setHasKey] = useState(false);

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getSettings()
      .then((s: Settings) => {
        setBaseUrl(s.base_url);
        setChatModel(s.chat_model);
        setVisionModel(s.vision_model);
        setEmbeddingModel(s.embedding_model);
        setEmbeddingLocal(s.embedding_use_local);
        setMasked(s.api_key_masked);
        setHasKey(s.has_api_key);
      })
      .catch((e) => setError(`读取配置失败：${e instanceof Error ? e.message : String(e)}`));
  }, []);

  const handleTest = async () => {
    if (!apiKey && !hasKey) {
      setTestResult({ ok: false, models: [], message: "请先填写 API Key" });
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const r = await testConnection(baseUrl, apiKey);
      setTestResult(r);
      if (r.ok) setModels(r.models);
    } catch (e) {
      setTestResult({ ok: false, models: [], message: `测试失败：${e instanceof Error ? e.message : String(e)}` });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      const s = await saveSettings({
        base_url: baseUrl,
        api_key: apiKey,
        chat_model: chatModel,
        vision_model: visionModel,
        embedding_model: embeddingModel,
        embedding_use_local: embeddingLocal,
      });
      setMasked(s.api_key_masked);
      setHasKey(s.has_api_key);
      setApiKey("");
      setSaved(true);
    } catch (e) {
      setError(`保存失败：${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold">API 配置</h1>
            <p className="text-xs text-gray-400 mt-0.5">
              USTC 大模型公共服务平台 · API Key 保存在服务端，不落前端
            </p>
          </div>
          <Link
            href="/"
            className="text-sm text-blue-600 hover:text-blue-800 border border-blue-200 rounded-lg px-3 py-1.5"
          >
            ← 返回对话
          </Link>
        </header>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm p-3">
            {error}
          </div>
        )}

        <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Base URL
            </label>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.llm.ustc.edu.cn/v1"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              学校平台默认地址，兼容 OpenAI API 格式
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              API Key
              {hasKey && (
                <span className="ml-2 text-xs text-green-600 bg-green-50 border border-green-200 rounded px-1.5 py-0.5">
                  已配置：{masked}
                </span>
              )}
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={hasKey ? "留空则保留当前 Key" : "sk-…"}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex items-center justify-between mt-2">
              <p className="text-xs text-gray-400">填写后可先测试连接，再保存</p>
              <button
                onClick={handleTest}
                disabled={testing}
                className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40"
              >
                {testing ? "测试中…" : "🔌 测试连接"}
              </button>
            </div>
            {testResult && (
              <div
                className={`mt-2 text-sm rounded-lg p-3 ${
                  testResult.ok
                    ? "bg-green-50 border border-green-200 text-green-700"
                    : "bg-orange-50 border border-orange-200 text-orange-700"
                }`}
              >
                {testResult.message}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                对话模型（chat）
              </label>
              <input
                value={chatModel}
                onChange={(e) => setChatModel(e.target.value)}
                list="model-options"
                placeholder="deepseek-v4-flash"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                视觉模型（vision，可留空）
              </label>
              <input
                value={visionModel}
                onChange={(e) => setVisionModel(e.target.value)}
                list="model-options"
                placeholder="留空则使用对话模型"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          {models.length > 0 && (
            <datalist id="model-options">
              {models.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Embedding 模型
              </label>
              <input
                value={embeddingModel}
                onChange={(e) => setEmbeddingModel(e.target.value)}
                placeholder="bge-m3"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={embeddingLocal}
                  onChange={(e) => setEmbeddingLocal(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300"
                />
                使用本地 Embedding（bge-m3，推荐）
              </label>
            </div>
          </div>

          <div className="border-t border-gray-100 pt-4 flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-xl bg-primary px-6 py-2.5 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-40"
            >
              {saving ? "保存中…" : "💾 保存配置"}
            </button>
            {saved && (
              <span className="ml-3 self-center text-sm text-green-600">✓ 已保存</span>
            )}
          </div>
        </div>

        <p className="mt-4 text-xs text-gray-400 leading-relaxed">
          提示：模型列表可通过「测试连接」自动获取（学校平台 /models 接口）。
          按平台文档建议，API Key 仅保存在服务端（data/settings.json），浏览器不落盘。
        </p>
      </div>
    </main>
  );
}
