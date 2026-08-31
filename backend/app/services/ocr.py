"""OCR 服务：使用 USTC API 的 unlimited-ocr 模型解析扫描版 PDF。"""
import asyncio
import base64
import json
import re
from pathlib import Path

from app.core.config import settings
from app.services import llm


class OCRError(Exception):
    """OCR 处理失败。"""


async def pdf_to_images(pdf_path: Path, dpi: int = 200) -> list[bytes]:
    """将 PDF 每页转为图片（PNG 格式）。
    
    Args:
        pdf_path: PDF 文件路径
        dpi: 分辨率（默认 200）
    
    Returns:
        每页图片的 bytes 列表
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise OCRError("PyMuPDF 未安装")
    
    doc = fitz.open(pdf_path)
    images = []
    
    for page in doc:
        # 渲染为图片
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        images.append(img_bytes)
    
    doc.close()
    return images


async def ocr_image(image_bytes: bytes) -> str:
    """使用 unlimited-ocr 模型识别图片文字。
    
    Args:
        image_bytes: 图片 bytes
    
    Returns:
        识别的文字内容
    """
    # 将图片转为 base64
    img_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    # 调用 LLM API（使用 unlimited-ocr 模型）
    # 注意：这里需要构造多模态请求
    prompt = "请识别这张图片中的所有文字内容，包括公式、图表说明等。按原文排版输出。"
    
    # 使用 chat_once 调用（需要支持视觉的模型）
    result = await llm.chat_once(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                    },
                ],
            }
        ],
        model="unlimited-ocr",  # 指定 OCR 模型
    )
    
    return result.get("content", "")


async def ocr_pdf(pdf_path: Path) -> str:
    """完整 OCR 流程：PDF → 图片 → OCR → 文本。
    
    Args:
        pdf_path: PDF 文件路径
    
    Returns:
        识别的完整文本内容
    """
    # 1. PDF 转图片
    images = await pdf_to_images(pdf_path)
    
    # 2. 逐页 OCR
    texts = []
    for i, img_bytes in enumerate(images):
        text = await ocr_image(img_bytes)
        texts.append(f"--- 第{i+1}页 ---\n{text}")
    
    # 3. 合并结果
    return "\n\n".join(texts)


async def parse_pdf_with_ocr(pdf_path: Path, doc_id: str) -> list:
    """使用 OCR 解析 PDF 并返回 Chunk 列表。
    
    Args:
        pdf_path: PDF 文件路径
        doc_id: 文档 ID
    
    Returns:
        Chunk 列表
    """
    from app.services.rag import _parse_filename, _split_text
    
    # 1. OCR 识别
    full_text = await ocr_pdf(pdf_path)
    
    # 2. 解析元数据
    doc_name, chapter = _parse_filename(pdf_path.name)
    
    # 3. 分块
    chunks_text = _split_text(full_text, settings.chunk_size, settings.chunk_overlap)
    
    # 4. 构造 Chunk
    chunks = []
    for seq, text in enumerate(chunks_text, start=1):
        chunks.append(
            {
                "id": f"{doc_id}_c{seq}",
                "doc_id": doc_id,
                "seq": seq,
                "content": text,
                "chapter": chapter,
                "page": (seq - 1) // 3 + 1,  # 粗略估算页码
                "doc_name": doc_name,
            }
        )
    
    return chunks
