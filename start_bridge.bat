@echo off
cd /d "%~dp0"
chcp 65001 >nul
echo AI-Gameboy 开桥模式: 给不在这台电脑上的 AI 一个公网 MCP 网址
python -m console.server --bridge
pause
