@echo off
REM Kensho Daemon セットアップ — Watchdog + 自動起動
chcp 65001 >nul
setlocal

set "BASE=D:\Project2\kensho"
set "PYTHON=C:\Users\1F\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
set "WATCHDOG=%BASE%\scripts\kensho_watchdog.bat"

echo === Kensho Daemon セットアップ ===
echo.

REM ── 1. Watchdog Task Scheduler登録 ──
echo [1/3] Watchdog Task Scheduler登録...
schtasks /QUERY /TN "KenshoWatchdog" >nul 2>&1
if %errorlevel% equ 0 (
    echo   ※ KenshoWatchdog タスクは既に存在します（上書き登録）
    schtasks /DELETE /TN "KenshoWatchdog" /F >nul 2>&1
)

schtasks /CREATE /TN "KenshoWatchdog" /TR "%WATCHDOG%" ^
    /SC MINUTE /MO 5 /RU SYSTEM /F >nul 2>&1
if %errorlevel% equ 0 (
    echo   ✅ 登録完了（5分おきに死活監視）
) else (
    echo   ❌ 登録失敗（管理者権限で実行して下さい）
)

REM ── 2. ログイン時自動起動 ──
echo [2/3] ログイン時自動起動登録...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" ^
    /v "KenshoDaemon" /t REG_SZ ^
    /d "%PYTHON% %BASE%\daemon.py" /f >nul 2>&1
echo   ✅ 登録完了

REM ── 3. daemon起動確認 ──
echo [3/3] daemon起動確認...
tasklist /FI "IMAGENAME eq python.exe" 2>nul | findstr python >nul
if %errorlevel% equ 0 (
    echo   ✅ daemon.py は既に稼働中
) else (
    echo   🔄 daemon.py を起動します...
    start "" /B "%PYTHON%" "%BASE%\daemon.py"
    echo   ✅ 起動完了
)

echo.
echo === セットアップ完了 ===
echo.
echo   Watchdog  : 5分おきにdaemon死活監視（自動再起動）
echo   自動起動  : ログイン時にdaemon自動起動
echo.
echo   確認コマンド:
echo     tasklist /FI "IMAGENAME eq python.exe"
echo     schtasks /QUERY /TN "KenshoWatchdog"
echo.
echo   削除コマンド:
echo     schtasks /DELETE /TN "KenshoWatchdog" /F
echo     reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "KenshoDaemon" /f
