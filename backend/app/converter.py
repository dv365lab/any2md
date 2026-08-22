"""转换引擎抽象 + MinerU 子进程实现（核心）。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config


class ConversionError(RuntimeError):
    """转换失败：引擎缺失 / 启动失败 / 超时 / 非零退出码 / 无输出。"""


@dataclass
class ConversionResult:
    markdown_path: Path
    images_dir: Optional[Path]
    output_dir: Path


class Converter(ABC):
    """转换引擎抽象，便于未来替换为进程内 API 或其他引擎。"""

    @abstractmethod
    def convert(
        self,
        pdf_path: Path,
        output_dir: Path,
        *,
        lang: str = "ch",
        force_ocr: bool = False,
    ) -> ConversionResult:
        ...


class MinerUConverter(Converter):
    """以子进程方式调用 mineru CLI，把庞大的模型内存/崩溃与 Web 进程隔离。"""

    def __init__(
        self,
        backend: Optional[str] = None,
        timeout: Optional[int] = None,
        model_source: Optional[str] = None,
        disable_hf_xet: Optional[bool] = None,
        device: Optional[str] = None,
    ) -> None:
        self.backend = backend or config.MINERU_BACKEND
        self.timeout = config.MINERU_TIMEOUT if timeout is None else timeout
        self.model_source = config.MODEL_SOURCE if model_source is None else model_source
        self.disable_hf_xet = config.DISABLE_HF_XET if disable_hf_xet is None else disable_hf_xet
        self.device = config.MINERU_DEVICE if device is None else device

    def _executable(self) -> str:
        """定位 mineru 可执行文件。

        兼顾“未激活虚拟环境直接跑 .venv\\Scripts\\python.exe run.py”的场景：
        此时 .venv\\Scripts 不在 PATH 上，回退到当前解释器同目录查找。
        """
        override = os.environ.get("ANY2MD_MINERU_EXE")
        if override and Path(override).is_file():
            return override
        exe = shutil.which("mineru")
        if exe:
            return exe
        name = "mineru.exe" if os.name == "nt" else "mineru"
        candidate = Path(sys.executable).parent / name
        if candidate.is_file():
            return str(candidate)
        raise ConversionError(
            "MinerU is not installed. Install the engine with: "
            'pip install -U "mineru[core]" (requires Python 3.10-3.12), '
            "or point ANY2MD_MINERU_EXE at the mineru executable."
        )

    def convert(
        self,
        pdf_path: Path,
        output_dir: Path,
        *,
        lang: str = "ch",
        force_ocr: bool = False,
    ) -> ConversionResult:
        exe = self._executable()
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [exe, "--path", str(pdf_path), "--output", str(output_dir), "--backend", self.backend]
        if self.backend == "pipeline":
            cmd += ["--method", "ocr" if force_ocr else "auto"]
            if lang and lang != "auto":
                cmd += ["--lang", lang]

        env = os.environ.copy()
        if self.model_source:
            env["MINERU_MODEL_SOURCE"] = self.model_source
        if self.disable_hf_xet:
            env["HF_HUB_DISABLE_XET"] = "1"
        if self.device:
            env["MINERU_DEVICE_MODE"] = self.device

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout, env=env
            )
        except subprocess.TimeoutExpired:
            raise ConversionError(
                f"Conversion timed out after {self.timeout} seconds"
            ) from None
        except OSError as exc:
            raise ConversionError(f"Failed to launch mineru: {exc}") from exc

        if proc.returncode != 0:
            tail = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()[-2000:]
            raise ConversionError(f"mineru exited with code {proc.returncode}: {tail}")

        md = self._find_markdown(output_dir, pdf_path.stem)
        if md is None:
            raise ConversionError("mineru finished but produced no markdown output")
        images_dir = md.parent / "images"
        return ConversionResult(
            markdown_path=md,
            images_dir=images_dir if images_dir.is_dir() else None,
            output_dir=output_dir,
        )

    @staticmethod
    def _find_markdown(output_dir: Path, stem: str) -> Optional[Path]:
        """MinerU 输出结构为 output/<stem>/<method>/<stem>.md + images/。

        优先匹配同名 stem，否则取体积最大的 .md。
        """
        candidates = sorted(output_dir.rglob("*.md"))
        if not candidates:
            return None
        for c in candidates:
            if c.stem == stem:
                return c
        return max(candidates, key=lambda p: p.stat().st_size)


class WordConverter(Converter):
    """Word(.docx) → Markdown，用 mammoth（纯 Python，无需模型/外部程序）。

    .docx 是结构化 XML，不需要 OCR/模型；抽取图片到 images/ 并把
    Markdown 中的图片引用改写为相对路径 images/<name>。
    """

    def convert(
        self,
        pdf_path: Path,  # 实为 .docx 路径（沿用抽象接口的参数名）
        output_dir: Path,
        *,
        lang: str = "ch",
        force_ocr: bool = False,
    ) -> ConversionResult:
        try:
            import mammoth
        except ImportError:
            raise ConversionError(
                "mammoth is not installed. Install it with: pip install mammoth"
            ) from None

        output_dir.mkdir(parents=True, exist_ok=True)
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        counter = {"n": 0}

        def _save_image(image):
            """把内嵌图片落盘到 images/，并返回 Markdown 引用的相对路径。"""
            counter["n"] += 1
            ext = (image.content_type or "image/png").split("/")[-1].replace("jpeg", "jpg")
            name = f"img{counter['n']}.{ext}"
            with image.open() as f:
                (images_dir / name).write_bytes(f.read())
            return {"src": f"images/{name}"}

        try:
            with open(pdf_path, "rb") as f:
                result = mammoth.convert_to_markdown(
                    f, convert_image=mammoth.images.img_element(_save_image)
                )
        except Exception as exc:
            raise ConversionError(f"Word conversion failed: {exc}") from exc

        markdown = result.value
        md_path = output_dir / f"{pdf_path.stem}.md"
        md_path.write_text(markdown, encoding="utf-8")

        has_images = any(images_dir.iterdir())
        return ConversionResult(
            markdown_path=md_path,
            images_dir=images_dir if has_images else None,
            output_dir=output_dir,
        )


class PptxConverter(Converter):
    """PowerPoint(.pptx) → Markdown，用 python-pptx（纯 Python，无需模型/外部程序）。

    每张幻灯片：标题占位符 → `## `，副标题占位符 → `### `；正文按段落缩进
    层级 → Markdown 列表（level=0 且未显式带符号的引导句保持为普通段落）；
    表格 → Markdown 表格；图片抽取到 images/ 并引用相对路径 images/<name>；
    幻灯片之间以 `---` 分隔。老式 .ppt（OLE2 二进制）不受支持，给出明确报错。
    """

    def convert(
        self,
        pdf_path: Path,  # 实为 .pptx 路径（沿用抽象接口的参数名）
        output_dir: Path,
        *,
        lang: str = "ch",
        force_ocr: bool = False,
    ) -> ConversionResult:
        if pdf_path.suffix.lower() == ".ppt":
            raise ConversionError(
                "Legacy .ppt (OLE2 binary) is not supported. "
                "Please open it in PowerPoint and save as .pptx, then retry."
            )
        try:
            from pptx import Presentation
        except ImportError:
            raise ConversionError(
                "python-pptx is not installed. Install it with: pip install python-pptx"
            ) from None

        output_dir.mkdir(parents=True, exist_ok=True)
        images_dir = output_dir / "images"
        counter = {"n": 0}

        def _save_image(image) -> str:
            """把幻灯片中的图片落盘到 images/，返回 Markdown 引用的相对路径。"""
            counter["n"] += 1
            name = f"img{counter['n']}.{image.ext}"
            images_dir.mkdir(parents=True, exist_ok=True)
            (images_dir / name).write_bytes(image.blob)
            return f"images/{name}"

        try:
            prs = Presentation(str(pdf_path))
        except Exception as exc:
            raise ConversionError(f"PowerPoint conversion failed: {exc}") from exc

        parts: list[str] = []
        deck_title = (prs.core_properties.title or "").strip()
        if deck_title:
            parts.append(f"# {deck_title}")

        for slide in prs.slides:
            block = self._slide_to_markdown(slide, _save_image)
            if block:
                parts.append(block)

        markdown = "\n\n---\n\n".join(parts).strip() + "\n"
        md_path = output_dir / f"{pdf_path.stem}.md"
        md_path.write_text(markdown, encoding="utf-8")

        has_images = images_dir.is_dir() and any(images_dir.iterdir())
        return ConversionResult(
            markdown_path=md_path,
            images_dir=images_dir if has_images else None,
            output_dir=output_dir,
        )

    @classmethod
    def _slide_to_markdown(cls, slide, save_image) -> str:
        """单张幻灯片 → Markdown 片段：标题 + 副标题 + 正文/表格/图片。"""
        from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER

        lines: list[str] = []
        title_shape = slide.shapes.title
        handled_ids: set[int] = set()
        if title_shape is not None and title_shape.has_text_frame:
            title = " ".join(title_shape.text_frame.text.split())
            if title:
                lines += [f"## {title}", ""]
                handled_ids.add(title_shape.shape_id)

        for shape in cls._iter_shapes(slide.shapes):
            if shape.shape_id in handled_ids:
                continue  # 已处理
            if getattr(shape, "has_table", False) and shape.has_table:
                lines += cls._table_to_markdown(shape.table)
            elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    src = save_image(shape.image)
                except Exception:
                    continue  # 链接式图片等无法读取时跳过
                lines += ["", f"![{shape.name}]({src})", ""]
            elif shape.has_text_frame:
                if cls._is_subtitle(shape):
                    sub = " ".join(shape.text_frame.text.split())
                    if sub:
                        lines += [f"### {sub}", ""]
                else:
                    lines += cls._text_frame_to_markdown(shape)

        # 去掉首尾空行，压缩连续空行
        out: list[str] = []
        for line in lines:
            if line == "" and (not out or out[-1] == ""):
                continue
            out.append(line)
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out)

    @staticmethod
    def _iter_shapes(shapes):
        """递归展开组合形状（group），按文档顺序产出所有叶子形状。"""
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        for shape in shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                yield from PptxConverter._iter_shapes(shape.shapes)
            else:
                yield shape

    @classmethod
    def _text_frame_to_markdown(cls, shape) -> list[str]:
        """文本框/正文占位符 → 列表或普通段落，保留缩进层级。

        正文占位符的段落默认带项目符号（继承占位符样式）；显式设置
        buNone（无符号）的段落输出为普通段落。
        """
        lines: list[str] = []
        default_bullet = cls._is_body_placeholder(shape)
        for para in shape.text_frame.paragraphs:
            text = " ".join(para.text.replace("\v", " ").split())
            if not text:
                continue
            kind = cls._bullet_kind(para, default_bullet)
            indent = "  " * para.level
            if kind == "number":
                lines.append(f"{indent}1. {text}")
            elif kind == "bullet":
                lines.append(f"{indent}- {text}")
            else:
                lines += ["", text, ""]
        return lines

    @staticmethod
    def _is_subtitle(shape) -> bool:
        """是否为副标题占位符。"""
        from pptx.enum.shapes import PP_PLACEHOLDER

        if not shape.is_placeholder:
            return False
        return shape.placeholder_format.type == PP_PLACEHOLDER.SUBTITLE

    @staticmethod
    def _is_body_placeholder(shape) -> bool:
        """正文类占位符的段落默认带项目符号；标题/副标题/文本框默认不带。"""
        from pptx.enum.shapes import PP_PLACEHOLDER

        if not shape.is_placeholder:
            return False
        ph_type = shape.placeholder_format.type
        return ph_type not in (
            PP_PLACEHOLDER.TITLE,
            PP_PLACEHOLDER.CENTER_TITLE,
            PP_PLACEHOLDER.SUBTITLE,
        )

    @staticmethod
    def _bullet_kind(para, default_bullet: bool) -> Optional[str]:
        """判断段落列表类型：'bullet' | 'number' | None（普通段落）。

        段落未显式设置时继承占位符默认：正文占位符默认项目符号。
        """
        from pptx.oxml.ns import qn

        pPr = para._p.find(qn("a:pPr"))
        if pPr is not None:
            if pPr.find(qn("a:buNone")) is not None:
                return None
            if pPr.find(qn("a:buAutoNum")) is not None:
                return "number"
            if pPr.find(qn("a:buChar")) is not None:
                return "bullet"
        return "bullet" if default_bullet else None

    @staticmethod
    def _table_to_markdown(table) -> list[str]:
        """幻灯片表格 → Markdown 表格，首行作表头。"""

        def _cell(text: str) -> str:
            return " ".join(text.split()).replace("|", "\\|")

        rows = [[_cell(c.text) for c in row.cells] for row in table.rows]
        if not rows:
            return []
        lines = ["", "| " + " | ".join(rows[0]) + " |"]
        lines.append("|" + "|".join(["---"] * len(rows[0])) + "|")
        for row in rows[1:]:
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
        return lines


def get_converter_for(filename: str) -> Converter:
    """按文件扩展名路由到对应转换器。"""
    ext = Path(filename).suffix.lower()
    if ext in {".docx", ".doc"}:
        return WordConverter()
    if ext in {".pptx", ".ppt"}:
        return PptxConverter()
    return MinerUConverter()
