"""停止 any2md 后台服务。

优先读 storage/server.pid（launch.py 启动时写入），用 taskkill /T 结束整个进程树；
找不到时兜底扫描命令行含 run.py 且路径在本项目内的 python 进程。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PID_PATH = BASE_DIR / "storage" / "server.pid"


def kill_pid(pid: int) -> bool:
    """taskkill /T /F 结束进程树，返回是否成功。"""
    r = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def stop_by_pid_file() -> bool:
    if not PID_PATH.exists():
        return False
    try:
        pid = int(PID_PATH.read_text(encoding="ascii").strip())
    except (ValueError, OSError):
        PID_PATH.unlink(missing_ok=True)
        return False
    ok = kill_pid(pid)
    PID_PATH.unlink(missing_ok=True)
    return ok


def stop_by_scan() -> bool:
    """兜底：PowerShell 扫描本项目 venv 里跑 run.py 的进程（wmic 在新 Win11 已移除）。"""
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -like 'python*' -and "
        "$_.CommandLine -like '*run.py*' -and "
        "$_.CommandLine -like '*any2md*' } | "
        "ForEach-Object { $_.ProcessId }"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as e:
        print(f"[ERROR] 无法枚举进程: {e}")
        return False
    found = False
    for line in r.stdout.split():
        if not line.strip().isdigit():
            continue
        pid = int(line)
        print(f"正在停止 any2md (PID {pid}) ...")
        if kill_pid(pid):
            found = True
    return found


def main() -> int:
    stopped = stop_by_pid_file() or stop_by_scan()
    print("any2md 已停止。" if stopped else "any2md 未在运行。")
    input("按回车退出...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
