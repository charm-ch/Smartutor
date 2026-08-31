"use client";

import Link from "next/link";
import { useState } from "react";

import { createUserProfile } from "@/lib/api";
import type { UserProfileResponse } from "@/lib/types";

export default function UserProfilePage() {
  const [conversationId, setConversationId] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<UserProfileResponse | null>(null);
  const [error, setError] = useState("");

  const handleGenerate = async () => {
    if (!conversationId) {
      setError("请先输入会话 ID");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await createUserProfile({
        conversation_id: conversationId,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-6">
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold">个性化学习画像</h1>
            <p className="text-xs text-gray-400 mt-0.5">
              基于对话历史分析知识点掌握情况，生成强弱点分析和建议
            </p>
          </div>
          <Link
            href="/"
            className="text-sm text-blue-600 border border-blue-200 rounded-lg px-3 py-1.5 hover:bg-blue-50"
          >
            ← 返回对话
          </Link>
        </header>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm p-3">
            {error}
          </div>
        )}

        {/* 配置面板 */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 mb-6">
          <h2 className="text-base font-medium mb-4">画像配置</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                会话 ID
              </label>
              <input
                value={conversationId}
                onChange={(e) => setConversationId(e.target.value)}
                placeholder="输入会话 ID"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <button
            onClick={handleGenerate}
            disabled={loading || !conversationId}
            className="mt-4 w-full rounded-lg bg-primary text-white py-2.5 text-sm font-medium hover:bg-primary-dark disabled:opacity-40"
          >
            {loading ? "生成中..." : "生成学习画像"}
          </button>
        </div>

        {/* 结果展示 */}
        {result && (
          <div className="space-y-4">
            {/* 学习统计 */}
            {result.statistics && (
              <div className="bg-white rounded-2xl border border-gray-200 p-6">
                <h3 className="text-base font-medium mb-3">📊 学习统计</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="rounded-lg bg-gray-50 p-4">
                    <div className="text-sm text-gray-500">总提问数</div>
                    <div className="text-2xl font-semibold text-gray-800">
                      {result.statistics.total_questions}
                    </div>
                  </div>
                  <div className="rounded-lg bg-gray-50 p-4">
                    <div className="text-sm text-gray-500">涉及知识点数</div>
                    <div className="text-2xl font-semibold text-gray-800">
                      {result.statistics.topics_covered}
                    </div>
                  </div>
                  <div className="rounded-lg bg-gray-50 p-4">
                    <div className="text-sm text-gray-500">学习风格</div>
                    <div className="text-2xl font-semibold text-gray-800">
                      {result.statistics.learning_style}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 知识点掌握情况 */}
            {result.knowledge_points && result.knowledge_points.length > 0 && (
              <div className="bg-white rounded-2xl border border-gray-200 p-6">
                <h3 className="text-base font-medium mb-3">📚 知识点掌握情况</h3>
                <div className="space-y-3">
                  {result.knowledge_points.map((kp, index) => (
                    <div key={index} className="rounded-lg bg-gray-50 p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-gray-800">
                          {kp.name}
                        </span>
                        <span className="text-sm text-gray-500">
                          提问 {kp.frequency} 次
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-primary h-2 rounded-full"
                          style={{ width: `${kp.mastery * 100}%` }}
                        ></div>
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        掌握度 {Math.round(kp.mastery * 100)}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 薄弱环节 */}
            {result.weak_points && result.weak_points.length > 0 && (
              <div className="bg-white rounded-2xl border border-gray-200 p-6">
                <h3 className="text-base font-medium mb-3">⚠️ 薄弱环节</h3>
                <ul className="space-y-2">
                  {result.weak_points.map((point, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className="text-red-500">•</span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 优势领域 */}
            {result.strong_points && result.strong_points.length > 0 && (
              <div className="bg-white rounded-2xl border border-gray-200 p-6">
                <h3 className="text-base font-medium mb-3">✅ 优势领域</h3>
                <ul className="space-y-2">
                  {result.strong_points.map((point, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className="text-green-500">•</span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 学习建议 */}
            {result.suggestions && result.suggestions.length > 0 && (
              <div className="bg-white rounded-2xl border border-gray-200 p-6">
                <h3 className="text-base font-medium mb-3">💡 学习建议</h3>
                <ul className="space-y-2">
                  {result.suggestions.map((suggestion, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className="text-blue-500">•</span>
                      <span>{suggestion}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
