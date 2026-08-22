"""任务管理：线程池 + 内存任务表，状态流转 queued → running → done|error。"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .converter import Converter


@dataclass
class Job:
    id: str
    filename: str
    pdf_path: Path
    output_dir: Path
    lang: str = "ch"
    force_ocr: bool = False
    status: str = "queued"  # queued | running | done | error
    progress: int = 0
    message: str = ""
    markdown_path: Optional[Path] = None
    images_dir: Optional[Path] = None


class JobManager:
    """一次转换可能几十秒到几分钟，必须异步：上传即返回 job_id，前端轮询状态。"""

    def __init__(self, converter: Optional[Converter] = None, max_workers: int = 2) -> None:
        # converter 为 None 时按文件扩展名自动路由（pdf→MinerU，docx/doc→Word）
        self._converter = converter
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        *,
        job_id: str,
        filename: str,
        pdf_path: Path,
        output_dir: Path,
        lang: str,
        force_ocr: bool,
    ) -> Job:
        job = Job(
            id=job_id,
            filename=filename,
            pdf_path=pdf_path,
            output_dir=output_dir,
            lang=lang,
            force_ocr=force_ocr,
        )
        with self._lock:
            self._jobs[job.id] = job
        self._executor.submit(self._run, job.id)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def _update(self, job_id: str, **fields: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for key, value in fields.items():
                setattr(job, key, value)

    def _run(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        self._update(job_id, status="running", progress=10, message="转换引擎运行中…")
        try:
            converter = self._resolve_converter(job.filename)
            result = converter.convert(
                job.pdf_path,
                job.output_dir,
                lang=job.lang,
                force_ocr=job.force_ocr,
            )
        except Exception as exc:  # 捕获任何引擎异常并写入 message
            self._update(job_id, status="error", progress=100, message=str(exc))
            return
        self._update(
            job_id,
            status="done",
            progress=100,
            message="转换完成",
            markdown_path=result.markdown_path,
            images_dir=result.images_dir,
        )

    def _resolve_converter(self, filename: str) -> Converter:
        if self._converter is not None:
            return self._converter
        from .converter import get_converter_for

        return get_converter_for(filename)
