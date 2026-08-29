"""利用 MinerU middle.json 为技术截图重建 Markdown 版面。

MinerU 的最终 Markdown 会丢掉一部分已经识别出的结构信息；middle.json 仍保留
阅读顺序 index、代码块类型、逐行文字和 bbox。这里仅在结构信号足够明确的单页
技术截图上重建，复杂表格/图片/公式继续沿用 MinerU 原始 Markdown。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Optional

_BULLETS = "•·◦●○▪▫◆◇■□。．｡"
_BULLET_RE = re.compile(rf"^[\s{re.escape(_BULLETS)}]*([{re.escape(_BULLETS)}])\s*")
_CJK = r"\u3400-\u4dbf\u4e00-\u9fff"
_OPTION_RE = re.compile(r"(?<![A-Za-z0-9_])-[A-Za-z][A-Za-z0-9_-]*_[A-Za-z0-9_-]+")
_LABEL_RE = re.compile(rf"^([{_CJK}A-Za-z0-9]{{2,8}}：)(.+)$")
_ALLOWED_BLOCK_TYPES = {"text", "title", "code"}


def _spans_text(line: dict[str, Any]) -> str:
    return "".join(
        str(span.get("content", ""))
        for span in line.get("spans", [])
        if span.get("type") in {None, "text", "inline_equation", "interline_equation"}
    ).strip()


def _direct_lines(block: dict[str, Any]) -> list[dict[str, Any]]:
    return [line for line in block.get("lines", []) if _spans_text(line)]


def _nested_lines(block: dict[str, Any]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for child in block.get("blocks", []):
        lines.extend(_direct_lines(child))
        lines.extend(_nested_lines(child))
    return lines


def _block_lines(block: dict[str, Any]) -> list[dict[str, Any]]:
    lines = _direct_lines(block)
    return lines if lines else _nested_lines(block)


def _line_x(line: dict[str, Any], fallback: float) -> float:
    bbox = line.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        return float(bbox[0])
    return fallback


def _line_height(line: dict[str, Any]) -> float:
    bbox = line.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        return max(1.0, float(bbox[3]) - float(bbox[1]))
    return 1.0


def _block_x(block: dict[str, Any]) -> float:
    bbox = block.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        return float(bbox[0])
    return 0.0


def _block_y(block: dict[str, Any]) -> float:
    bbox = block.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        return float(bbox[1])
    return 0.0


def _sort_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """index 是 MinerU 的阅读顺序；缺失时才按纵坐标回退。"""
    return sorted(
        blocks,
        key=lambda block: (
            0 if isinstance(block.get("index"), int) else 1,
            block.get("index", _block_y(block)),
            _block_y(block),
        ),
    )


def _strip_bullet(text: str) -> tuple[str, bool]:
    match = _BULLET_RE.match(text)
    if not match:
        return text.strip(), False
    return text[match.end() :].strip(), True


def _option_glossary(texts: Iterable[str]) -> dict[str, str]:
    """用同页已正确识别的带下划线选项修复其他位置的空格误识别。"""
    glossary: dict[str, str] = {}
    for text in texts:
        for match in _OPTION_RE.finditer(text.replace("\\_", "_")):
            canonical = match.group(0)
            glossary[canonical.replace("_", " ")] = canonical
    return glossary


def _normalize_prose(text: str, glossary: dict[str, str]) -> str:
    text = text.replace("\\_", "_").strip()
    for wrong, canonical in sorted(glossary.items(), key=lambda item: -len(item[0])):
        text = text.replace(wrong, canonical)

    # 中英文/技术标记边界：OCR 常吞掉这些视觉空格。
    text = re.sub(rf"(?<=[{_CJK}])(?=[A-Za-z0-9@-])", " ", text)
    text = re.sub(rf"(?<=[A-Za-z0-9_*)])(?=[{_CJK}])", " ", text)
    text = re.sub(rf"(?<=[{_CJK}A-Za-z0-9_)])\s*([+=])\s*(?=[{_CJK}A-Za-z0-9(@-])", r" \1 ", text)
    text = re.sub(r"(-[A-Za-z][A-Za-z0-9_-]*)\s*\(", r"\1 (", text)
    text = re.sub(r"(?<=[A-Za-z0-9])\s*/\s*(?=[A-Za-z0-9])", " / ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _format_list_text(text: str) -> str:
    match = _LABEL_RE.match(text)
    if not match:
        return text
    return f"**{match.group(1)}** {match.group(2).lstrip()}"


def _looks_like_code(text: str) -> bool:
    return bool(
        re.search(
            r"(^\s*(?:always|module|endmodule|assign|begin|end|case|endcase)\b)"
            r"|(?:\b\d+'[bhd][0-9a-fxz]+\b)|(?:@\s*\()|(?:[;{}])"
            r"|(?:^(?:UNIX|xcelium|bash|cmd|PowerShell)>\s*)",
            text,
            re.IGNORECASE,
        )
    )


def _code_language(lines: list[str]) -> str:
    joined = "\n".join(lines)
    if re.search(r"\b(?:always|module|endmodule|assign|endcase)\b|\d+'[bhd]", joined):
        return "verilog"
    if re.search(r"^(?:UNIX|xcelium|bash|cmd|PowerShell)>", joined, re.MULTILINE):
        return "shell"
    return "text"


def _fenced_code(lines: list[str], level: int) -> str:
    indent = "  " * max(0, level)
    language = _code_language(lines)
    body = "\n".join(f"{indent}{line}" for line in lines)
    return f"{indent}```{language}\n{body}\n{indent}```"


def _heading_block(
    blocks: list[dict[str, Any]], page_height: float
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    if not blocks:
        return None, blocks
    first = blocks[0]
    if first.get("type") == "title":
        return first, blocks[1:]
    if first.get("type") != "text" or _block_y(first) > page_height * 0.15:
        return None, blocks

    first_lines = _block_lines(first)
    body_heights = [
        _line_height(line)
        for block in blocks[1:]
        if block.get("type") == "text"
        for line in _block_lines(block)
    ]
    if not first_lines or not body_heights:
        return None, blocks
    typical_body = median(body_heights)
    if median(_line_height(line) for line in first_lines) < typical_body * 1.35:
        return None, blocks
    return first, blocks[1:]


def _indent_context(
    blocks: list[dict[str, Any]], page_width: float
) -> tuple[float, float, bool]:
    entries: list[tuple[float, bool]] = []
    for block in blocks:
        if block.get("type") != "text":
            continue
        fallback = _block_x(block)
        for line in _block_lines(block):
            _, has_bullet = _strip_bullet(_spans_text(line))
            entries.append((_line_x(line, fallback), has_bullet))
    if not entries:
        return 0.0, max(4.0, page_width * 0.02), False

    baseline = min(x for x, _ in entries)
    threshold = max(4.0, page_width * 0.02)
    list_mode = any(has_bullet for _, has_bullet in entries)
    return baseline, threshold, list_mode


def _line_level(x: float, baseline: float, threshold: float) -> int:
    return 1 if x - baseline >= threshold else 0


def _render_text_block(
    block: dict[str, Any],
    *,
    baseline: float,
    threshold: float,
    list_mode: bool,
    glossary: dict[str, str],
) -> list[str]:
    lines = _block_lines(block)
    if not lines:
        return []

    rendered: list[str] = []
    fallback = _block_x(block)
    previous_level: Optional[int] = None
    for line in lines:
        raw = _spans_text(line)
        text, explicit_bullet = _strip_bullet(raw)
        text = _normalize_prose(text, glossary)
        if not text:
            continue
        level = _line_level(_line_x(line, fallback), baseline, threshold)

        if explicit_bullet or list_mode:
            # 同一文本块中同级的无符号后续行通常是自动换行；缩进增加则是子项。
            if (
                rendered
                and not explicit_bullet
                and previous_level == level
                and level == 0
            ):
                rendered[-1] += " " + text
            else:
                rendered.append(f"{'  ' * level}- {_format_list_text(text)}")
            previous_level = level
        else:
            rendered.append(text)
            previous_level = None
    return rendered


def _render_code_block(
    block: dict[str, Any],
    *,
    baseline: float,
    threshold: float,
    list_mode: bool,
    glossary: dict[str, str],
) -> list[str]:
    line_objs = _block_lines(block)
    if not line_objs:
        return []
    raw_lines = [_spans_text(line) for line in line_objs]
    fallback = _block_x(block)
    level = _line_level(fallback, baseline, threshold) if list_mode else 0

    # 有时 MinerU 把项目说明和命令行一起包进 code block；按行拆分后分别渲染。
    result: list[str] = []
    code_run: list[str] = []

    def flush_code() -> None:
        if code_run:
            result.append(_fenced_code(code_run.copy(), level))
            code_run.clear()

    for line_obj, raw in zip(line_objs, raw_lines):
        text, explicit_bullet = _strip_bullet(raw)
        if _looks_like_code(text):
            code_run.append(text)
            continue
        flush_code()
        prose = _normalize_prose(text, glossary)
        if not prose:
            continue
        prose_level = _line_level(
            _line_x(line_obj, fallback), baseline, threshold
        )
        if explicit_bullet or list_mode:
            result.append(f"{'  ' * prose_level}- {_format_list_text(prose)}")
        else:
            result.append(prose)
    flush_code()
    return result


def rebuild_image_markdown(middle_path: Path) -> Optional[str]:
    """从 MinerU middle.json 重建单页技术截图；不适用时返回 ``None``。"""
    try:
        data = json.loads(middle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None

    pages = data.get("pdf_info")
    if not isinstance(pages, list) or len(pages) != 1:
        return None
    page = pages[0]
    blocks = page.get("para_blocks")
    page_size = page.get("page_size")
    if not isinstance(blocks, list) or not blocks or not isinstance(page_size, list):
        return None
    if any(block.get("type") not in _ALLOWED_BLOCK_TYPES for block in blocks):
        return None
    # 只在代码型截图上启用；普通照片/表格/简历继续采用 MinerU 原 Markdown。
    if not any(block.get("type") == "code" for block in blocks):
        return None

    ordered = _sort_blocks(blocks)
    page_width = float(page_size[0]) if page_size else 1.0
    page_height = float(page_size[1]) if len(page_size) > 1 else 1.0
    heading, body = _heading_block(ordered, page_height)
    if heading is None:
        return None

    all_text = [
        _spans_text(line)
        for block in ordered
        for line in _block_lines(block)
    ]
    glossary = _option_glossary(all_text)
    baseline, threshold, list_mode = _indent_context(body, page_width)

    parts: list[str] = []
    heading_lines = _block_lines(heading)
    for index, line in enumerate(heading_lines):
        text = _normalize_prose(_spans_text(line), glossary)
        if text:
            level = min(6, int(heading.get("level", 2)) + index)
            parts.append(f"{'#' * level} {text}")

    for block in body:
        if block.get("type") == "code":
            items = _render_code_block(
                block,
                baseline=baseline,
                threshold=threshold,
                list_mode=list_mode,
                glossary=glossary,
            )
        elif block.get("type") == "title":
            items = [
                f"## {_normalize_prose(_spans_text(line), glossary)}"
                for line in _block_lines(block)
                if _spans_text(line)
            ]
        else:
            items = _render_text_block(
                block,
                baseline=baseline,
                threshold=threshold,
                list_mode=list_mode,
                glossary=glossary,
            )
        parts.extend(item for item in items if item)

    if len(parts) < 2:
        return None
    return "\n\n".join(parts).rstrip() + "\n"
