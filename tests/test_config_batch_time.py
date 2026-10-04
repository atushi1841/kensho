"""config.yaml の batch time が必ず文字列 "HH:MM" であることを検証する。

背景: YAML 1.1 ではクォートされていない `10:45` は sexagesimal（60進）整数 645 として
パースされる。orchestrator が batch["time"].split(":") を呼ぶため int だと AttributeError で
即死する（実測 2026-10-04: 1日59回クラッシュ）。先頭0付きの `07:35` は 8進数として不正なため
str のまま残るという非対称性があり、目視では気づけない。全件を機械的に検証する。
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def test_all_batch_times_are_hhmm_strings():
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    bad = []
    for acct in cfg.get("accounts", []):
        for batch in (acct.get("schedule") or {}).get("batches") or []:
            t = batch.get("time")
            if not isinstance(t, str) or not _TIME_RE.match(t):
                bad.append((acct.get("key"), t, type(t).__name__))
    assert not bad, f"不正な batch time（YAMLクォート漏れの疑い）: {bad}"
