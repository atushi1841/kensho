@echo off
REM ════════════════════════════════════════════
REM Kensho Code Workflow Launcher
REM ── Aider + DeepSeek公式API + pytest ──
REM
REM 使い方:
REM   kensho_code.bat                              # インタラクティブ
REM   kensho_code.bat "バグ直して"                 # 一発指示
REM   kensho_code.bat --hermes "ここ直して" file.py  # Hermes連携
REM   kensho_code.bat --mode plan                  # 計画のみ
REM   kensho_code.bat --mode test                  # テストのみ
REM ════════════════════════════════════════════

cd /d D:\Project2\kensho

python tools\kensho_code.py %*
