"""/api 路由。"""
from __future__ import annotations

import re
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from . import config
from .jobs import Job, JobManager
from .models import ConvertResponse, ResultResponse, StatusResponse

router = APIRouter()

_manager: Optional[JobManager] = None


def init(manager: JobManager) -> None:
    """由应用入口注入 JobManager（便于测试替换为假引擎）。"""
    global _manager
    _manager = manager


def _get_manager() -> JobManager:
    if _manager is None:
        raise RuntimeError("JobManager has not been initialised")
    return _manager


def _get_job_or_404(job_id: str) -> Job:
    job = _get_manager().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# MinerU 生成的 Markdown 中图片为相对路径 images/xxx，改写到 /api/files
_IMG_LINK = re.compile(r"(!\[[^\]]*\]\()\s*(\.?/?images/)")

# 支持的扩展名 → (魔数, 描述)
_SIGNATURES = {
    ".pdf": (b"%PDF", "PDF"),
    ".docx": (b"PK", "Word"),  # docx 是 zip 容器
    ".doc": (b"\xd0\xcf\x11\xe0", "Word"),  # 老式 OLE2 复合文档
    ".pptx": (b"PK", "PowerPoint"),  # pptx 是 zip 容器
    ".ppt": (b"\xd0\xcf\x11\xe0", "PowerPoint"),  # 老式 OLE2 复合文档
}

# 源文件的 media type（浏览器只对 PDF 做内联预览，Word/PPT 触发下载）
_SOURCE_MEDIA = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
}


@router.post("/api/convert", response_model=ConvertResponse)
async def convert(
    file: UploadFile = File(...),
    lang: str = Form(default=""),
    force_ocr: bool = Form(default=False),
) -> ConvertResponse:
    filename = file.filename or "document.pdf"
    ext = Path(filename).suffix.lower()
    if ext not in _SIGNATURES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Supported: " + ", ".join(sorted(_SIGNATURES)),
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {config.MAX_UPLOAD_MB} MB limit",
        )
    magic, kind = _SIGNATURES[ext]
    if not data.startswith(magic):
        raise HTTPException(status_code=400, detail=f"Invalid {kind} file (bad magic bytes)")

    config.ensure_dirs()
    job_id = uuid.uuid4().hex
    pdf_path = config.UPLOAD_DIR / f"{job_id}{ext}"
    pdf_path.write_bytes(data)

    chosen_lang = (lang or "").strip() or config.DEFAULT_LANG
    _get_manager().submit(
        job_id=job_id,
        filename=filename,
        pdf_path=pdf_path,
        output_dir=config.OUTPUT_DIR / job_id,
        lang=chosen_lang,
        force_ocr=force_ocr,
    )
    return ConvertResponse(job_id=job_id)


@router.get("/api/status/{job_id}", response_model=StatusResponse)
def status(job_id: str) -> StatusResponse:
    job = _get_job_or_404(job_id)
    return StatusResponse(status=job.status, progress=job.progress, message=job.message)


@router.get("/api/result/{job_id}", response_model=ResultResponse)
def result(job_id: str) -> ResultResponse:
    job = _get_job_or_404(job_id)
    if job.status != "done" or job.markdown_path is None:
        raise HTTPException(status_code=409, detail=f"Job not finished (status={job.status})")

    markdown = job.markdown_path.read_text(encoding="utf-8")
    markdown = _IMG_LINK.sub(rf"\1/api/files/{job_id}/images/", markdown)

    images: list[str] = []
    if job.images_dir and job.images_dir.is_dir():
        images = sorted(p.name for p in job.images_dir.iterdir() if p.is_file())
    return ResultResponse(filename=job.filename, markdown=markdown, images=images)


@router.get("/api/source/{job_id}")
def source(job_id: str) -> FileResponse:
    """返回原始文件。PDF 供前端 <iframe> 并排预览；Word 浏览器无法内联预览。"""
    job = _get_job_or_404(job_id)
    if not job.pdf_path.is_file():
        raise HTTPException(status_code=404, detail="Source file not found")
    media = _SOURCE_MEDIA.get(job.pdf_path.suffix.lower(), "application/octet-stream")
    return FileResponse(job.pdf_path, media_type=media, filename=job.filename)


@router.get("/api/files/{job_id}/{path:path}")
def files(job_id: str, path: str) -> FileResponse:
    """提供抽取出的图片等资源，带路径穿越防护。

    Markdown 中图片为相对 .md 所在目录的路径（images/xxx），故以该目录为基准。
    """
    job = _get_job_or_404(job_id)
    base_dir = job.markdown_path.parent if job.markdown_path else job.output_dir
    base = base_dir.resolve()
    target = (base / path).resolve()
    if not target.is_relative_to(base) or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)


@router.get("/api/download/{job_id}")
def download(job_id: str, format: str = Query(default="md", pattern="^(md|zip)$")) -> FileResponse:
    job = _get_job_or_404(job_id)
    if job.status != "done" or job.markdown_path is None:
        raise HTTPException(status_code=409, detail=f"Job not finished (status={job.status})")

    stem = Path(job.filename).stem or "document"
    if format == "md":
        return FileResponse(
            job.markdown_path, media_type="text/markdown", filename=f"{stem}.md"
        )

    zip_path = job.output_dir / f"{stem}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(job.markdown_path, arcname=f"{stem}.md")
        if job.images_dir and job.images_dir.is_dir():
            for p in sorted(job.images_dir.rglob("*")):
                if p.is_file():
                    zf.write(p, arcname=str(Path("images") / p.relative_to(job.images_dir)))
    return FileResponse(zip_path, media_type="application/zip", filename=f"{stem}.zip")
