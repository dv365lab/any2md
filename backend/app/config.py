"""集中管理配置与路径，所有项均可被环境变量覆盖。"""
from __future__ import annotations

import os
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


BASE_DIR = Path(__file__).resolve().parents[2]  # 项目根目录
FRONTEND_DIR = BASE_DIR / "frontend"

STORAGE_DIR = Path(os.environ.get("ANY2MD_STORAGE", str(BASE_DIR / "storage"))).resolve()
UPLOAD_DIR = STORAGE_DIR / "uploads"
OUTPUT_DIR = STORAGE_DIR / "outputs"

# MinerU 引擎
MINERU_BACKEND = os.environ.get("ANY2MD_MINERU_BACKEND", "pipeline")  # pipeline 为纯 CPU
MINERU_DEVICE = os.environ.get("ANY2MD_MINERU_DEVICE", "")  # torch 设备提示，如 cpu/cuda
DEFAULT_LANG = os.environ.get("ANY2MD_DEFAULT_LANG", "ch")  # 默认 OCR 语言
MINERU_TIMEOUT = _env_int("ANY2MD_MINERU_TIMEOUT", 1800)  # 单文件转换超时（秒）

# 上传
MAX_UPLOAD_MB = _env_int("ANY2MD_MAX_UPLOAD_MB", 100)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# 模型下载
MODEL_SOURCE = os.environ.get("MINERU_MODEL_SOURCE", "huggingface")  # huggingface/modelscope
DISABLE_HF_XET = _env_bool("ANY2MD_DISABLE_HF_XET", False)


def ensure_dirs() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
