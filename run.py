"""便捷启动器：python run.py，然后打开 http://127.0.0.1:8000

ANY2MD_PORT 环境变量可覆盖端口（start-any2md.bat 用它实现端口自动避让）。
"""
from __future__ import annotations

import os

import uvicorn

HOST = "127.0.0.1"
PORT = int(os.environ.get("ANY2MD_PORT", "8000"))

if __name__ == "__main__":
    # reload=False：改了代码要重启进程才生效
    # use_colors=False：Windows cmd.exe 不解析 ANSI 颜色码，关闭以免输出 [32m/[1m 之类的乱码
    print(f"any2md 启动中: http://{HOST}:{PORT}", flush=True)
    uvicorn.run(
        "backend.app.main:app",
        host=HOST,
        port=PORT,
        reload=False,
        use_colors=False,
    )
