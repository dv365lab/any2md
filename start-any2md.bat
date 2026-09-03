@echo off
rem any2md 一键启动：双击即用（找端口→后台启动→自动开浏览器）
cd /d "%~dp0"
".venv\Scripts\python.exe" launch.py
