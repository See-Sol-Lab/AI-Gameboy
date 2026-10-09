@echo off
cd /d "%~dp0"
chcp 65001 >nul
echo AI-Gameboy 本地模式: 只有这台电脑能连
python -m console.server
pause
