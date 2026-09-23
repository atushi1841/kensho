#!/bin/bash
# Git credential helper: 環境変数の GitHub token を返す（非対話 push 用）.
#
# 使い方: git -c credential.helper= -c credential.helper=<このスクリプト> push ...
# token の供給元（優先順）:
#   1. 環境変数 GITHUB_TOKEN / GH_TOKEN
#   2. /home/atushi/.config/kensho/github-sync.env（kensho_github_sync.py が読み込む）
# このファイル自体は token を含まない（コミット可）。
[ "${1:-}" = "get" ] || exit 0

token="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
[ -n "$token" ] || exit 0

input=$(cat)
host=""
while IFS='=' read -r key value; do
  case "$key" in
    host) host="$value" ;;
  esac
done <<< "$input"

case "$host" in
  *github.com*) ;;
  *) exit 0 ;;
esac

printf 'protocol=https\nhost=%s\nusername=%s\npassword=%s\n' \
  "$host" "${GITHUB_USER:-atushi1841}" "$token"
