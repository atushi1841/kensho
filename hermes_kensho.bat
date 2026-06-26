@echo off
REM ════════════════════════════════════════════
REM Kensho Hermes Launcher
REM ── 事前チェック → Hermes起動 ──
REM
REM 使い方:
REM   hermes_kensho                    — 事前チェック後にhermes起動
REM   hermes_kensho --check-only      — チェックのみ（hermes起動しない）
REM   hermes_kensho --force-reset     — pg0強制初期化後にhermes起動
REM   hermes_kensho --skip-check      — チェックせず直接hermes起動
REM ════════════════════════════════════════════

setlocal enabledelayedexpansion

set PROJECT_DIR=D:\Project2\kensho
set PYTHON=C:\Users\1F\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe
set HERMES=C:\Users\1F\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe

set CHECK_ONLY=0
set FORCE_RESET=0
set SKIP_CHECK=0

:parse_args
if "%~1"=="" goto :end_parse
if "%~1"=="--check-only" set CHECK_ONLY=1
if "%~1"=="--force-reset" set FORCE_RESET=1
if "%~1"=="--skip-check" set SKIP_CHECK=1
shift
goto :parse_args
:end_parse

echo ═══════════════════════════════════════════
echo Kensho Hermes Launcher
echo ═══════════════════════════════════════════
echo.
echo Project: %PROJECT_DIR%
echo Python:  %PYTHON%
echo Hermes:  %HERMES%
echo.

if %SKIP_CHECK%==1 (
    echo [SKIP] 事前チェックをスキップ
    goto :launch_hermes
)

REM ── Step 1: Health Check ──
echo [1/2] Running Health Check...
if %FORCE_RESET%==1 (
    "%PYTHON%" "%PROJECT_DIR%\tools\health_check.py" --force-reset
) else (
    "%PYTHON%" "%PROJECT_DIR%\tools\health_check.py"
)

if errorlevel 1 (
    echo ⚠ Health Check で警告があります — 続行しますか？
    choice /C YN /M "続行(Y) / 中止(N)"
    if errorlevel 2 (
        echo 中止しました
        pause
        exit /b 1
    )
)

REM ── Step 2: Hindsight Guard ──
echo [2/2] Running Hindsight Guard...
if %FORCE_RESET%==1 (
    "%PYTHON%" "%PROJECT_DIR%\tools\hindsight_guard.py" --force-reset
) else (
    "%PYTHON%" "%PROJECT_DIR%\tools\hindsight_guard.py"
)

if errorlevel 2 (
    echo ❌ Hindsight Guard で修復不能なエラー — 手動対応が必要です
    echo    ログ: %PROJECT_DIR%\logs\hindsight_guard.log
    pause
    exit /b 2
)

if %CHECK_ONLY%==1 (
    echo.
    echo ✅ チェック完了（--check-only のため終了）
    pause
    exit /b 0
)

echo.
echo ✅ 事前チェック完了 — Hermes を起動します...
echo.

:launch_hermes

REM ── Hindsight起動時のログをクリア（巨大化防止）──
if exist "%USERPROFILE%\.hindsight\profiles\hermes.log" (
    for %%F in ("%USERPROFILE%\.hindsight\profiles\hermes.log") do (
        if %%~zF GTR 10485760 (
            del /F /Q "%%F" 2>nul
            echo [CLEANUP] hindsight.log が10MB超のため削除
        )
    )
)

REM ── ロックファイル削除 ──
if exist "%USERPROFILE%\.hindsight\profiles\hermes.lock" (
    del /F /Q "%USERPROFILE%\.hindsight\profiles\hermes.lock" 2>nul
)

REM ── Hermes起動 ──
echo 🚀 Launching Hermes...
echo.
"%HERMES%" %*

if errorlevel 1 (
    echo ❌ Hermes が異常終了しました (exit code %errorlevel%)
    pause
    exit /b %errorlevel%
)

exit /b 0
