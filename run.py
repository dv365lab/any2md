"""便捷启动器：python run.py，然后打开 http://127.0.0.1:8000"""
from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    # reload=False：改了代码要重启进程才生效
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
