#!/usr/bin/env python3
"""Aider Launcher v2 — Kensho用Aider起動ヘルパー"""

import os
import shutil
import subprocess
import sys


def main():
    # 環境変数からキーを取得
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    # Hermes経由だとキーが隠されるので、他の取得方法も試す
    if len(deepseek_key) <= 3:
        deepseek_key = ""
    if len(openrouter_key) <= 3:
        openrouter_key = ""

    aider_path = shutil.which("aider")
    if not aider_path:
        print("❌ aider not found.", file=sys.stderr)
        print("   インストール: pip install aider-install && aider-install", file=sys.stderr)
        sys.exit(1)

    # キーがない場合の対処
    if not deepseek_key and not openrouter_key:
        print("")
        print("⚠️  APIキーが利用できません。以下の手順で設定してください:")
        print("")
        print("   1. 通常のCMDまたはPowerShellを開く（Hermes経由は不可）")
        print("   2. cd D:\\Project2\\kensho")
        print("   3. setup_aider.bat を実行")
        print("")
        print("   または手動で:")
        print('     setx OPENROUTER_API_KEY "あなたのキー"')
        print("")
        print("   設定後、端末を再起動してから再度実行してください。")
        print("")
        sys.exit(1)

    # コマンド構築
    cmd = [aider_path]
    # DeepSeek V4 Flash 公式API直結（OpenRouterは不使用）
    cmd.extend(["--model", "deepseek/deepseek-v4-flash"])
    cmd.extend(["--yes", "--no-show-model-warnings"])
    cmd.extend(sys.argv[1:])

    env = os.environ.copy()
    if openrouter_key:
        env["OPENROUTER_API_KEY"] = openrouter_key
    if deepseek_key:
        env["DEEPSEEK_API_KEY"] = deepseek_key

    try:
        proc = subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        sys.exit(1)

    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
