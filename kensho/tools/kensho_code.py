#!/usr/bin/env python3
"""
Kensho Code Workflow — Aider + DeepSeek公式API + pytest

使い方:
  python tools/kensho_code.py                            # インタラクティブ
  python tools/kensho_code.py "このバグ直して"           # 1回だけ実行
  python tools/kensho_code.py --mode plan                # 計画のみ
  python tools/kensho_code.py --mode test                # テストのみ
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime

PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\033[36m[{ts}]\033[0m {msg}", flush=True)


def check_git(work_dir: pathlib.Path) -> bool:
    """Gitリポジトリ確認（なければ作る）"""
    git_dir = work_dir / ".git"
    if not git_dir.exists():
        log("📦 Gitリポジトリがありません → 作成します")
        subprocess.run(["git", "init"], cwd=work_dir, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=work_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial commit before using Aider"], cwd=work_dir, capture_output=True)
    return True


def step1_aider(prompt: str, work_dir: pathlib.Path, arch: bool = True) -> bool:
    """Step 1: Aider + DeepSeekでコード修正"""
    log("=" * 50)
    log("🚀 Aider + DeepSeek でコード修正開始")
    log("=" * 50)

    aider = shutil.which("aider")
    if not aider:
        log("❌ aider not found. インストール: pip install aider-install && aider-install")
        return False

    env = os.environ.copy()
    # .envからキーを読み込む
    env_file = work_dir / ".env"
    if env_file.exists():
        for line in env_file.read_text("utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    # Aiderの推奨フラグ
    cmd = [
        aider,
        "--model",
        "deepseek/deepseek-v4-flash",
        "--yes",
        "--no-show-model-warnings",
        "--auto-commits",
    ]  # 自動コミット

    if arch:
        cmd.append("--architect")  # 計画→実行モード

    # テストコマンド（--dir指定時は全テスト、未指定時は test_browser.py 除外）
    if work_dir == PROJECT_DIR:
        test_cmd = "python -m pytest -x -q --ignore=tests/test_browser.py"
    else:
        test_cmd = "python -m pytest -x -q"
    cmd.extend(["--test-cmd", test_cmd])

    # プロンプト
    if prompt:
        cmd.extend(["--message", prompt])
        log(f"📝 タスク: {prompt[:80]}...")
    else:
        log("💬 インタラクティブモード（終わったらCtrl+C or /exit）")

    log("🤖 Model: DeepSeek公式API（コスト約$0.002/回）")
    log("🛡️ 安全機能: 自動git commit + テスト失敗時は自動revert")
    log("")

    try:
        proc = subprocess.run(cmd, cwd=work_dir, env=env)
        if proc.returncode == 0:
            log("✅ Aider完了！")
        else:
            log(f"⚠️ Aiderが終了コード {proc.returncode} で終了")
        return proc.returncode == 0
    except KeyboardInterrupt:
        log("⚠️ 中断されました")
        return False


def step2_pytest(work_dir: pathlib.Path) -> bool:
    """Step 2: pytest最終確認"""
    log("=" * 50)
    log("🧪 pytest 最終確認")
    log("=" * 50)

    # テストコマンド（--dir指定時は全テスト、未指定時は test_browser.py 除外）
    if work_dir == PROJECT_DIR:
        pytest_cmd = [sys.executable, "-m", "pytest", "-x", "-q", "--ignore=tests/test_browser.py", "tests/"]
    else:
        pytest_cmd = [sys.executable, "-m", "pytest", "-x", "-q", "tests/"]
    proc = subprocess.run(pytest_cmd, cwd=work_dir, capture_output=True, text=True)

    for line in proc.stdout.strip().splitlines():
        if line.strip():
            log(f"  {line.strip()}")

    if proc.returncode == 0:
        log("✅ 全テスト通過！変更は安全です")
        return True
    else:
        log(f"❌ テスト失敗！終了コード: {proc.returncode}")
        log("💡 Aiderが自動revertしたはずです。確認:")
        log("   git log --oneline -3")
        return False


def run_aider_hermes(prompt: str, files: list[str], target_dir: pathlib.Path | None = None) -> dict:
    """Hermes連携: Aiderを非対話モードで実行しJSON結果を返す"""
    import threading
    import time

    work_dir: pathlib.Path = target_dir or PROJECT_DIR

    aider = shutil.which("aider")
    if not aider:
        return {"status": "error", "message": "aider not found"}

    env = os.environ.copy()
    env_file = work_dir / ".env"
    if env_file.exists():
        for line in env_file.read_text("utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    check_git(work_dir)

    cmd = [
        aider,
        "--model",
        "deepseek/deepseek-v4-flash",
        "--yes",
        "--no-show-model-warnings",
        "--auto-commits",
        "--architect",
        "--test-cmd",
        "python -m pytest -x -q --ignore=tests/test_browser.py",
        "--no-stream",
        "--message",
        prompt,
    ]
    if files:
        cmd.extend(files)

    # ── プログレス表示（コンソール + data/.aider-progress.txt ファイル）──
    progress_stop = threading.Event()
    _PROGRESS_FILE = work_dir / "data" / ".aider-progress.txt"
    _PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _print_progress() -> None:
        t0 = time.time()
        spinner = "⠋⠙⠸⠴⠦⠇"
        idx = 0
        while not progress_stop.is_set():
            spin = spinner[idx % len(spinner)]
            elapsed = time.time() - t0
            line = f"[{spin}] Aider実行中... {elapsed:.0f}秒経過"
            print(f"  {line}", flush=True)
            try:
                _PROGRESS_FILE.write_text(line, encoding="utf-8")
            except Exception:
                pass
            idx += 1
            progress_stop.wait(5.0)

    t0 = time.time()
    progress_thread = threading.Thread(target=_print_progress, daemon=True)
    progress_thread.start()

    try:
        proc = subprocess.run(
            cmd,
            cwd=work_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        progress_stop.set()
        try:
            _PROGRESS_FILE.write_text("[✗] Aiderタイムアウト (600秒)", encoding="utf-8")
        except Exception:
            pass
        return {"status": "error", "message": "Aider timed out (600s)"}
    finally:
        progress_stop.set()
        try:
            _PROGRESS_FILE.write_text(f"[✓] Aider完了: {round(time.time() - t0, 1)}秒", encoding="utf-8")
        except Exception:
            pass

    elapsed = time.time() - t0

    # git差分を取得
    diff_proc = subprocess.run(
        ["git", "diff", "--stat"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    diff_stat = diff_proc.stdout.strip()

    # 最新コミットを取得
    log_proc = subprocess.run(
        ["git", "log", "--oneline", "-3"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    recent_commits = log_proc.stdout.strip()

    result = {
        "status": "ok" if proc.returncode == 0 else "error",
        "returncode": proc.returncode,
        "elapsed_sec": round(elapsed, 1),
        "stdout": proc.stdout.strip()[-2000:],  # 末尾2000文字
        "stderr": proc.stderr.strip()[-1000:],
        "diff_stat": diff_stat,
        "recent_commits": recent_commits,
    }
    if proc.returncode != 0:
        result["message"] = f"Aider exited with code {proc.returncode}"
    return result


def main():
    parser = argparse.ArgumentParser(description="Kensho Code Workflow")
    parser.add_argument("prompt", nargs="?", default="", help="タスク指示")
    parser.add_argument("--mode", choices=["full", "plan", "code", "test"], default="full", help="実行モード")
    parser.add_argument("--no-architect", action="store_true", help="Architectモード無効")
    parser.add_argument("--hermes", action="store_true", help="Hermes連携モード（JSON出力、装飾なし）")
    parser.add_argument("files", nargs="*", help="編集対象ファイル")
    parser.add_argument("--dir", type=str, default=None, help="作業ディレクトリ（省略時はプロジェクトルート）")
    args = parser.parse_args()

    # --- 作業ディレクトリ決定 ---
    target_dir = pathlib.Path(args.dir).resolve() if args.dir else PROJECT_DIR

    # --- Hermes連携モード ---
    if args.hermes:
        import json

        if not args.prompt:
            result = {"status": "error", "message": "prompt is required in --hermes mode"}
        else:
            result = run_aider_hermes(args.prompt, args.files, target_dir)
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0 if result["status"] == "ok" else 1)

    mode = args.mode

    print("")
    print("╔═══════════════════════════════════════════╗")
    print("║     Kensho Code Workflow v2.0            ║")
    print("║     🚀 Aider + DeepSeek                  ║")
    print("╚═══════════════════════════════════════════╝")
    print("")

    # Git確認
    check_git()

    if mode == "full":
        ok = step1_aider(args.prompt, target_dir, arch=not args.no_architect)
        if ok:
            step2_pytest(target_dir)
        log("🏁 ワークフロー完了")
        print("")

    elif mode == "plan":
        log("📋 計画モード（変更前に計画を確認）")
        ok = step1_aider(args.prompt, target_dir, arch=True)
        if not ok:
            log("💡 計画は承認されませんでした")

    elif mode == "code":
        log("🚀 コード修正のみ（テストなし）")
        step1_aider(args.prompt, target_dir, arch=False)

    elif mode == "test":
        step2_pytest(target_dir)

    # 変更サマリー
    if mode in ("full", "code"):
        log("")
        log("📊 変更サマリー:")
        subprocess.run(["git", "diff", "--stat"], cwd=target_dir)


if __name__ == "__main__":
    main()
