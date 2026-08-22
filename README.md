# any2md

一个**本地运行**的 PDF / Word / PowerPoint → Markdown 转换 Web 应用。上传 PDF、Word 或 PPT，尽量"原样"得到 Markdown：
保留标题、段落、列表、**表格、图片、数学公式、代码**；PDF 支持**文字版与扫描版**、
**中英文**；不依赖任何云服务 / 大模型 API。

## 特性

- 🖥️ Web 界面：浏览器上传、**原文件与渲染结果并排预览**、下载 `.md` / `.zip`
- 📄 **PDF**：文字版 + 扫描版自动检测（扫描件走 OCR，可强制），公式 → LaTeX、表格 → HTML
- 📝 **Word（.docx）**：用 [mammoth](https://github.com/mwilliamson/python-mammoth) 转 Markdown，自动抽取图片；纯 Python、无需模型/外部程序
- 📊 **PowerPoint（.pptx）**：用 [python-pptx](https://github.com/scanny/python-pptx) 转 Markdown，幻灯片标题 → 二级标题、正文缩进层级 → 列表、表格/图片原样保留，幻灯片间以 `---` 分隔；纯 Python、无需模型/外部程序
- 🔒 完全本地：不出网、不用 LLM/云
- ⚙️ PDF 转换引擎为 [MinerU](https://github.com/opendatalab/MinerU)，以子进程方式调用其 CLI；按文件扩展名自动路由引擎

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

- **拖拽** PDF / Word / PPT 到虚线框，或**点击**虚线框选择文件；
- 支持 **PDF**、**Word（.docx）** 和 **PowerPoint（.pptx）**，最大 100 MB（可用 `ANY2MD_MAX_UPLOAD_MB` 调整）;
- 按扩展名自动选择引擎：`.pdf` → MinerU，`.docx` → mammoth，`.pptx` → python-pptx。

### 3. 选择转换选项

| 选项 | 说明 | 适用 |
|---|---|---|
| 识别语言 | 默认 `中文`；可选 English / 繁体中文 / 日本語 / 한국어 | 仅 PDF |
| 强制 OCR | 扫描件 / 图片型 PDF 勾选；文字版保持默认（自动检测）即可 | 仅 PDF |

> Word / PPT 是结构化文档，无需 OCR / 语言选项，这两项对 `.docx` / `.pptx` 不生效。

### 4. 开始转换

点击 **开始转换**。

- **PDF 首次运行**需下载模型（1~2GB，见下节），之后转换通常几十秒到几分钟；
- **Word** 无需模型，通常几秒内完成。
- **PPT** 无需模型，通常几秒内完成。

进度条会实时显示状态。

### 5. 查看与下载结果

转换完成后，页面下方出现结果区：

- **PDF**：**左右并排**——左为原始 PDF（浏览器自带查看器），右为转换结果；
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
│  │  ├─ converter.py   # Converter 抽象 + MinerUConverter(PDF,子进程) + WordConverter(docx,mammoth) + PptxConverter(pptx,python-pptx) + 按扩展名路由
│  │  ├─ jobs.py        # JobManager（线程池 + 内存任务表，按文件名路由引擎）
│  │  ├─ api.py         # /api 路由
│  │  └─ main.py        # FastAPI 应用入口 + 托管前端
│  └─ tests/
│     └─ test_smoke.py  # 不依赖引擎的冒烟测试
├─ frontend/            # 原生 HTML/JS/CSS（marked + KaTeX 走 CDN）
├─ storage/             # 运行时生成（gitignore）：uploads/ outputs/
├─ run.py               # 便捷启动器
├─ requirements.txt         # Web 层（轻量）
├─ requirements-engine.txt  # MinerU 引擎（重，3.10–3.12）
└─ requirements-dev.txt     # 测试依赖
```

## 测试

冒烟测试（不需要引擎和模型，用假转换器跑通完整流程）：

```text
pip install -r requirements-dev.txt
pytest
```

## API 一览

| 方法/路径 | 作用 |
|---|---|
| `POST /api/convert` | multipart 上传 PDF/Word/PPT（按扩展名路由引擎），返回 `job_id` |
| `GET /api/status/{id}` | 轮询 `status/progress/message` |
| `GET /api/result/{id}` | Markdown（图片链接已改写）+ 图片列表 |
| `GET /api/source/{id}` | 原始文件（PDF 供 iframe 预览；Word/PPT 返回对应 media type） |
| `GET /api/files/{id}/{path}` | 抽取出的图片（路径穿越防护） |
| `GET /api/download/{id}?format=md\|zip` | 下载 `.md` 或含图片的 `.zip` |
