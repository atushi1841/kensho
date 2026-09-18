#!/usr/bin/env bash
# scripts/install_push_guard.sh — push_guard.py を git フックとして登録 (t_c2104009)
#
# 問題: worker が commit のまま push を忘れて done → guard(e) "unpushed code" で FAIL
# 対策: コミット後に自動 push する post-commit フックを登録し、
#       origin/main..HEAD == 0 の不変条件を恒常化する。
#       pre-commit 側は .pre-commit-config.yaml の local hook で防御（積み重ねブロック）。
#
# 使い方: bash scripts/install_push_guard.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS="$ROOT/.git/hooks"

if [ ! -d "$HOOKS" ]; then
    echo "error: no .git/hooks under $ROOT — is this a git repo?" >&2
    exit 1
fi

# post-commit hook: コミット成立直後に自動 push。失敗しても commit は巻き戻さない（警告のみ）。
# REPO_ROOT を動的解決することで worktree からコミットしても正しい repo/ブランチを push する。
POST="$HOOKS/post-commit"
cat > "$POST" <<'EOF'
#!/usr/bin/env bash
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$REPO_ROOT" ] || REPO_ROOT="/mnt/d/Project2/kensho"
cd "$REPO_ROOT" || exit 0
exec python3 scripts/push_guard.py --stage post-commit --workdir "$REPO_ROOT"
EOF
chmod +x "$POST"

echo "installed post-commit hook: $POST"
echo "pre-commit guard is config-driven (.pre-commit-config.yaml repo:local push-guard)."
echo "If the pre-commit bootstrap hook is missing, run: python3 -m pre_commit install"
