#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RAGAS 评测「智学」答疑链路。

指标：faithfulness（忠实度/防幻觉）、answer_relevancy（答案相关性）、
context_precision（上下文精确率）、context_recall（上下文召回率）。

数据路径与生产一致：
- contexts: app.services.rag.retrieve（与 conversations.py 同源）
- 提示词:   app.api.conversations._SYSTEM_PROMPT + _build_context（生产同款）
- 答案:     app.services.llm.chat_once（含生产重试逻辑）
- judge:    settings.json 的 chat_model（GLM，OpenAI 兼容）
- embeddings: 本地 bge-small-zh-v1.5（离线）

用法（服务器）:
  cd /opt/zhixue/backend && .venv/bin/python ../tools/eval/run_ragas_eval.py [--kb <id>] [--limit N]
输出: /opt/zhixue/data/eval/ragas-report-<ts>.{json,md} + stdout
"""
import argparse
import asyncio
import json
import os
import sys
import time
import types
from datetime import datetime

# ---- ragas 0.4.3 兼容 shim：langchain-community>=0.4 移除了 vertexai 模块 ----
_shim = types.ModuleType("langchain_community.chat_models.vertexai")
class ChatVertexAI:  # noqa: 占位，ragas 仅在 import 时引用该符号
    pass
_shim.ChatVertexAI = ChatVertexAI
sys.modules.setdefault("langchain_community.chat_models.vertexai", _shim)

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

BACKEND = "/opt/zhixue/backend"
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)  # 让 pydantic-settings 读到 backend/.env

OUT_DIR = "/opt/zhixue/data/eval"

# ---- 评测集：20 问（源自 tools/retrieval-eval.sh）+ 参考答案 ----
EVAL_SET = [
    ("什么是空指针？解引用会怎样？",
     "空指针是值为 NULL、不指向任何有效对象的指针；解引用它是未定义行为，通常导致段错误崩溃。"),
    ("野指针是什么？",
     "野指针是未初始化或指向已失效内存的指针，其值不确定，解引用会产生不可预测后果。"),
    ("悬空指针怎么产生？",
     "指针指向的内存被 free 释放后指针未置 NULL，就产生悬空指针；free 后应立即置 NULL。"),
    ("数组下标越界会怎么样？",
     "越界访问是未定义行为，可能程序崩溃、读到垃圾值或静默破坏相邻内存数据。"),
    ("怎么计算数组元素个数？",
     "用 sizeof(arr) / sizeof(arr[0]) 计算数组元素个数，仅对编译期完整数组类型有效。"),
    ("二维数组怎么定义？",
     "静态定义如 int a[3][4]；指针形式 int (*p)[4] = a；动态分配用 malloc 按行或连续分配。"),
    ("for循环死循环的常见原因？",
     "常见原因：循环变量忘记更新、更新方向与终止条件相反、循环条件永真（如浮点精度问题）。"),
    ("break和continue的区别？",
     "break 立即终止整个循环；continue 只跳过本次循环体剩余语句，进入下一轮条件判断。"),
    ("怎么调试死循环？",
     "用 gdb 在运行中 Ctrl+C 暂停查看调用栈、加打印日志观察变量、用 top 观察 CPU 占用定位进程。"),
    ("函数参数是值传递还是引用传递？",
     "C 语言函数参数是值传递（形参是实参的拷贝）；要修改实参需传指针，数组传参退化为指针。"),
    ("递归必须有终止条件吗？",
     "必须有终止条件（base case），否则无限递归导致栈溢出崩溃。"),
    ("返回局部变量的地址有什么问题？",
     "局部变量存于栈帧，函数返回后栈帧销毁，返回其地址得到悬空指针，解引用是未定义行为。"),
    ("malloc失败返回什么？",
     "malloc 分配失败返回 NULL，使用返回指针前必须判空。"),
    ("内存泄漏是什么？",
     "动态分配（malloc/realloc）的内存使用完毕后未 free，导致这块内存无法复用，长期运行会耗尽内存。"),
    ("double free会怎样？",
     "同一块堆内存被释放两次是未定义行为，会破坏堆管理结构，可能导致程序崩溃。"),
    ("怎么检测内存泄漏？",
     "用 valgrind 的 memcheck 工具，或编译时加 AddressSanitizer（-fsanitize=address）。"),
    ("strlen和sizeof的区别？",
     "strlen 是运行时函数，统计字符串字符数（不含结尾 '\\0'）；sizeof 是编译期运算符，求变量/类型占字节数（含 '\\0'）。"),
    ("字符串常量能修改吗？",
     "不能。字符串常量存放在只读数据段，试图修改是未定义行为。"),
    ("结构体指针怎么访问成员？",
     "用箭头运算符 p->member，等价于 (*p).member。"),
    ("fopen失败返回什么？",
     "fopen 打开失败返回 NULL（如文件不存在、无权限），必须检查返回值后才能使用。"),
]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def pick_kb(kb_arg: str | None) -> str:
    """选 KB：优先 --kb，否则取库里第一个。"""
    from app.core import db as appdb

    async def _q():
        try:
            rows = await appdb.fetch_all("SELECT id, name FROM kb ORDER BY created_at DESC")
        except Exception:  # 列名差异时回退
            rows = await appdb.fetch_all("SELECT id, name FROM kb")
        return [(r["id"], r["name"]) for r in rows]

    kbs = asyncio.run(_q())
    if not kbs:
        raise SystemExit("库中没有任何 KB，请先上传课程 PDF。")
    for kid, name in kbs:
        log(f"可用 KB: {kid}  {name}")
    if kb_arg:
        if not any(k == kb_arg for k, _ in kbs):
            raise SystemExit(f"--kb {kb_arg} 不存在")
        return kb_arg
    log(f"未指定 --kb，默认用第一个: {kbs[0][0]}")
    return kbs[0][0]


async def build_rows(kb_id: str, limit: int) -> list[dict]:
    """检索 + 生成答案（生产同款链路）。"""
    from app.api.conversations import _SYSTEM_PROMPT, _build_context
    from app.services import rag
    from app.services.llm import chat_once

    data = []
    total_tokens = 0
    for i, (q, ref) in enumerate(EVAL_SET[:limit], 1):
        t0 = time.monotonic()
        try:
            retrieved = [dict(r) for r in await rag.retrieve(kb_id, q)]
        except rag.RAGError as e:
            log(f"[{i}/20] 检索失败 {e}，按空资料处理")
            retrieved = []
        contexts = [
            f"《{r.get('doc_name', '')}》{r.get('chapter', '')} 第{r.get('page', '')}页："
            f"{r.get('content') or r.get('snippet', '')}"
            for r in retrieved
        ]
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_context(q, retrieved, None)},
        ]
        msg = await chat_once(messages)
        answer = (msg.get("content") or "").strip()
        usage = msg.get("usage") or {}
        total_tokens += (usage.get("prompt_tokens", 0) or 0) + (usage.get("completion_tokens", 0) or 0)
        dt = time.monotonic() - t0
        log(f"[{i}/20] {dt:.1f}s ctx={len(contexts)} ans={len(answer)}字 | {q}")
        data.append({
            "user_input": q,
            "retrieved_contexts": contexts,
            "response": answer,
            "reference": ref,
        })
    log(f"生成阶段完成，共 {total_tokens} tokens")
    return data


class LocalBGE:
    """langchain Embeddings 适配器 → 本地 sentence-transformers（离线）。"""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        log(f"加载本地 embedding: {model_name}")
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default=None)
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    from ragas import evaluate, RunConfig
    try:
        from ragas import EvaluationDataset as ED
    except ImportError:
        from ragas.evaluation import EvaluationDataset as ED
    from ragas.metrics import (
        faithfulness, answer_relevancy, context_precision, context_recall,
    )
    from langchain_openai import ChatOpenAI

    cfg = json.load(open("/opt/zhixue/data/settings.json", encoding="utf-8"))
    base_url, key, chat_model = cfg["api_base_url"], cfg["api_key"], cfg["chat_model"]
    embed_model = cfg.get("embedding_model") or "BAAI/bge-small-zh-v1.5"

    kb_id = pick_kb(args.kb)
    log(f"== 阶段 1/2：真实链路生成 {args.limit} 条 QA（KB={kb_id}）==")
    rows = asyncio.run(build_rows(kb_id, args.limit))

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_base = os.path.join(OUT_DIR, f"ragas-report-{ts}")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_base + ".dataset.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    log(f"评测数据集已存 {out_base}.dataset.json")

    log("== 阶段 2/2：RAGAS 四指标评审（GLM judge + 本地 bge）==")
    judge = ChatOpenAI(
        model=chat_model, base_url=base_url, api_key=key,
        temperature=0, timeout=180, max_retries=2,
    )
    emb = LocalBGE(embed_model)
    dataset = ED.from_list(rows)
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=judge,
        embeddings=emb,
        run_config=RunConfig(max_workers=2, max_retries=2, timeout=300),
        show_progress=True,
    )

    df = result.to_pandas()
    scores = {}
    for m in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        if m in df.columns:
            scores[m] = round(float(df[m].mean()), 4)
    log(f"总分: {json.dumps(scores, ensure_ascii=False)}")

    with open(out_base + ".json", "w", encoding="utf-8") as f:
        json.dump({"kb": kb_id, "chat_model": chat_model, "embed_model": embed_model,
                   "n": len(rows), "scores": scores}, f, ensure_ascii=False, indent=1)
    df.to_json(out_base + ".detail.json", orient="records", force_ascii=False)

    lines = [
        "# RAGAS 评测报告（智学答疑链路）",
        f"- 时间: {ts} | KB: {kb_id} | 样本: {len(rows)} | judge: {chat_model} | embeddings: {embed_model}",
        "",
        "| 指标 | 得分 | 含义 |",
        "|---|---|---|",
        f"| faithfulness | {scores.get('faithfulness', '-')} | 回答忠实于检索资料的程度（防幻觉） |",
        f"| answer_relevancy | {scores.get('answer_relevancy', '-')} | 回答与问题的相关性 |",
        f"| context_precision | {scores.get('context_precision', '-')} | 检索块中相关内容的排序质量 |",
        f"| context_recall | {scores.get('context_recall', '-')} | 参考答案所需信息被检索覆盖的比例 |",
        "",
        "| # | 问题 | faith | relev | c_prec | c_rec |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in df.iterrows():
        q = str(r["user_input"])[:24]
        vals = [r.get(m, "-") for m in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]]
        vals = ["-" if (isinstance(v, float) and v != v) else round(float(v), 3) for v in vals]
        lines.append(f"| {i + 1} | {q} | {vals[0]} | {vals[1]} | {vals[2]} | {vals[3]} |")
    with open(out_base + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log(f"报告已写 {out_base}.md / .json / .detail.json")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
