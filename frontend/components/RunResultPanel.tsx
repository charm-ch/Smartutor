"use client";

import type { RunResult } from "@/lib/types";

/** 沙箱运行结果面板：代码 + 输出 + 退出码（契约 §3） */
export default function RunResultPanel({ run }: { run: RunResult }) {
  return (
    <div className="mt-2 rounded-lg border border-gray-200 bg-gray-900 text-gray-100 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800 text-xs">
        <span>代码运行</span>
        <span className="text-gray-400">
          {run.exit_code === 0 ? (
            <span className="text-green-400">✓ 运行成功</span>
          ) : (
            <span className="text-red-400">✗ 退出码 {run.exit_code}</span>
          )}{" "}
          · {run.time_ms}ms
        </span>
      </div>
      {run.code && (
        <pre className="px-3 py-2 text-xs overflow-x-auto border-b border-gray-700">
          <code>{run.code}</code>
        </pre>
      )}
      {run.output && (
        <pre className="px-3 py-2 text-xs overflow-x-auto whitespace-pre-wrap">
          <code>{run.output}</code>
        </pre>
      )}
    </div>
  );
}
