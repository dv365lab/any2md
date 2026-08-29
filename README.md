# any2md

一个**本地运行**的 PDF / Word / PowerPoint / 图片 → Markdown 转换 Web 应用。上传 PDF、Word、PPT 或
图片，尽量"原样"得到 Markdown：保留标题、段落、列表、**表格、图片、数学公式、代码**；PDF 支持**文字版与扫描版**、
**中英文**；不依赖任何云服务 / 大模型 API。

## 特性

- 🖥️ Web 界面：浏览器上传、**原文件与渲染结果并排预览**、下载 `.md` / `.zip`
- 📄 **PDF**：文字版 + 扫描版自动检测（扫描件走 OCR，可强制），公式 → LaTeX、表格 → HTML
- 🖼️ **图片（.jpg/.jpeg/.png/.webp/.bmp/.gif/.tif/.tiff）**：截图 / 拍照 / 扫描图当作单页扫描件，复用 MinerU 的 OCR + 版面识别管线，恒走 OCR；**含代码的技术截图会自动重建版面**（标题层级 / 代码块 / 列表缩进 / 中英文空格），公式 → LaTeX、表格 → HTML；纯本地，无需额外依赖
- 📝 **Word（.docx）**：用 [mammoth](https://github.com/mwilliamson/python-mammoth) 转 Markdown，自动抽取图片；纯 Python、无需模型/外部程序
- 📊 **PowerPoint（.pptx）**：用 [python-pptx](https://github.com/scanny/python-pptx) 转 Markdown，幻灯片标题 → 二级标题、正文缩进层级 → 列表、表格/图片原样保留，幻灯片间以 `---` 分隔；纯 Python、无需模型/外部程序
- 🔒 完全本地：不出网、不用 LLM/云
- ⚙️ PDF / 图片 转换引擎为 [MinerU](https://github.com/opendatalab/MinerU)，以子进程方式调用其 CLI；按文件扩展名自动路由引擎

## 快速开始

**版本约束**：Web 层任意 Python 3.10–3.14；**MinerU 引擎只支持 3.10–3.12**。

推荐用 [uv](https://docs.astral.sh/uv/)：

```text
uv venv --python 3.11
uv pip install -r requirements.txt
uv pip install -r requirements-engine.txt
```

或手动（cmd.exe）：

```text
py -3.11 -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
pip install -r requirements-engine.txt
```

启动：

```text
python run.py
```

打开 <http://127.0.0.1:8000>，上传 PDF → 开始转换。

> 注意：命令行末尾**不要**跟 `# 注释`（cmd 不识别 `#`，会把它当参数传给 pip）。

## 使用方法

### 1. 启动服务

```text
.\.venv\Scripts\python.exe run.py
```

浏览器打开 <http://127.0.0.1:8000>。

### 2. 上传文件

- **拖拽** PDF / Word / PPT / 图片 到虚线框，或**点击**虚线框选择文件；
- 也可以**复制文件后直接 `Ctrl+V` 粘贴**上传；粘贴剪贴板里的**截图 / 复制图片**同样生效（会自动补 `.png` 等扩展名）；
- 支持 **PDF**、**Word（.docx）**、**PowerPoint（.pptx）** 和 **图片（.jpg/.jpeg/.png/.webp/.bmp/.gif/.tif/.tiff）**，最大 100 MB（可用 `ANY2MD_MAX_UPLOAD_MB` 调整）;
- 按扩展名自动选择引擎：`.pdf` / 图片 → MinerU，`.docx` → mammoth，`.pptx` → python-pptx。

### 3. 选择转换选项

| 选项 | 说明 | 适用 |
|---|---|---|
| 识别语言 | 默认 `中文`；可选 English / 繁体中文 / 日本語 / 한국어 | PDF / 图片 |
| 强制 OCR | 扫描件 / 图片型 PDF 勾选；文字版保持默认（自动检测）即可（**图片输入恒走 OCR，此项对图片不生效**） | 仅 PDF |

> Word / PPT 是结构化文档，无需 OCR / 语言选项，这两项对 `.docx` / `.pptx` 不生效。
> 图片本身即"图像型"、无文字层，无论是否勾选强制 OCR 都会走 OCR；识别语言选项对图片有效。

### 4. 开始转换

点击 **开始转换**。

- **PDF / 图片 首次运行**需下载模型（1~2GB，见下节），之后转换通常几十秒到几分钟；
- **Word** 无需模型，通常几秒内完成。
- **PPT** 无需模型，通常几秒内完成。

进度条会实时显示状态。

### 5. 查看与下载结果

转换完成后，页面下方出现结果区：

- **PDF**：**左右并排**——左为原始 PDF（浏览器自带查看器），右为转换结果；
- **图片**：**左右并排**——左为原始图片（浏览器内联显示），右为转换结果；
- **Word / PPT**：浏览器无法内联预览 `.docx` / `.pptx`，自动切换为**单栏**，只显示转换结果。

结果区可在 `预览`（渲染后，含公式）/ `Markdown 源码` 两个标签页间切换。

下载：

- **下载 .md**：仅 Markdown 文件；
- **下载 .zip（含图片）**：Markdown + 抽取出的所有图片（图片在 `.md` 中以 `images/xxx` 相对路径引用，解压后可直接用）。

点击 **新转换** 清空当前任务，开始下一个。

### 6. 命令行方式（可选，不经 Web）

PDF：

```text
.\.venv\Scripts\mineru.exe --path <输入.pdf> --output <输出目录> --backend pipeline --lang ch
```

输出结构为 `<输出目录>/<文件名>/<method>/<文件名>.md` + `images/`。

图片（.jpg/.png/… 与 PDF 共用 MinerU，图片恒走 OCR）：

```text
.\.venv\Scripts\mineru.exe --path <输入.png> --output <输出目录> --backend pipeline --method ocr --lang ch
```

输出结构同 PDF：`<输出目录>/<文件名>/<method>/<文件名>.md` + `images/`。

Word（Python 内调用 mammoth）：

```text
.\.venv\Scripts\python.exe -c "import mammoth,sys; open(sys.argv[2],'w',encoding='utf-8').write(mammoth.convert_to_markdown(open(sys.argv[1],'rb')).value)" <输入.docx> <输出.md>
```

PPT（Python 内调用 python-pptx）：

```text
.\.venv\Scripts\python.exe -c "from pptx import Presentation; import sys,os; prs=Presentation(sys.argv[1]); md=''; slide_id=0; img_id=0;  \
  for slide in prs.slides: \
    if slide_id > 0: md += '---\n'; \
    for shape in slide.shapes: \
      if not shape.has_text_frame: continue; \
      for p in shape.text_frame.paragraphs: \
        if p.level == 0: md += '# ' + p.text + '\n'; \
        elif p.level == 1: md += '## ' + p.text + '\n'; \
        elif p.level == 2: md += '- ' + p.text + '\n'; \
    for shape in slide.shapes: \
      if not shape.has_image: continue; \
      img = shape.image; ext = img.ext; img_id += 1; fn = f'img{slide_id:03d}_{img_id:03d}.{ext}'; \
      with open(os.path.join(sys.argv[2],fn),'wb') as f: f.write(img.blob); md += f'![](./{fn})\n'; \
  open(sys.argv[2]+'/slide001.md','w',encoding='utf-8').write(md)" <输入.pptx> <输出目录>
```

### 常见问题

- **提示 "MinerU is not installed"**：PDF 引擎未装或不在 PATH。用
  `.\.venv\Scripts\python.exe -m pip install -r requirements-engine.txt` 安装；
  或设 `ANY2MD_MINERU_EXE` 指向 `mineru.exe`。
- **Word 转换失败 / 提示 mammoth 未装**：用
  `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` 安装 Web 层依赖。
- **老式 `.doc` / `.ppt`（非 `.docx` / `.pptx`）**：mammoth / python-pptx 不支持 OLE2 二进制格式，请先在 Word / PowerPoint 中**另存为 `.docx` / `.pptx`** 再转换。
- **首次转换卡在下载 / 报 SSL 错误**：模型权重主机被网络封锁，见下节"模型下载"。
- **改了代码不生效**：`run.py` 用 `reload=False`，需**重启进程**。
- **扫描件识别不全**：勾选"强制 OCR"重试；复杂手写 / 多栏排版尽力而为，可在并排预览中核对修正。

## 图片转换详解（结构化重建）

### 背景：OCR 的格式误差

图片是纯像素，MinerU 需要先"看图识字"再识别版面。对于文字密集、含代码的技术截图，
MinerU 其实已经在内部中间文件（`*_middle.json`）中识别出了标题、代码块、列表层级和每个文本块的
坐标，但生成最终 Markdown 时往往会丢掉这些结构信息，导致：

- 标题与副标题被合并成一行；
- 代码块（如 Verilog / Shell 命令）退化成普通段落；
- 列表的缩进层级丢失，子项与主项平级；
- 项目符号被 OCR 误识别成句号 `。` 等；
- 中英文边界空格、`-delay_trigger` 等带下划线选项的空格丢失。

### 做了什么：基于坐标重建版面

针对上述问题，any2md 在图片转换时新增了**坐标级版面重建**（`backend/app/image_layout.py`）：

- 按 MinerU 给出的阅读顺序 `index` 排序，避免段落错位；
- 依据逐行内容与行高，把标题与副标题拆回 `##` / `###`；
- 依据文本块的横向坐标（bbox 左边界），恢复主列表 / 子列表的缩进层级；
- 依据 `type=code` 直接生成 fenced code block（三个反引号围栏），并自动标注 `verilog` / `shell` 等语言；
- 把 `机理：`、`解法：` 这类引导标签加粗；
- 用同一页中识别正确的词汇，修复 `-delay trigger` → `-delay_trigger` 等空格误识别；
- 恢复中英文、数学符号之间的边界空格；
- 把 Unicode 项目符号（`•` / `·` / `。` 等）统一为 Markdown 标准列表 `- `。

### 触发条件（哪些图片会重建）

只有**同时满足**以下条件的单页技术截图才会触发重建，其余情况回退到 MinerU 原始输出，
避免误伤表格 / 照片 / 简历等版面：

1. 只有一页；
2. 所有内容块类型都是 `text` / `title` / `code`（即不含表格、图片、公式块）；
3. 至少含一个代码块；
4. 能识别出标题（首块是 title，或首块行高显著大于正文）。

> 换句话说：含代码的、文字型的技术文档截图会自动获得更好的结构；普通照片、带表格的
> 截图、简历等仍走 MinerU 原有流程，行为不变。

### 使用建议（怎么得到最好结果）

- **首选：直接用源文件。** 截图若来自 PPT / PDF，直接把 `.pptx` / `.pdf` 拖进来——结构化
  提取零 OCR 误差，标题 / 列表 / 表格 / 图片全部原样保留，效果远好于任何截图。
- **代码密集型截图**：本功能专为它优化——含 Verilog / Shell 命令的截图会自动得到
  代码块和正确的列表层级。
- **截图时尽量清晰**：用高分辨率、大字号截图，避免压缩过度的图，能显著降低 OCR 误差。
- **识别语言**：中文为主选 `中文`，英文为主选 `English`；图片恒走 OCR，无需勾选"强制 OCR"。
- **查看与微调**：转换结果在右侧预览，可切换到 `Markdown 源码` 标签页查看原始 Markdown，
  对个别识别不准的字符按需微调。

## 模型下载（首次）

首次转换需下载 1~2GB 模型权重，之后缓存到 `%USERPROFILE%\.cache\huggingface` 即可离线使用。
受限网络下：

1. 换不受限网络（如手机热点）跑一次转换预热模型；
2. 或从别的机器拷贝 `~/.cache/huggingface` 到本机同路径；
3. 或让 IT 放行 `us.aws.cdn.hf.co` / `modelscope.cn`，或设 `HTTPS_PROXY`。

企业 TLS 拦截环境记得装 `pip-system-certs`（已在 `requirements-engine.txt`）。

## 配置（环境变量）

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `ANY2MD_MINERU_BACKEND` | `pipeline` | MinerU 后端，`pipeline` 纯 CPU |
| `ANY2MD_MINERU_DEVICE` | 自动 | torch 设备提示，如 `cpu`/`cuda` |
| `ANY2MD_DEFAULT_LANG` | `ch` | 默认 OCR 语言 |
| `ANY2MD_MINERU_TIMEOUT` | `1800` | 单文件转换超时（秒） |
| `ANY2MD_MAX_UPLOAD_MB` | `100` | 上传大小上限 |
| `ANY2MD_STORAGE` | `./storage` | 上传与输出目录 |
| `ANY2MD_MINERU_EXE` | 自动探测 | mineru 可执行文件路径覆盖 |
| `MINERU_MODEL_SOURCE` | `huggingface` | 模型下载源：`huggingface`/`modelscope` |
| `ANY2MD_DISABLE_HF_XET` | `0` | 置 `1` 关闭 HF Xet 下载 |

## 项目结构

```text
any2md/
├─ backend/
│  ├─ app/
│  │  ├─ config.py      # 配置与路径（环境变量可覆盖）
│  │  ├─ models.py      # Pydantic 请求/响应模型
│  │  ├─ converter.py   # Converter 抽象 + MinerUConverter(PDF/图片,子进程) + WordConverter(docx,mammoth) + PptxConverter(pptx,python-pptx) + 按扩展名路由
│  │  ├─ image_layout.py # 图片 OCR 结果的坐标级版面重建（标题/代码块/列表层级/空格）
│  │  ├─ jobs.py        # JobManager（线程池 + 内存任务表，按文件名路由引擎）
│  │  ├─ api.py         # /api 路由
│  │  └─ main.py        # FastAPI 应用入口 + 托管前端
│  └─ tests/
│     ├─ test_smoke.py        # 不依赖引擎的冒烟测试
│     └─ test_image_layout.py # 图片版面重建测试
├─ frontend/            # 原生 HTML/JS/CSS（marked + KaTeX 走 CDN）
├─ storage/             # 运行时生成（gitignore）：uploads/ outputs/
├─ run.py               # 便捷启动器
├─ requirements.txt         # Web 层（轻量）
├─ requirements-engine.txt  # MinerU 引擎（重，3.10–3.12）
└─ requirements-dev.txt     # 测试依赖
```

## 测试

测试不需要 MinerU 引擎和模型（用假转换器跑通完整流程）：

- `test_smoke.py`：冒烟测试——上传 / 状态 / 结果 / 下载 / 引擎路由 / 魔数校验等完整流程；
- `test_image_layout.py`：图片 OCR 结果的版面重建——标题层级、代码块、列表缩进、术语与空格修复。

```text
pip install -r requirements-dev.txt
pytest
```

## API 一览

| 方法/路径 | 作用 |
|---|---|
| `POST /api/convert` | multipart 上传 PDF/Word/PPT/图片（按扩展名路由引擎），返回 `job_id` |
| `GET /api/status/{id}` | 轮询 `status/progress/message` |
| `GET /api/result/{id}` | Markdown（图片链接已改写）+ 图片列表 |
| `GET /api/source/{id}` | 原始文件（PDF / 图片供浏览器内联预览；Word/PPT 返回对应 media type） |
| `GET /api/files/{id}/{path}` | 抽取出的图片（路径穿越防护） |
| `GET /api/download/{id}?format=md\|zip` | 下载 `.md` 或含图片的 `.zip` |
