@echo off
title AlpLingo
chcp 65001 > nul
cd /d "%~dp0"

echo ===================================================
echo   AlpLingo - Ekran ve Oyun Cevirici Baslatiliyor
echo   Model: Meta NLLB-200 (NVIDIA RTX CUDA / CPU)
echo ===================================================

taskkill /F /IM pythonw.exe >nul 2>&1
start "" "runtime\pythonw.exe" main.py
exit
