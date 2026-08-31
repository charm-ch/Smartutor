"use client";

import type { Citation } from "@/lib/types";

/** 溯源引用卡片（契约 §2.4）：展示 doc_name / chapter / page / snippet */
export default function CitationCard({ citation }: { citation: Citation }) {
  return (
    <div
      className={`mt-2 rounded-lg border p-3 text-sm ${
        citation.verified
          ? "bg-citation-bg border-citation-border"
          : "bg-orange-50 border-orange-300"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-blue-900">
          [{citation.index}] {citation.doc_name}
        </span>
        {citation.verified ? (
          <span className="text-xs text-blue-600 shrink-0">已核实</span>
        ) : (
          <span className="text-xs text-orange-600 shrink-0">待核实</span>
        )}
      </div>
      {(citation.chapter || citation.page > 0) && (
        <div className="mt-0.5 text-xs text-gray-500">
          {citation.chapter}
          {citation.page > 0 && ` · 第${citation.page}页`}
        </div>
      )}
      <p className="mt-1.5 text-gray-700 line-clamp-3">{citation.snippet}</p>
    </div>
  );
}
