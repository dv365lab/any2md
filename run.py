"""便捷启动器：python run.py。

默认尝试 8000；被占用则自动向后换端口，直到能绑定为止。
ANY2MD_PORT 可指定首选端口（start-any2md.bat / launch.py 会传入）。
"""
from __future__ import annotations

import uvicorn

from ports import (
    HOST,
    find_available_port,
    is_addr_in_use,
    preferred_port,
    write_port_file,
)


def _start(port: int) -> None:
    write_port_file(port)
    print(f"any2md 启动中: http://{HOST}:{port}", flush=True)
    uvicorn.run(
        "backend.app.main:app",
        host=HOST,
        port=port,
        reload=False,
        use_colors=False,
    )


if __name__ == "__main__":
    # reload=False：改了代码要重启进程才生效
    # use_colors=False：Windows cmd.exe 不解析 ANSI 颜色码，关闭以免输出 [32m/[1m 之类的乱码
    want = preferred_port()
    start = want
    last_error: BaseException | None = None
    for _ in range(32):
        port = find_available_port(start=start)
        if port != want:
            print(
                f"端口 {want} 已被占用，自动切换到 {port}",
                flush=True,
            )
        try:
            _start(port)
            break
        except OSError as exc:
            last_error = exc
            if not is_addr_in_use(exc):
                raise
            print(f"端口 {port} 在绑定前被占用，继续寻找…", flush=True)
            if port >= 65535:
                raise RuntimeError("找不到可用端口") from exc
            start = port + 1
    else:
        raise RuntimeError("找不到可用端口") from last_error
