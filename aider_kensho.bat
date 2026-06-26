@echo off
REM ════════════════════════════════════════════
REM Aider Launcher for Kensho
REM ── DeepSeek / OpenRouter 自動判定 ──
REM
REM 使い方:
REM   aider_kensho                    — インタラクティブモード
REM   aider_kensho "バグを直して"     — 1回だけ実行
REM   aider_kensho --architect        — 計画→実行モード
REM ════════════════════════════════════════════

cd /d D:\Project2\kensho

REM Python経由のランチャーを使う（APIキーの特殊文字対策）
python tools\aider_launcher.py %*
