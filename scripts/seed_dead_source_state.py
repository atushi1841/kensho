"""critic v71 導入時シーディング: logs/collect_*.log を遡及して data/dead_source_state.json を初期化。

背景:
  デッドソースセンチネルの zero_streak は state JSON が白紙のままだと収集ごとに 1 ずつ
  しか増えない。twscrape は導入以前から約30収集連続0件（実態は08-20から恒久死）なので、
  シードなしだと検知が導入後さらに12収集（≈1日）遅れる。過去ログの Step 3 行
  「[Step 3] 結果保存... (knshow 6件, ken-kaku 14件, ..., 計319件)」をパースして
  真の連続0件streakと ever_positive を再現する。

使い方:
  python scripts/seed_dead_source_state.py [--dry-run]

注意:
  - 既存 state がある場合は上書きしない（--force で明示上書き）。
  - 収集本体には干渉しない。fail-safe: パース不能ログは読み飛ばす。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_DIR / "logs"
STATE_PATH = PROJECT_DIR / "data" / "dead_source_state.json"

_STEP3_RE = re.compile(r"\[Step 3\] 結果保存.*?\((.+?)\)")
_PAIR_RE = re.compile(r"([a-z0-9.\-]+(?:\.[a-z\-]+)?) (\d+)件")

# 監視対象（dead_source_sentinel._TRACKED_SOURCES と必ず一致させる）
TRACKED = (
    "knshow",
    "ken-kaku",
    "kenshou.club",
    "cp.meikan",
    "ke-ma",
    "twscrape",
    "chance.com",
    "kensho-everyday",
)


def _parse_log(path: Path) -> dict[str, int] | None:
    """Step 3 行からソース別件数を抽出。見つからなければ None。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = _STEP3_RE.search(text)
    if not m:
        return None
    pairs = {k: int(v) for k, v in _PAIR_RE.findall(m.group(1)) if k != "計"}
    return pairs or None


def build_state(force: bool = False) -> dict[str, Any]:
    if STATE_PATH.exists() and not force:
        raise SystemExit(f"state が既に存在します: {STATE_PATH}\n上書きするなら --force を付けて再実行してください。")
    logs = sorted(LOG_DIR.glob("collect_2026*.log"))
    parsed: list[dict[str, int]] = []
    for lp in logs:
        p = _parse_log(lp)
        if p is not None:
            parsed.append(p)

    sources: dict[str, Any] = {}
    for src in TRACKED:
        zero_streak = 0
        ever_positive = False
        for p in reversed(parsed):
            if src not in p:
                continue
            if p[src] > 0:
                ever_positive = True
                break
            zero_streak += 1
        sources[src] = {
            "zero_streak": zero_streak,
            "ever_positive": ever_positive,
            "alerted": False,
        }
    return {
        "sources": sources,
        "fixupx_streak": 0,
        "fixupx_alerted": False,
        "created_tasks": {},
        "last_run": "seeded-from-logs",
        "seed_note": f"scripts/seed_dead_source_state.py from {len(parsed)}/{len(logs)} logs",
    }


def main() -> int:
    force = "--force" in sys.argv
    dry = "--dry-run" in sys.argv
    state = build_state(force=force)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    if dry:
        print("(dry-run: 書込みなし)")
        return 0
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {STATE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
