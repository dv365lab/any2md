"""监听端口选择：优先用户指定/默认端口，被占用则向后找空闲端口。

仅依赖标准库，供 run.py 与 launch.py 共用。
"""
from __future__ import annotations

import os
import socket
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 8000
# 从首选端口起连续探测的数量（含首选）。足够大，避免十几个常见开发端口被占就起不来。
PORT_SCAN_LIMIT = 100

BASE_DIR = Path(__file__).resolve().parent
PORT_FILE = BASE_DIR / "storage" / "server.port"


def preferred_port() -> int:
    raw = os.environ.get("ANY2MD_PORT", str(DEFAULT_PORT)).strip()
    try:
        port = int(raw)
    except ValueError:
        return DEFAULT_PORT
    if port <= 0 or port > 65535:
        return DEFAULT_PORT
    return port


def can_bind(host: str, port: int) -> bool:
    """本进程此刻能否 bind 该地址（比 connect 探测更贴近真实启动）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _os_assigned_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def find_available_port(
    host: str = HOST,
    start: int | None = None,
    limit: int = PORT_SCAN_LIMIT,
) -> int:
    """从 start 起找可 bind 的端口；一段都满则交给操作系统分配。"""
    if start is None:
        start = preferred_port()
    if start <= 0 or start > 65535:
        start = DEFAULT_PORT
    end = min(start + limit, 65536)
    for port in range(start, end):
        if can_bind(host, port):
            return port
    return _os_assigned_port(host)


def is_addr_in_use(exc: BaseException) -> bool:
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in {98, 48, 10048}:
        return True
    # Windows / uvicorn 包装后的文案兜底
    msg = str(exc).lower()
    return "address already in use" in msg or "10048" in msg


def write_port_file(port: int) -> None:
    PORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    PORT_FILE.write_text(str(port), encoding="ascii")


def read_port_file() -> int | None:
    if not PORT_FILE.exists():
        return None
    try:
        port = int(PORT_FILE.read_text(encoding="ascii").strip())
    except (ValueError, OSError):
        return None
    if port <= 0 or port > 65535:
        return None
    return port
