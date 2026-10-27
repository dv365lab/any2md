"""一键启动器（被 start-any2md.bat 调用）。

逻辑：
1. 若已有 any2md 在跑（先看 storage/server.port，再扫一段端口），直接开浏览器，不重复启动。
2. 从首选端口起找空闲端口（被占用则自动后移，不因 8000 被占而失败）。
3. 用 .venv 的 pythonw.exe 后台启动 run.py（无窗口）；run.py 若发现竞态占用会再换端口。
4. 轮询 /health 直到就绪（最多 90 秒，模型/依赖加载慢时留足余量）。
5. 打开默认浏览器。

全程只依赖标准库。命令行运行时输出进度；双击 bat 时窗口短暂显示后自动关闭。
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from ports import (
    DEFAULT_PORT,
    HOST,
    PORT_SCAN_LIMIT,
    find_available_port,
    preferred_port,
    read_port_file,
    write_port_file,
)

BASE_DIR = Path(__file__).resolve().parent
START_TIMEOUT = 90  # 秒


def http_ok(url: str, timeout: float = 2.0) -> bool:
    """GET url，返回是否 200。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def is_any2md(port: int) -> bool:
    """端口上是否跑着 any2md（以 /health 返回 200 判定）。"""
    return http_ok(f"http://{HOST}:{port}/health")


def _tcp_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((HOST, port)) == 0


def find_running_any2md() -> int | None:
    """优先看上次写入的端口，再扫首选端口附近，避免全段 HTTP 探测。"""
    recorded = read_port_file()
    if recorded is not None and is_any2md(recorded):
        return recorded
    start = preferred_port()
    end = min(start + PORT_SCAN_LIMIT, 65536)
    for port in range(start, end):
        if not _tcp_open(port):
            continue
        if is_any2md(port):
            return port
    if start != DEFAULT_PORT:
        for port in range(DEFAULT_PORT, min(DEFAULT_PORT + PORT_SCAN_LIMIT, 65536)):
            if not _tcp_open(port):
                continue
            if is_any2md(port):
                return port
    return None


def main() -> int:
    # ---- 1. 已在运行？直接开浏览器 ----
    running = find_running_any2md()
    if running is not None:
        print(f"any2md 已在运行: http://{HOST}:{running}/")
        open_browser(f"http://{HOST}:{running}/")
        return 0

    # ---- 2. 找空闲端口（被占则自动后移） ----
    want = preferred_port()
    port = find_available_port(start=want)
    if port != want:
        print(f"端口 {want} 已被占用，自动切换到 {port}")

    # ---- 3. 后台静默启动（pythonw 无窗口；stdout 重定向到日志文件便于排错） ----
    venv_dir = BASE_DIR / ".venv" / "Scripts"
    pythonw = venv_dir / "pythonw.exe"
    python = venv_dir / "python.exe"
    exe = pythonw if pythonw.exists() else python
    if not exe.exists():
        print(f"[ERROR] 未找到 {exe}")
        print("请先在项目目录执行:")
        print("  python -m venv .venv")
        print("  .venv\\Scripts\\pip install -r requirements.txt -r requirements-engine.txt")
        input("按回车退出...")
        return 1

    env = {**os.environ, "ANY2MD_PORT": str(port), "PYTHONUNBUFFERED": "1"}
    log_path = BASE_DIR / "storage" / "server.log"
    pid_path = BASE_DIR / "storage" / "server.pid"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_port_file(port)
    print(f"any2md 启动中: http://{HOST}:{port}/")
    with log_path.open("ab") as log:
        proc = subprocess.Popen(
            [str(exe), str(BASE_DIR / "run.py")],
            cwd=str(BASE_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW
            if os.name == "nt"
            else 0,  # 完全无窗口
        )
    pid_path.write_text(str(proc.pid), encoding="ascii")  # stop.py 据此结束进程树

    # ---- 4. 等就绪（run.py 若遇竞态会再换端口，以 server.port 为准） ----
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        actual = read_port_file() or port
        if is_any2md(actual):
            print(f"已就绪: http://{HOST}:{actual}/ ，正在打开浏览器...")
            open_browser(f"http://{HOST}:{actual}/")
            print("服务在后台运行。停止服务请双击 stop-any2md.bat。")
            time.sleep(2)  # 让用户看到提示
            return 0
        time.sleep(1)
    print(f"[ERROR] 服务 {START_TIMEOUT} 秒内未就绪，日志见: {log_path}")
    input("按回车退出...")
    return 1


def open_browser(url: str) -> None:
    try:
        import webbrowser

        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
