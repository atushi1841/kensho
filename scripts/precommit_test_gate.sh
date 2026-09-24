#!/usr/bin/env bash
# scripts/precommit_test_gate.sh — commit 前テストゲート (t_1570eca6)
#
# 背景: 赤テストのまま commit が進行し、破損版が HEAD に入る → loop_health.sh 全断
# （QA notepad 9/25 実測: tests/test_loop_health.py 3 failed のまま f20bf96/3f1727a。
#   NameError: repeats → score=0 / alert=ERROR、profile 側 symlink 経由で全レポート＋
#   3 monitor が同時盲目化）。push-guard (t_c2104009) は push 忘れ防止のみで
#   テストは実行しないため、赤コミットを止めるゲートが存在しなかった。
#
# 実装:
#   - ステージされた変更 *.py/*.yaml/*.sh/*.js（tests/ 配下は除外）ごとに、
#     対応する tests/test_<stem>.py があれば実行し、赤なら exit 1（commit 拒否）。
#   - 対応テストが特定できない場合は警告のみ（ブロックしない・開発を止めない）。
#   - cron 最小PATH (/usr/bin:/bin) でも動くよう python は絶対パスで解決する
#     （bare `python3` / bare `hermes` は使わない）。
#
# 使い方:
#   bash scripts/precommit_test_gate.sh [--workdir <path>] [--stage pre-commit|manual]
#
# exit code: 0 = PASS / skip / 警告のみ   1 = 赤テストあり（commit 拒否）

set -uo pipefail

WORKDIR=""
STAGE="pre-commit"
while [ $# -gt 0 ]; do
    case "$1" in
        --workdir) WORKDIR="$2"; shift 2 ;;
        --stage)   STAGE="$2";   shift 2 ;;
        *) echo "[precommit-test-gate] unknown arg: $1" >&2; exit 2 ;;
    esac
done

if [ -z "$WORKDIR" ]; then
    WORKDIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi
if [ ! -d "$WORKDIR/.git" ] && [ ! -f "$WORKDIR/.git" ]; then
    echo "[precommit-test-gate] skip: not a git repo ($WORKDIR)"
    exit 0
fi
cd "$WORKDIR" || exit 0

# python 解決: まず HERMES_VENV_BIN、次に PATH。bare python3 依存を避ける。
PYTHON="${HERMES_VENV_BIN:-/home/atushi/.hermes/hermes-agent/venv/bin}/python3"
if [ ! -x "$PYTHON" ]; then
    PYTHON="$(command -v python3 || true)"
fi
if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
    echo "[precommit-test-gate] BLOCK: python3 unresolved (PATH=$PATH, HERMES_VENV_BIN=${HERMES_VENV_BIN:-unset})" >&2
    exit 1
fi

# ステージされた変更を取得（pre-commit hook 経路）。手動実行では作業ツリー差分。
if [ "$STAGE" = "pre-commit" ]; then
    CHANGED="$(git diff --cached --name-only 2>/dev/null)"
else
    CHANGED="$(git status --porcelain 2>/dev/null | awk '{print $2}')"
fi

if [ -z "$CHANGED" ]; then
    echo "[precommit-test-gate] no staged files — skip"
    exit 0
fi

FAILURES=""
TESTED=0
CODE_SEEN=0

while IFS= read -r file; do
    [ -z "$file" ] && continue
    # tests/ 配下はスキップ（ゲート自身の無限ループ防止）
    case "$file" in
        tests/*) continue ;;
    esac
    # コード対象: *.py / *.yaml / *.sh / *.js（.html は除外、data/・reports/ は除外）
    case "$file" in
        *.py|*.yaml|*.sh|*.js) ;;
        *) continue ;;
    esac
    case "$file" in
        data/*|reports/*) continue ;;
    esac

    CODE_SEEN=$((CODE_SEEN + 1))

    stem="$(basename "$file")"
    stem="${stem%.*}"
    candidate="tests/test_${stem}.py"
    if [ ! -f "$candidate" ]; then
        echo "[precommit-test-gate] warning: no test for $file (expected $candidate)"
        continue
    fi

    TESTED=$((TESTED + 1))
    echo "[precommit-test-gate] testing $candidate (for $file)"
    if ! "$PYTHON" -m pytest "$candidate" -q --no-header --tb=line \
         -p no:cacheprovider --no-cov 2>&1 | tail -5; then
        FAILURES="$FAILURES $candidate"
    fi
done <<< "$CHANGED"

if [ -n "$FAILURES" ]; then
    echo "[precommit-test-gate] BLOCK: red tests:$FAILURES" >&2
    echo "[precommit-test-gate] 修正してから commit してください（赤コミットによる loop_health 全断の再発防止）。" >&2
    exit 1
fi

if [ "$TESTED" -eq 0 ]; then
    if [ "$CODE_SEEN" -eq 0 ]; then
        echo "[precommit-test-gate] no relevant code files changed — commit allowed"
    else
        echo "[precommit-test-gate] no matching tests (warning only) — commit allowed"
    fi
else
    echo "[precommit-test-gate] PASS: $TESTED test file(s) green"
fi
exit 0
