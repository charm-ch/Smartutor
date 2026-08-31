"use client";

import Link from "next/link";
import { useState } from "react";

import { createMockExam } from "@/lib/api";
import type { MockExamResponse } from "@/lib/types";

export default function MockExamPage() {
  const [kbId, setKbId] = useState("");
  const [numQuestions, setNumQuestions] = useState(10);
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [includeAnswers, setIncludeAnswers] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MockExamResponse | null>(null);
  const [error, setError] = useState("");
  const [showAnswers, setShowAnswers] = useState(false);

  const handleGenerate = async () => {
    if (!kbId) {
      setError("请先选择知识库");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    setShowAnswers(false);

    try {
      const res = await createMockExam({
        kb_id: kbId,
        num_questions: numQuestions,
        difficulty,
        include_answers: includeAnswers,
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
            <h1 className="text-xl font-semibold">模拟试卷生成</h1>
            <p className="text-xs text-gray-400 mt-0.5">
              基于历年真题风格，生成针对性模拟试题
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
          <h2 className="text-base font-medium mb-4">试卷配置</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                知识库（历年真题）
              </label>
              <input
                value={kbId}
                onChange={(e) => setKbId(e.target.value)}
                placeholder="输入知识库 ID"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                题目数量
              </label>
              <input
                type="number"
                value={numQuestions}
                onChange={(e) => setNumQuestions(parseInt(e.target.value) || 10)}
                min={1}
                max={50}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                难度
              </label>
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as "easy" | "medium" | "hard")}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="easy">简单（基础题为主）</option>
                <option value="medium">中等（基础 + 综合）</option>
                <option value="hard">困难（综合 + 创新）</option>
              </select>
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeAnswers}
                  onChange={(e) => setIncludeAnswers(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300"
                />
                包含参考答案
              </label>
            </div>
          </div>
          <button
            onClick={handleGenerate}
            disabled={loading || !kbId}
            className="mt-4 w-full rounded-lg bg-primary text-white py-2.5 text-sm font-medium hover:bg-primary-dark disabled:opacity-40"
          >
            {loading ? "生成中..." : "生成模拟试卷"}
          </button>
        </div>

        {/* 结果展示 */}
        {result && (
          <div className="space-y-4">
            {/* 题目风格分析 */}
            {result.analysis && (
              <div className="bg-white rounded-2xl border border-gray-200 p-6">
                <h3 className="text-base font-medium mb-3">📊 题目风格分析</h3>
                <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {result.analysis}
                </div>
              </div>
            )}

            {/* 模拟试题 */}
            <div className="bg-white rounded-2xl border border-gray-200 p-6">
              <h3 className="text-base font-medium mb-3">📝 模拟试题</h3>
              <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed markdown-body">
                {result.exam}
              </div>
            </div>

            {/* 参考答案 */}
            {result.answers && (
              <div className="bg-white rounded-2xl border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-base font-medium">✅ 参考答案</h3>
                  <button
                    onClick={() => setShowAnswers(!showAnswers)}
                    className="text-sm text-blue-600 hover:text-blue-800"
                  >
                    {showAnswers ? "收起" : "展开"}
                  </button>
                </div>
                {showAnswers && (
                  <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed markdown-body">
                    {result.answers}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
