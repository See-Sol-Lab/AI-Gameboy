@echo off
cd /d "%~dp0"
chcp 65001 >nul
echo AI-Gameboy 临时外网接入: 启动同一台游戏机并附带临时隧道
python -m console.server --bridge
pause
