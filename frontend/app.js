"use strict";

const $ = (sel) => document.querySelector(sel);

const dropzone = $("#dropzone");
const fileInput = $("#file-input");
const fileName = $("#file-name");
const langSel = $("#lang");
const forceOcr = $("#force-ocr");
const convertBtn = $("#convert-btn");
const progressWrap = $("#progress-wrap");
const progressBar = $("#progress-bar");
const statusText = $("#status-text");
const errorText = $("#error-text");
const resultCard = $("#result-card");
const pdfFrame = $("#pdf-frame");
const imgFrame = $("#img-frame");
const imgPreview = $("#img-preview");
const mdRendered = $("#md-rendered");
const mdSource = $("#md-source");
const tabPreview = $("#tab-preview");
const tabSource = $("#tab-source");
const downloadMd = $("#download-md");
const downloadZip = $("#download-zip");
const resetBtn = $("#reset-btn");

const POLL_INTERVAL = 1200;

let selectedFile = null;
let currentJobId = null;
let pollTimer = null;

/* ---------- 文件选择（点击 / 拖拽 / 粘贴） ---------- */
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) setFile(fileInput.files[0]);
});
["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files && e.dataTransfer.files[0];
  if (f) setFile(f);
});

/* 复制文件后 Ctrl+V 粘贴上传；也支持粘贴剪贴板里的截图 / 复制图片 */
window.addEventListener("paste", (e) => {
  const cd = e.clipboardData;
  if (!cd) return;
  // 1) 剪贴板里有真实文件（在资源管理器复制的文件），优先取带文件名的
  if (cd.files && cd.files.length) {
    const f = cd.files[0];
    if (f.name) {
      e.preventDefault();
      setFile(f);
      return;
    }
  }
  // 2) 剪贴板里是图片（截图 / 复制图片），getAsFile() 无名，补上扩展名
  for (const item of cd.items || []) {
    if (item.kind === "file" && item.type.startsWith("image/")) {
      const f = item.getAsFile();
      if (f) {
        e.preventDefault();
        const ext = (item.type.split("/")[1] || "png").replace("jpeg", "jpg");
        setFile(new File([f], `pasted-image.${ext}`, { type: item.type }));
        return;
      }
    }
  }
});

function setFile(file) {
  const ok = /\.(pdf|docx|doc|pptx|ppt|jpg|jpeg|png|webp|bmp|gif|tif|tiff)$/i.test(file.name);
  if (!ok) {
    showError("只支持 PDF、Word（.docx/.doc）、PowerPoint（.pptx/.ppt）或图片（.jpg/.png/.webp/.bmp/.gif/.tiff）文件");
    return;
  }
  selectedFile = file;
  fileName.textContent = `${file.name}（${(file.size / 1024 / 1024).toFixed(2)} MB）`;
  convertBtn.disabled = false;
  hideError();
}

/* ---------- 转换 ---------- */
convertBtn.addEventListener("click", () => {
  if (selectedFile) startConversion(selectedFile);
});

async function startConversion(file) {
  hideError();
  resultCard.hidden = true;
  setProgress(2, "上传中…");
  convertBtn.disabled = true;

  const fd = new FormData();
  fd.append("file", file);
  fd.append("lang", langSel.value);
  fd.append("force_ocr", forceOcr.checked ? "true" : "false");

  try {
    const res = await fetch("/api/convert", { method: "POST", body: fd });
    if (!res.ok) throw new Error(await readError(res));
    const { job_id } = await res.json();
    currentJobId = job_id;
    setProgress(5, "任务已创建，排队中…");
    schedulePoll();
  } catch (err) {
    showError(err.message || "上传失败");
    progressWrap.hidden = true;
    convertBtn.disabled = false;
  }
}

function schedulePoll() {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(pollStatus, POLL_INTERVAL);
}

async function pollStatus() {
  if (!currentJobId) return;
  try {
    const res = await fetch(`/api/status/${currentJobId}`);
    if (!res.ok) throw new Error(await readError(res));
    const s = await res.json();

    if (s.status === "done") {
      setProgress(100, "转换完成");
      await loadResult();
      return;
    }
    if (s.status === "error") {
      showError(s.message || "转换失败");
      progressWrap.hidden = true;
      convertBtn.disabled = false;
      return;
    }
    setProgress(
      Math.max(s.progress, 10),
      s.message || "转换中…（首次运行需下载模型，可能较慢）"
    );
    schedulePoll();
  } catch (err) {
    showError(err.message || "状态查询失败");
    convertBtn.disabled = false;
  }
}

async function loadResult() {
  try {
    const res = await fetch(`/api/result/${currentJobId}`);
    if (!res.ok) throw new Error(await readError(res));
    const data = await res.json();

    mdSource.textContent = data.markdown;
    mdRendered.innerHTML = marked.parse(data.markdown);
    if (window.renderMathInElement) {
      renderMathInElement(mdRendered, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "\\[", right: "\\]", display: true },
          { left: "$", right: "$", display: false },
          { left: "\\(", right: "\\)", display: false },
        ],
        throwOnError: false,
      });
    }

    // PDF / 图片 可浏览器内联预览（左右并排）；Word/PPT 无法内联，隐藏左栏改单栏
    const pdf = isPdf(data.filename);
    const img = isImage(data.filename);
    const previewable = pdf || img;
    if (pdf) {
      pdfFrame.src = `/api/source/${currentJobId}`;
    } else {
      pdfFrame.src = "about:blank";
    }
    if (img) {
      imgPreview.src = `/api/source/${currentJobId}`;
    } else {
      imgPreview.removeAttribute("src");
    }
    pdfFrame.hidden = !pdf;
    imgFrame.hidden = !img;
    document.querySelector(".split").classList.toggle("single", !previewable);
    downloadMd.href = `/api/download/${currentJobId}?format=md`;
    downloadZip.href = `/api/download/${currentJobId}?format=zip`;

    resultCard.hidden = false;
    showTab("preview");
    resultCard.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showError(err.message || "结果加载失败");
  } finally {
    convertBtn.disabled = false;
  }
}

/* ---------- 预览 / 源码 切换 ---------- */
tabPreview.addEventListener("click", () => showTab("preview"));
tabSource.addEventListener("click", () => showTab("source"));

function showTab(which) {
  const preview = which === "preview";
  mdRendered.hidden = !preview;
  mdSource.hidden = preview;
  tabPreview.classList.toggle("active", preview);
  tabSource.classList.toggle("active", !preview);
}

/* ---------- 新转换 ---------- */
resetBtn.addEventListener("click", () => {
  clearTimeout(pollTimer);
  currentJobId = null;
  selectedFile = null;
  fileInput.value = "";
  fileName.textContent = "支持 PDF、Word、PowerPoint、图片，最大 100 MB";
  convertBtn.disabled = true;
  resultCard.hidden = true;
  progressWrap.hidden = true;
  pdfFrame.src = "about:blank";
  pdfFrame.hidden = false;
  imgPreview.removeAttribute("src");
  imgFrame.hidden = true;
  document.querySelector(".split").classList.remove("single");
  hideError();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

/* ---------- 工具 ---------- */
function setProgress(pct, text) {
  progressWrap.hidden = false;
  progressBar.style.width = `${pct}%`;
  statusText.textContent = text || "";
}

function showError(msg) {
  errorText.textContent = msg;
  errorText.hidden = false;
}

function hideError() {
  errorText.hidden = true;
  errorText.textContent = "";
}

async function readError(res) {
  try {
    const body = await res.json();
    return body.detail || `HTTP ${res.status}`;
  } catch {
    return `HTTP ${res.status}`;
  }
}

function isPdf(name) {
  return /\.pdf$/i.test(name);
}

function isImage(name) {
  return /\.(jpg|jpeg|png|webp|bmp|gif|tif|tiff)$/i.test(name);
}
