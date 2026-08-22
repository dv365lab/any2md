"""Pydantic 请求/响应模型。"""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel

JobStatus = Literal["queued", "running", "done", "error"]


class ConvertResponse(BaseModel):
    job_id: str


class StatusResponse(BaseModel):
    status: JobStatus
    progress: int
    message: str = ""


class ResultResponse(BaseModel):
    filename: str
    markdown: str
    images: List[str]


class ErrorResponse(BaseModel):
    detail: str
