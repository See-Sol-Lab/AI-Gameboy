@echo off
cd /d "%~dp0"
chcp 65001 >nul
echo AI-Gameboy 启动游戏机: 本机入口可用，已配置的固定隧道会一起启动
python -m console.server
pause
