"""RAG 服务（M1）：PDF 解析 → 分块 → 向量化 → 检索。

- 解析：PyMuPDF 逐页抽取，按 chunk_size 字符滑窗切块（重叠 chunk_overlap）
- 元数据：从文件名 `<书名>-第N章-<章节名>.pdf` 提取 doc_name / chapter，页码逐页记录
- 向量：FAISS IndexFlatIP（归一化后内积=余弦），每个 KB 一个索引文件
- 检索结果必须含 doc_name/chapter/page/snippet 四元组（契约 §6）
"""
import asyncio
import json
from pathlib import Path

import faiss
import numpy as np

from app.core import db
from app.core.config import settings
from app.services import llm


class RAGError(Exception):
    """检索/解析失败。"""


class RetrievedChunk(dict):
    """检索结果：doc_name / chapter / page / snippet / score。"""


# ---------- FAISS 索引管理 ----------

_FAISS_DIR = Path(settings.kb_data_dir).parent / "faiss"
_kb_locks: dict[str, asyncio.Lock] = {}


def _kb_lock(kb_id: str) -> asyncio.Lock:
    if kb_id not in _kb_locks:
        _kb_locks[kb_id] = asyncio.Lock()
    return _kb_locks[kb_id]


def _index_path(kb_id: str) -> Path:
    return _FAISS_DIR / f"{kb_id}.index"


def _ids_path(kb_id: str) -> Path:
    return _FAISS_DIR / f"{kb_id}.ids.json"


def _load_index(kb_id: str) -> tuple[faiss.Index | None, list[str]]:
    if not _index_path(kb_id).exists():
        return None, []
    index = faiss.read_index(str(_index_path(kb_id)))
    ids = json.loads(_ids_path(kb_id).read_text(encoding="utf-8"))
    return index, ids


def _save_index(kb_id: str, index: faiss.Index, ids: list[str]) -> None:
    _FAISS_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(_index_path(kb_id)))
    _ids_path(kb_id).write_text(json.dumps(ids, ensure_ascii=False), encoding="utf-8")


# ---------- 元数据解析 ----------

def _parse_filename(filename: str) -> tuple[str, str]:
    """`C程序设计-第8章-指针.pdf` → (doc_name='C程序设计', chapter='第8章 指针')。"""
    stem = Path(filename).stem
    parts = stem.split("-")
    if len(parts) >= 3:
        return parts[0], f"{parts[1]} {parts[2]}".strip()
    if len(parts) == 2:
        return parts[0], parts[1]
    return stem, ""


# ---------- 解析与切块 ----------

def _clean_text(text: str) -> str:
    """清理 PostgreSQL 不接受的 NUL (0x00) 字节，避免入库报错。"""
    return text.replace("\x00", "")


def _split_text(text: str, size: int, overlap: int) -> list[str]:
    """滑窗切块。优先在换行/句号边界断开。"""
    text = _clean_text(text).strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # 在窗口后 1/3 内找断行点
            window = text[start + size // 2 : end]
            for sep in ("\n\n", "\n", "。", "；"):
                pos = window.rfind(sep)
                if pos > 0:
                    end = start + size // 2 + pos + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


async def parse_pdf(path: Path, doc_id: str, use_ocr: bool = False) -> list:
    """解析 PDF → Chunk 列表（含元数据）。
    
    Args:
        path: PDF 文件路径
        doc_id: 文档 ID
        use_ocr: 是否使用 unlimited-ocr 模型（适合扫描版 PDF）
    """
    if use_ocr:
        return await _parse_pdf_with_ocr(path, doc_id)
    return await _parse_pdf_with_pymupdf(path, doc_id)


async def _parse_pdf_with_pymupdf(path: Path, doc_id: str) -> list:
    """使用 PyMuPDF 解析 PDF（适合文字版 PDF）。"""
    import fitz  # PyMuPDF

    doc_name, chapter = _parse_filename(path.name)
    chunks = []
    try:
        doc = fitz.open(path)
    except Exception as e:  # noqa: BLE001
        raise RAGError(f"E_PARSE_FAILED: {e}") from e

    seq = 0
    buffer = ""
    buffer_page = 0
    for page_no, page in enumerate(doc, start=1):
        page_text = _clean_text(page.get_text("text")).strip()
        if not page_text:
            continue
        if not buffer:
            buffer_page = page_no
        buffer += page_text + "\n"
        # 累积超过 2 倍块大小时切一次，保留末块继续跨页累积
        if len(buffer) >= settings.chunk_size * 2:
            pieces = _split_text(buffer, settings.chunk_size, settings.chunk_overlap)
            for piece in pieces[:-1]:
                seq += 1
                chunks.append(
                    {
                        "id": f"{doc_id}_c{seq}",
                        "doc_id": doc_id,
                        "seq": seq,
                        "content": piece,
                        "chapter": chapter,
                        "page": buffer_page,
                        "doc_name": doc_name,
                    }
                )
            buffer = pieces[-1] if pieces else ""
            buffer_page = page_no
    if buffer.strip():
        seq += 1
        chunks.append(
            {
                "id": f"{doc_id}_c{seq}",
                "doc_id": doc_id,
                "seq": seq,
                "content": buffer.strip(),
                "chapter": chapter,
                "page": buffer_page,
                "doc_name": doc_name,
            }
        )
    doc.close()
    return chunks


async def _parse_pdf_with_ocr(path: Path, doc_id: str) -> list:
    """使用 unlimited-ocr 模型解析 PDF（适合扫描版/图片型 PDF）。"""
    from app.services import ocr
    
    try:
        return await ocr.parse_pdf_with_ocr(path, doc_id)
    except Exception as e:  # noqa: BLE001
        raise RAGError(f"E_OCR_FAILED: {e}") from e


# ---------- 入库 ----------

async def index_document(doc_id: str, chunks: list) -> int:
    """向量化 + 写 chunks 表 + 追加 FAISS 索引。返回入库块数。"""
    if not chunks:
        return 0

    kb_id = await _doc_kb(doc_id)
    texts = [c["content"] for c in chunks]
    vectors = await llm.embed_texts(texts)
    mat = np.asarray(vectors, dtype="float32")
    faiss.normalize_L2(mat)

    async with _kb_lock(kb_id):
        # 元数据入库
        for c in chunks:
            await db.execute(
                """INSERT INTO chunks (id, doc_id, seq, content, chapter, page)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO NOTHING""",
                (c["id"], c["doc_id"], c["seq"], c["content"], c["chapter"], c["page"]),
            )
        # 追加向量
        index, ids = _load_index(kb_id)
        if index is None:
            dim = mat.shape[1]
            index = faiss.IndexFlatIP(dim)
            ids = []
        index.add(mat)
        ids.extend(c["id"] for c in chunks)
        _save_index(kb_id, index, ids)

    await db.execute("UPDATE documents SET status='parsed', chunk_count=%s WHERE id=%s",
                     (len(chunks), doc_id))
    return len(chunks)


async def _doc_kb(doc_id: str) -> str:
    row = await db.fetch_one("SELECT kb_id FROM documents WHERE id=%s", (doc_id,))
    if row is None:
        raise RAGError("E_NOT_FOUND: 文档不存在")
    return row["kb_id"]


# ---------- 检索 ----------

async def retrieve(kb_id: str, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
    """检索 Top-k：query 向量化 → FAISS → 元数据四元组。"""
    k = top_k or settings.retrieval_top_k
    async with _kb_lock(kb_id):
        index, ids = _load_index(kb_id)
    if index is None or index.ntotal == 0:
        raise RAGError("E_EMPTY_KB")

    qv = np.asarray((await llm.embed_texts([query]))[0], dtype="float32").reshape(1, -1)
    faiss.normalize_L2(qv)
    k = min(k, index.ntotal)
    scores, rows = index.search(qv, k)

    chunk_ids = [ids[i] for i in rows[0] if 0 <= i < len(ids)]
    if not chunk_ids:
        return []
    placeholders = ",".join(["%s"] * len(chunk_ids))
    rows_meta = await db.fetch_all(
        f"""SELECT c.id, c.content, c.chapter, c.page, d.filename
            FROM chunks c JOIN documents d ON c.doc_id = d.id
            WHERE c.id IN ({placeholders})""",
        tuple(chunk_ids),
    )
    meta_map = {m["id"]: m for m in rows_meta}

    results = []
    for pos, cid in enumerate(chunk_ids):
        m = meta_map.get(cid)
        if m is None:
            continue
        doc_name, chapter = _parse_filename(m["filename"])
        results.append(
            RetrievedChunk(
                doc_name=doc_name,
                chapter=chapter or m["chapter"] or "",
                page=m["page"],
                snippet=m["content"][:300],  # 卡片展示用
                content=m["content"],  # 完整内容：LLM 上下文用
                score=float(scores[0][pos]),
            )
        )
    return results


async def get_doc_status(kb_id: str, doc_id: str) -> dict:
    row = await db.fetch_one(
        "SELECT id, status, filename, chunk_count, error FROM documents WHERE id=%s AND kb_id=%s",
        (doc_id, kb_id),
    )
    if row is None:
        raise RAGError("E_NOT_FOUND")
    return {
        "doc_id": row["id"],
        "status": row["status"],
        "filename": row["filename"],
        "chunk_count": row["chunk_count"],
        "error": row["error"],
    }
