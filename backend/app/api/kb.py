"""KB 组路由（M1）：知识库管理，契约 §1。"""
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core import db
from app.core.config import settings
from app.schemas.kb import KBDocOut, KBDetail, KBOut
from app.services import rag

router = APIRouter()

_MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


async def _parse_task(kb_id: str, doc_id: str, path: Path) -> None:
    """后台解析任务：自动检测 PDF 类型，失败时更新状态。"""
    try:
        # 先尝试 PyMuPDF 解析
        chunks = await rag.parse_pdf(path, doc_id, use_ocr=False)
        
        # 如果解析结果为空，可能是扫描版 PDF，切换到 OCR
        if not chunks:
            chunks = await rag.parse_pdf(path, doc_id, use_ocr=True)
        
        await rag.index_document(doc_id, chunks)
    except Exception as e:  # noqa: BLE001
        await db.execute(
            "UPDATE documents SET status='failed', error=%s WHERE id=%s",
            (f"E_PARSE_FAILED: {e}", doc_id),
        )


@router.post("", response_model=KBOut)
async def create_kb(payload: dict) -> KBOut:
    name = (payload or {}).get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail={"code": "E_VALIDATION", "message": "name 必填"})
    kb_id = _new_id("kb")
    await db.execute(
        "INSERT INTO kb (id, name, description) VALUES (%s, %s, %s)",
        (kb_id, name, (payload or {}).get("description", "")),
    )
    row = await db.fetch_one("SELECT id, name, description, created_at FROM kb WHERE id=%s", (kb_id,))
    return KBOut(**{**row, "created_at": row["created_at"]})


@router.post("/{kb_id}/documents", response_model=KBDocOut, status_code=202)
async def upload_document(
    kb_id: str, background: BackgroundTasks, file: UploadFile = File(...)
) -> KBDocOut:
    if await db.fetch_one("SELECT id FROM kb WHERE id=%s", (kb_id,)) is None:
        raise HTTPException(status_code=404, detail={"code": "E_NOT_FOUND", "message": "知识库不存在"})
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail={"code": "E_VALIDATION", "message": "仅支持 PDF"})

    content = await file.read()
    if len(content) > _MAX_PDF_SIZE:
        raise HTTPException(status_code=400, detail={"code": "E_VALIDATION", "message": "文件超过 50MB"})

    doc_id = _new_id("doc")
    upload_dir = Path(settings.kb_data_dir) / kb_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).name
    dest = upload_dir / f"{doc_id}_{safe_name}"
    dest.write_bytes(content)

    await db.execute(
        "INSERT INTO documents (id, kb_id, filename, status) VALUES (%s, %s, %s, 'parsing')",
        (doc_id, kb_id, safe_name),
    )
    background.add_task(_parse_task, kb_id, doc_id, dest)
    return KBDocOut(doc_id=doc_id, status="parsing", filename=safe_name)


@router.get("/{kb_id}/documents/{doc_id}", response_model=KBDocOut)
async def get_document_status(kb_id: str, doc_id: str) -> KBDocOut:
    try:
        status = await rag.get_doc_status(kb_id, doc_id)
    except rag.RAGError as e:
        msg = str(e)
        code = msg.split(":")[0] if ":" in msg else "E_NOT_FOUND"
        raise HTTPException(status_code=404, detail={"code": code, "message": msg}) from None
    return KBDocOut(**status)


@router.post("/{kb_id}/documents/{doc_id}/reparse", status_code=202)
async def reparse_document(kb_id: str, doc_id: str, background: BackgroundTasks) -> dict:
    """重新解析文档（用于 OCR 失败后重试）。"""
    # 检查文档是否存在
    doc = await db.fetch_one(
        "SELECT id, filename FROM documents WHERE id=%s AND kb_id=%s",
        (doc_id, kb_id),
    )
    if doc is None:
        raise HTTPException(status_code=404, detail={"code": "E_NOT_FOUND", "message": "文档不存在"})
    
    # 更新状态为解析中
    await db.execute(
        "UPDATE documents SET status='parsing', error=NULL WHERE id=%s",
        (doc_id,),
    )
    
    # 获取文件路径
    upload_dir = Path(settings.kb_data_dir) / kb_id
    # 查找文件（文件名可能包含 doc_id 前缀）
    files = list(upload_dir.glob(f"{doc_id}_*.pdf"))
    if not files:
        raise HTTPException(status_code=404, detail={"code": "E_FILE_NOT_FOUND", "message": "PDF 文件不存在"})
    
    # 后台重新解析
    background.add_task(_parse_task, kb_id, doc_id, files[0])
    
    return {"status": "reparsing", "doc_id": doc_id}


@router.get("/{kb_id}", response_model=KBDetail)
async def get_kb_detail(kb_id: str) -> KBDetail:
    row = await db.fetch_one("SELECT id, name, description, created_at FROM kb WHERE id=%s", (kb_id,))
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "E_NOT_FOUND", "message": "知识库不存在"})
    docs = await db.fetch_all(
        "SELECT id, filename, status, chunk_count FROM documents WHERE kb_id=%s ORDER BY created_at",
        (kb_id,),
    )
    total = sum(d["chunk_count"] or 0 for d in docs)
    return KBDetail(
        id=row["id"],
        name=row["name"],
        description=row["description"] or "",
        created_at=row["created_at"],
        docs=[
            {"doc_id": d["id"], "filename": d["filename"], "status": d["status"], "chunk_count": d["chunk_count"] or 0}
            for d in docs
        ],
        chunk_count=total,
    )


@router.get("", response_model=list[KBOut])
async def list_kbs() -> list[KBOut]:
    rows = await db.fetch_all("SELECT id, name, description, created_at FROM kb ORDER BY created_at DESC")
    return [KBOut(**r) for r in rows]


@router.delete("/{kb_id}", status_code=204)
async def delete_kb(kb_id: str) -> JSONResponse:
    await db.execute("DELETE FROM kb WHERE id=%s", (kb_id,))
    # 清理本地文件与索引
    kb_dir = Path(settings.kb_data_dir) / kb_id
    if kb_dir.is_dir():
        shutil.rmtree(kb_dir, ignore_errors=True)
    faiss_dir = Path(settings.kb_data_dir).parent / "faiss"
    for p in faiss_dir.glob(f"{kb_id}.*"):
        p.unlink(missing_ok=True)
    return JSONResponse(status_code=204)
