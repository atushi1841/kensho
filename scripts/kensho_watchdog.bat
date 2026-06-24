@echo off
REM Kensho Daemon Watchdog — daemon.py の死活監視・自動再起動
REM Windows Task Scheduler から5分おきに実行される想定
chcp 65001 >nul
setlocal enabledelayedexpansion

set "BASE=D:\Project2\kensho"
set "PYTHON=C:\Users\1F\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
set "DAEMON=%BASE%\daemon.py"
set "LOG=%BASE%\logs\watchdog.log"

REM PIDファイルからdaemonのPIDを取得
set "PID_FILE=%BASE%\data\locks\daemon.pid"
set PID=
if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
)

if defined PID (
    tasklist /FI "PID eq %PID%" 2>nul | findstr /I "python" >nul
    if !errorlevel! equ 0 (
        REM daemonは正常稼働中
        exit /b 0
    )
)

REM daemonが死んでる → 再起動
echo [%date% %time%] daemon停止検出 → 再起動 >> "%LOG%"

REM ゾンビFirefox掃除
taskkill /F /IM firefox.exe >nul 2>&1

REM daemon起動（窓ゼロ）
start "" /B "%PYTHON%" "%DAEMON%"

echo [%date% %time%] daemon再起動完了 >> "%LOG%"
exit /b 0
