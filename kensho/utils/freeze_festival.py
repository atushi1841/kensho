"""
凍結祭りモニタリング（提案52, 2026-08-28）.

Xの凍結の波（凍結祭り）を日次チェックし、観測時は全垢のアクション量を
スケールダウンする。research-agent知見（2026年3/4/6/7月に凍結の波）に基づく
予防的対策。

チェックはローカルSearXNG（localhost:8888）のWeb検索で行い、X API・
セッション・ブラウザに依存しない（read-only・追加リスクなし）。
検索失敗時は fail-open（observed=False）で通常運用を継続する。

State file: data/freeze_festival_state.json
{
  "last_checked": "2026-08-28",
  "observed": false,
  "evidence": ["タイトル1", ...],
  "updated_at": "2026-08-28T01:00:00"
}

設定（config.yaml）:
freeze_festival:
  enabled: true        # falseで無効化（scale常に1.0）
  scale: 0.5           # 観測時のアクション量スケール（50%減速）
  valid_days: 3        # 観測情報の有効日数（超過で通常運用に戻る）
  search_query: "凍結祭り"  # Web検索クエリ
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

_STATE_FILE = "data/freeze_festival_state.json"


def _state_path(cfg: dict[str, Any]) -> Path:
    project_dir = cfg.get("general", {}).get("project_dir", ".")
    return Path(project_dir) / _STATE_FILE


def _fcfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("freeze_festival", {}) or {}


def load_state(cfg: dict[str, Any]) -> dict[str, Any]:
    """stateファイル読取。存在しない/壊れている場合は空状態。"""
    try:
        p = _state_path(cfg)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"last_checked": "", "observed": False, "evidence": []}


def save_state(cfg: dict[str, Any], state: dict[str, Any]) -> None:
    try:
        p = _state_path(cfg)
        p.parent.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = datetime.now().isoformat(timespec="seconds")
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_action_scale(cfg: dict[str, Any], log_fn: Callable[[str], None] | None = None) -> float:
    """凍結祭り観測中なら scale（例 0.5）、通常は1.0。state読取のみで軽量。

    - freeze_festival.enabled=False → 1.0
    - 観測情報が valid_days より古い → 1.0（通常運用に戻す）
    - 観測中 → scale
    """
    fcfg = _fcfg(cfg)
    if not fcfg.get("enabled", True):
        return 1.0
    state = load_state(cfg)
    if not state.get("observed"):
        return 1.0
    last = state.get("last_checked", "")
    valid_days = int(fcfg.get("valid_days", 3))
    try:
        last_d = datetime.strptime(last, "%Y-%m-%d").date()
    except Exception:
        return 1.0
    if (date.today() - last_d).days > valid_days:
        return 1.0
    scale = float(fcfg.get("scale", 0.5))
    if log_fn:
        log_fn(f"[FREEZE] 凍結祭り観測中（{last}確認）→ アクション量を{scale:.0%}に減速")
    return scale


def _search(query: str, timeout: float = 10.0) -> list[str]:
    """SearXNG(localhost:8888) で検索し、結果タイトル一覧を返す。失敗時は空リスト。"""
    try:
        url = "http://localhost:8888/search?" + urllib.parse.urlencode({"q": query, "format": "json"})
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        results = data.get("results", []) or []
        return [str(r.get("title", "")).strip() for r in results if r.get("title")]
    except Exception:
        return []


# 凍結祭り「発生中」を示す波キーワード（常設の解説記事とは区別する）
_WAVE_KEYWORDS = (
    "発生",
    "パージ",
    "急減",
    "多発",
    "大規模",
    "ボット",
    "前年比",
    "急増",
    "再び",
    "今度",
)
# 常設コンテンツ（解説・対策・個人アカウント）の除外キーワード
_EVERGREEN_KEYWORDS = (
    "とは",
    "原因",
    "解説",
    "対策",
    "リットリンク",
    "lit.link",
    "検索結果",
    "リアルタイム検索",
    "NEWSCAST",
)


def _is_wave_title(title: str) -> bool:
    """タイトルが「凍結祭り発生中」を示すか判定（保守的）。

    - 「凍結祭り」を含む
    - 波キーワードを1つ以上含む
    - 常設解説系キーワードを含まない
    """
    if "凍結祭り" not in title:
        return False
    if any(k in title for k in _EVERGREEN_KEYWORDS):
        return False
    return any(k in title for k in _WAVE_KEYWORDS)


def check_and_update(cfg: dict[str, Any], log_fn: Callable[[str], None] | None = None) -> bool:
    """日次チェック（1日1回のみ実行）。観測中ならTrue。

    - 当日既にチェック済み → stateのobservedを返す（再検索しない）
    - 検索結果に「凍結祭り発生中」を示すタイトルが2件以上 → observed=True
      （1件のみはノイズの可能性が高いため観測と判定しない）
    - 検索失敗（SearXNG不通等） → observed=False（fail-open）
    """
    fcfg = _fcfg(cfg)
    if not fcfg.get("enabled", True):
        return False
    state = load_state(cfg)
    today = date.today().isoformat()
    if state.get("last_checked") == today:
        return bool(state.get("observed"))
    query = str(fcfg.get("search_query", "凍結祭り"))
    titles = _search(query)
    wave_titles = [t for t in titles if _is_wave_title(t)]
    observed = len(wave_titles) >= 2
    state["last_checked"] = today
    state["observed"] = observed
    state["evidence"] = wave_titles[:5]
    save_state(cfg, state)
    if log_fn:
        log_fn(
            f"[FREEZE] 日次チェック: {'観測あり' if observed else '観測なし'}"
            f"（結果{len(titles)}件・波タイトル{len(wave_titles)}件）"
        )
    return observed
