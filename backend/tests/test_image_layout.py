"""图片 OCR 的坐标级版面重建测试。"""
from __future__ import annotations

import json
from pathlib import Path

from backend.app.image_layout import rebuild_image_markdown


def _text(index: int, x: int, y: int, text: str, *, height: int = 6) -> dict:
    return {
        "type": "text",
        "bbox": [x, y, 210, y + height],
        "index": index,
        "lines": [
            {
                "bbox": [x + 1, y, 209, y + height],
                "spans": [{"type": "text", "content": text}],
            }
        ],
    }


def _write_middle(tmp_path: Path) -> Path:
    """与用户“1a 信号毛刺”PNG 的真实 MinerU middle.json 同构。"""
    blocks = [
        {
            "type": "text",
            "bbox": [5, 5, 210, 26],
            "index": 1,
            "lines": [
                {
                    "bbox": [6, 5, 205, 17],
                    "spans": [
                        {
                            "type": "text",
                            "content": "1a信号毛刺：用-delay_trigger过滤零宽毛刺",
                        }
                    ],
                },
                {
                    "bbox": [6, 16, 209, 26],
                    "spans": [
                        {
                            "type": "text",
                            "content": "always块默认对零宽毛刺敏感，毛刺+组合环=仿真停摆",
                        }
                    ],
                },
            ],
        },
        _text(2, 5, 37, "机理：写进程先赋默认值再覆盖；即使值又改回原值，也足以唤醒等待的always块"),
        _text(3, 5, 45, "• 两个 always @(*)互相清零/置位对方，形成零延迟死循环："),
        {
            "type": "code",
            "bbox": [17, 55, 185, 69],
            "index": 4,
            "sub_type": "algorithm",
            "blocks": [
                {
                    "type": "code_body",
                    "lines": [
                        {
                            "spans": [
                                {
                                    "type": "text",
                                    "content": "always @(*) begin a = 1'b0; case (b) 1'b1 : a = 1'b1; endcase end",
                                }
                            ]
                        },
                        {
                            "spans": [
                                {
                                    "type": "text",
                                    "content": "always @(*) begin b = 1'b0; case (a) 1'b1 : b = 1'b1; endcase end",
                                }
                            ]
                        },
                    ],
                }
            ],
        },
        _text(5, 5, 70, "•解法：编译时加-delay trigger(xmvlog/xrun /ncvlog/irun 均支持)"),
        _text(6, 15, 77, "。仅当事件表达式中变量的值与块上次执行时不同才触发，过窄毛刺被滤除"),
        _text(7, 15, 84, "。详见 Verilog Compilation Command-Line Options 手册 2.18 节"),
        _text(8, 5, 94, "若该选项无效，说明循环另有原因，继续用后面的手段定位"),
    ]
    path = tmp_path / "slide_middle.json"
    path.write_text(
        json.dumps(
            {"pdf_info": [{"page_size": [228, 115], "para_blocks": blocks}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_rebuild_slide_image_preserves_visual_structure(tmp_path):
    middle = _write_middle(tmp_path)

    markdown = rebuild_image_markdown(middle)

    assert markdown is not None
    assert markdown.startswith(
        "## 1a 信号毛刺：用 -delay_trigger 过滤零宽毛刺\n\n"
        "### always 块默认对零宽毛刺敏感，毛刺 + 组合环 = 仿真停摆"
    )
    assert "- **机理：** 写进程先赋默认值再覆盖" in markdown
    assert "- 两个 always @(*) 互相清零/置位对方" in markdown
    assert "  ```verilog\n  always @(*) begin a = 1'b0;" in markdown
    assert "- **解法：** 编译时加 -delay_trigger (xmvlog / xrun / ncvlog / irun 均支持)" in markdown
    assert "  - 仅当事件表达式中变量的值与块上次执行时不同才触发" in markdown
    assert "  - 详见 Verilog Compilation Command-Line Options 手册 2.18 节" in markdown
    assert markdown.rstrip().endswith("- 若该选项无效，说明循环另有原因，继续用后面的手段定位")
    assert "•" not in markdown
    assert "。仅当" not in markdown


def test_image_converter_uses_middle_json_reconstruction(tmp_path, monkeypatch):
    from backend.app.converter import MinerUConverter

    monkeypatch.setattr(MinerUConverter, "_executable", lambda self: "mineru")

    def fake_run(cmd, **kwargs):
        out_dir = Path(cmd[cmd.index("--output") + 1])
        stem = Path(cmd[cmd.index("--path") + 1]).stem
        md_dir = out_dir / stem / "ocr"
        md_dir.mkdir(parents=True, exist_ok=True)
        (md_dir / f"{stem}.md").write_text(
            "1a信号毛刺：用-delay\\_trigger过滤零宽毛刺 always块默认对零宽毛刺敏感\n",
            encoding="utf-8",
        )
        middle = _write_middle(tmp_path)
        (md_dir / f"{stem}_middle.json").write_bytes(middle.read_bytes())

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Proc()

    monkeypatch.setattr("subprocess.run", fake_run)
    image = tmp_path / "slide.png"
    image.write_bytes(b"\x89PNG")

    result = MinerUConverter(backend="pipeline").convert(image, tmp_path / "out")
    markdown = result.markdown_path.read_text(encoding="utf-8")

    assert markdown.startswith("## 1a 信号毛刺：用 -delay_trigger 过滤零宽毛刺")
    assert "```verilog" in markdown
    assert "  - 仅当事件表达式" in markdown
