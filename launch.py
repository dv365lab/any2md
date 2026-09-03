"""一键启动器（被 start-any2md.bat 调用）。

逻辑：
1. 扫描 8000-8009，找一个既有空闲又能通过 /health 探测确认不是 any2md 的端口
   （若 8000 上已经是 any2md，直接开浏览器，不重复启动）。
2. 用 .venv 的 pythonw.exe 后台启动 run.py（无窗口）。
3. 轮询 /health 直到就绪（最多 90 秒，模型/依赖加载慢时留足余量）。
4. 打开默认浏览器。

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

BASE_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT_RANGE = range(8000, 8010)
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


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.connect_ex((HOST, port)) != 0


def main() -> int:
    # ---- 1. 已在运行？直接开浏览器 ----
    for port in PORT_RANGE:
        if is_any2md(port):
            print(f"any2md 已在运行: http://{HOST}:{port}/")
            open_browser(f"http://{HOST}:{port}/")
            return 0

    # ---- 2. 找空闲端口 ----
    port = None
    for p in PORT_RANGE:
        if port_free(p):
            port = p
            break
    if port is None:
        print("[ERROR] 8000-8009 端口全被占用，请先运行 stop-any2md.bat 或清理端口。")
        input("按回车退出...")
        return 1

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

    # ---- 4. 等就绪 ----
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if is_any2md(port):
            print("已就绪，正在打开浏览器...")
            open_browser(f"http://{HOST}:{port}/")
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
