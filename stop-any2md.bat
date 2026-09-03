@echo off
rem 停止 any2md 后台服务
cd /d "%~dp0"
".venv\Scripts\python.exe" stop.py
