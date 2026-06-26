@echo off
REM ════════════════════════════════════════════
REM Aider Setup for Kensho
REM ── 1回だけ実行すればOK ──
REM
REM 通常のコマンドプロンプトまたはPowerShellから
REM 実行してください（Hermes経由だとAPIキーが隠されます）
REM ════════════════════════════════════════════

echo ═══════════════════════════════════════════
echo Aider Setup for Kensho
echo ═══════════════════════════════════════════
echo.
echo このスクリプトは「通常の端末(CMD/PowerShell)」で
echo 実行してください。Hermes経由ではAPIキーが読めません。
echo.
echo Aider v0.86.2 がインストール済みです。
echo.
echo 使用するAPIキーを選んでください：
echo.
echo   [1] OpenRouter（推奨）— DeepSeek V3.2等が使える
echo   [2] DeepSeek直接 — DeepSeek APIキーが必要
echo   [3] Gemini CLI（完全無料）— Googleアカウントが必要
echo.

set /P CHOICE="番号を入力 (1/2/3): "

if "%CHOICE%"=="1" goto :setup_openrouter
if "%CHOICE%"=="2" goto :setup_deepseek
if "%CHOICE%"=="3" goto :setup_gemini
echo 無効な選択です
pause
exit /b 1

:setup_openrouter
echo.
echo OpenRouterのAPIキーを入力してください
echo （取得: https://openrouter.ai/keys）
set /P OR_KEY="APIキー: "
if "%OR_KEY%"=="" goto :setup_openrouter
setx OPENROUTER_API_KEY "%OR_KEY%"
echo.
echo ✅ OpenRouter APIキーを設定しました！
echo 端末を再起動すると有効になります。
echo.
echo 使い方:
echo   cd /d D:\Project2\kensho
echo   aider --model openrouter/deepseek/deepseek-chat --architect --auto-commits
echo.
echo またはランチャーを使う:
echo   python tools\aider_launcher.py
goto :end

:setup_deepseek
echo.
echo DeepSeekのAPIキーを入力してください
echo （取得: https://platform.deepseek.com/api_keys）
set /P DS_KEY="APIキー: "
if "%DS_KEY%"=="" goto :setup_deepseek
setx DEEPSEEK_API_KEY "%DS_KEY%"
echo.
echo ✅ DeepSeek APIキーを設定しました！
echo 端末を再起動すると有効になります。
echo.
echo 使い方:
echo   cd /d D:\Project2\kensho
echo   aider --model deepseek/deepseek-chat --architect --auto-commits
goto :end

:setup_gemini
echo.
echo Gemini CLIは Google AI Studio から無料で使えます
echo https://aistudio.google.com/
echo.
echo インストール:
echo   npm install -g @google/gemini-cli
echo.
echo 使い方:
echo   cd /d D:\Project2\kensho
echo   gemini "このバグを直して"
goto :end

:end
echo.
echo ═══════════════════════════════════════════
echo テスト方法:
echo   1. 端末を再起動（環境変数を反映）
echo   2. cd /d D:\Project2\kensho
echo   3. aider_kensho.bat "簡単な修正をテスト"
echo ═══════════════════════════════════════════
pause
