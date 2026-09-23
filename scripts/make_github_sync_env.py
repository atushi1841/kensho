"""GCM(Windows) から GitHub credential を取り出し、WSL 側の env ファイルへ保存する.

- token は標準出力に一切出さない（長さと prefix のみ）。
- 出力ファイルはリポジトリ外・chmod 600。
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

HELPER = "/home/atushi/.git-credential-helper-wsl.sh"
ENV_FILE = Path("/home/atushi/.config/kensho/github-sync.env")


def main() -> int:
    p = subprocess.run([HELPER, "get"], input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True, timeout=60)
    cred: dict[str, str] = {}
    for line in p.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            cred[k] = v
    token = cred.get("password", "").strip()
    user = cred.get("username", "atushi1841").strip()
    if not token:
        print("[err] helper から credential を取得できませんでした")
        return 1
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(ENV_FILE.parent, 0o700)
    body = (
        "# Kensho github_sync 用 credential（リポジトリ外・git 管理外）\n"
        "# 非対話 push 用。ここにある値をコミット/貼り付けしないこと。\n"
        "# 生成: scripts/make_github_sync_env.py\n"
        f"GITHUB_USER={user}\n"
        f"GITHUB_TOKEN={token}\n"
    )
    ENV_FILE.write_text(body, encoding="utf-8")
    os.chmod(ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)
    st = ENV_FILE.stat()
    print(f"[ok] wrote {ENV_FILE} mode={oct(st.st_mode & 0o777)} user={user} token_len={len(token)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
