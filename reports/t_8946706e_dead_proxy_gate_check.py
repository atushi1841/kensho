#!/usr/bin/env python3
"""t_8946706e: 本番データでのプロキシ死骸ゲート実測（読み取り専用・副作用なし）.

`data/status/<acct>.json`（proxy_watchdog が書く実運用の状態ファイル）と config.yaml を
そのまま入力し、どの垢が「応募を試行しない」判定になるかを実測する。
モックは使わない（= QA が同じコマンドで再現できる）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from kensho.core import config as kensho_config  # noqa: E402
from kensho.utils.safety import dead_proxy_accounts, dead_proxy_reason  # noqa: E402


def main() -> int:
    cfg = kensho_config.load()
    project_dir = Path(cfg["general"]["project_dir"])
    print(f"project_dir={project_dir}")
    print(f"safety.dead_proxy_check={cfg.get('safety', {}).get('dead_proxy_check')}")
    print(f"safety.dead_proxy_max_age_hours={cfg.get('safety', {}).get('dead_proxy_max_age_hours', 6)}")
    rows = []
    for acct in cfg.get("accounts", []):
        key = str(acct.get("key") or "")
        if not key:
            continue
        sp = project_dir / "data" / "status" / f"{key}.json"
        st: dict = {}
        if sp.exists():
            try:
                st = json.loads(sp.read_text(encoding="utf-8"))
            except Exception:
                st = {}
        reason = dead_proxy_reason(cfg, key)
        rows.append((key, str(st.get("status", "-")), str(st.get("updated", "-")),
                     "SKIP" if reason else "allow", reason))
    for key, status, updated, gate, reason in rows:
        print(f"  {key:16s} status={status:11s} updated={updated:26s} gate={gate}"
              + (f"  reason={reason}" if reason else ""))
    print(f"dead_proxy_accounts={dead_proxy_accounts(cfg)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
