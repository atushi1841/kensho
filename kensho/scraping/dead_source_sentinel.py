"""Kensho Dead Source Sentinel — 収集ソースのサイレント死を検知して自動タスク投入（critic v71）

背景（実測）:
  twscrape の XClientTxId 生成失敗（X側JS変更）が 2026-09-07 11:00 頃から約50時間・
  30収集連続で発生し続けたが、graceful degradation が設計通り静かに代替へ回ったため
  誰にも検出されなかった（観測ギャップ）。

仕組み:
  収集ごとに state JSON（data/dead_source_state.json）へ
    - ソース別取得件数（new_items_by_source）
    - fixupx ステップの成功/エラー数
  を追跡し、しきい値超過で収集ログに `[DEAD-SOURCE]` を明示 + 重複排除付きで
  hermes kanban create にタスクを自動投入する。

  検出2パターン:
      1. same-zero-streak: 監視対象ソースが THRESHOLD(12) 収集連続で 0 件。
         「以前成果があったのに死んだ」（twscrape型の突然死）も、state導入以前から
         一度も成果のない「最初から死んでいた」ソース（twscrapeの実態：全433ログで
         一度も [1-9] 件なし・08-20からXClIdGen失敗）も、同じ閾値で検知する。
         前者は「要調査」、後者は「代替で代替済み・依存自体が死んでいる」旨の
         文言を分ける（ever_positive フラグで判定）。
      2. error-streak: fixupx の HTTP 404/例外が THRESHOLD(12) 収集連続で再発
         （dead URL 残存・上流障害のシグナル）。

Safety:
  - kanban CLI 失敗・state 破損時も収集本体は絶対に止めない（fail-open / rc 不変）。
  - 同一キーのタスクは 1 回だけ投入（created_tasks + hermes idempotency で重複排除、
    復帰（>0件）で解除され次の死は新タスクになる）。
  - 収集が「全ソース0件」で早期 return するケースは異常ではなく新着なしの正常運用
    であるため、カウントしない（全ソース同時死は error-streak 側で拾う）。

初回シーディング（ever_positive 判定）:
  v71導入時点で既に死んでいるソース（twscrape: 09-07から50h連続0件、しかも全ログ
  遡及で一度も成果なし）は「以前成果があった」条件を要求すると永久に検知できない。
  そのため zero_streak は ever_positive を問わず全監視対象でカウントし、文言だけ
  「突然死（要調査）」/「導入以来0件（退役 or 修正判断）」に分ける。
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

STATE_FILENAME: str = "dead_source_state.json"

# 同一ソースの連続0件 / 連続エラーこの回数でデッド宣言（critic v71 提案①の数値）
DEAD_STREAK_THRESHOLD: int = 12

# 監視対象ソース（collected.json の new_items_by_source と同じキー体系で揃える）
# knshow は v71実装時に追加: 09-08 13:00以降連続0件なのに監視外だった（twscrape型ギャップ）
_TRACKED_SOURCES: tuple[str, ...] = (
    "knshow",
    "ken-kaku",
    "kenshou.club",
    "cp.meikan",
    "ke-ma",
    "twscrape",
    "chance.com",
    "kensho-everyday",
)

_KANBAN_ASSIGNEE: str = "kensho-worker"
_KANBAN_CREATED_BY: str = "kensho-dead-source-sentinel"


def _load_state(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data: Any = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:  # noqa: BLE001 — fail-open
        pass
    return {"sources": {}, "fixupx_streak": 0, "created_tasks": {}, "last_run": ""}


def _save_state(path: Path, state: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:  # noqa: BLE001 — state保存失敗で収集を止めない
        pass


def _resolve_hermes() -> str:
    """実行可能な hermes バイナリを解決する。

    cron の PATH では /usr/local/bin/hermes（root管理・venv python不正で rc=126）が
    先頭に来る。ユーザーローカルの正常なバイナリを優先解決する（critic v71 実測対応）。
    """
    import shutil

    candidates = [
        Path.home() / ".local" / "bin" / "hermes",
        Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "hermes",
    ]
    for c in candidates:
        if c.exists() and os.access(c, os.X_OK):
            return str(c)
    found = shutil.which("hermes")
    return found or "hermes"


def _create_kanban_task(title: str, body: str, idem: str) -> tuple[bool, str]:
    """hermes kanban create でタスク投入。失敗しても例外を投げず (ok, detail) を返す。"""
    try:
        result = subprocess.run(
            [
                _resolve_hermes(),
                "kanban",
                "create",
                title,
                "--body",
                body,
                "--assignee",
                _KANBAN_ASSIGNEE,
                "--priority",
                "1",
                "--created-by",
                _KANBAN_CREATED_BY,
                "--idempotency-key",
                idem,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()[:200]
        return False, f"rc={result.returncode} {result.stderr.strip()[:200]}"
    except Exception as e:  # noqa: BLE001 — FileNotFoundError/TimeoutExpired 等
        return False, f"exec error: {e}"


def check_dead_sources(
    by_source: dict[str, int],
    fixupx_errors: int,
    fixupx_fetched: int,
    data_dir: Path,
    out: Any,
    kanban_create: Any | None = None,
) -> list[str]:
    """収集完了時に呼ぶ死活チェック。検出メッセージ（`[DEAD-SOURCE] ...`）のリストを返す。

    by_source: collected.json の new_items_by_source と同じキー体系のソース別取得数
    fixupx_errors / fixupx_fetched: Step 4 のエラー/取得数（twscrape_items 等と同様に渡す）
    data_dir: state JSON 保存先（<project_dir>/data）
    out: ログ出力コールバック
    kanban_create: 投入関数（テストで差し替え可能。None→_create_kanban_task）
    """
    out = out or (lambda m: print(m, flush=True))
    create = kanban_create or _create_kanban_task
    state_path: Path = data_dir / STATE_FILENAME
    state = _load_state(state_path)
    sources: dict[str, Any] = state.setdefault("sources", {})
    created_tasks: dict[str, Any] = state.setdefault("created_tasks", {})
    alerts: list[str] = []
    now_iso = datetime.now().isoformat(timespec="seconds")

    # 全ソース同時0件 = 「新着なし」の正常運用であり死の証拠ではない → カウントしない
    tracked_counts = [int(by_source.get(s, 0)) for s in _TRACKED_SOURCES if s in by_source]
    total_new = sum(tracked_counts)

    if by_source and total_new > 0:
        for src in _TRACKED_SOURCES:
            if src not in by_source:
                continue
            entry = sources.setdefault(src, {"zero_streak": 0, "ever_positive": False, "alerted": False})
            n = int(by_source[src])
            if n > 0:
                entry["ever_positive"] = True
                entry["zero_streak"] = 0
                entry["alerted"] = False  # 復帰したら次死で再アラート可
                created_tasks.pop(f"dead-src-{src}", None)  # 次エピソードは新タスク可
            else:
                # ever_positive を問わずカウントする: v71導入以前から死んでいるソース
                # （twscrape型）を「一度も成果なし」を理由に検知不能にしないため。
                entry["zero_streak"] = int(entry.get("zero_streak", 0)) + 1
                streak = int(entry["zero_streak"])
                if streak >= DEAD_STREAK_THRESHOLD and not entry.get("alerted"):
                    ever = bool(entry.get("ever_positive"))
                    why = (
                        f"（最終正常取得は{streak}収集前まで）— 上流変更の可能性、要調査"
                        if ever
                        else "（導入以来一度も成果なし）— ソース退役 or 修正判断が必要"
                    )
                    msg = f"[DEAD-SOURCE] {src}: {streak}収集連続で0件{why}"
                    alerts.append(msg)
                    out(msg)
                    entry["alerted"] = True
                    # idem は安定キー（ソース名のみ）: alerted フラグがエピソード単位の
                    # 抑止を担う。復帰→再死は created_tasks.pop でキーが消えるため再投入、
                    # 同一エピソード内は alerted=True で投入自体が発生しない（dupes=0）。
                    idem = f"dead-src-{src}"
                    reason = (
                        "サイト側HTML変更（セレクタ死）、X側API変更、認証切れ"
                        if ever
                        else "上流障害・恒久死（twscrape型: XClientTxId生成不能など）"
                    )
                    action = (
                        "スクレイパ更新 or ソース退役判断"
                        if ever
                        else "修正（上流依存の復旧）か退役判断。収入は代替ソースで維持。"
                    )
                    body = (
                        f"critic v71 dead-source alert（自動検出 {now_iso}）\\n\\n"
                        f"ソース `{src}` が {streak} 収集連続で新規0件です"
                        f"（{'以前は成果あり=突然死' if ever else '導入以来一度も成果なし'}）。\\n"
                        f"by_source={json.dumps(by_source, ensure_ascii=False)}\\n\\n"
                        f"想定原因: {reason}。\\n"
                        f"対応: {action}\\n"
                        f"state: {state_path}"
                    )
                    ok, detail = create(f"[dead-source] {src} が{streak}収集連続0件 — 上流調査", body, idem)
                    created_tasks[idem] = {"ok": ok, "detail": detail, "at": now_iso}
                    if not ok:
                        entry["alerted"] = False  # 投入失敗→次収集で再試行（dupesはhermes idempotencyが抑止）
                    out(f"  [DEAD-SOURCE] kanban投入({src}): {'OK' if ok else '失敗'} — {detail[:120]}")

    # fixupx エラーの連続再発（dead URL 残存 or 上流障害）
    fx_streak = int(state.get("fixupx_streak", 0))
    fx_alerted = bool(state.get("fixupx_alerted", False))
    if fixupx_errors > 0 and fixupx_fetched == 0:
        # 全滅収集のみカウント（部分的エラーは正常な混在収集で水膨れしない）
        fx_streak += 1
    elif fixupx_errors == 0:
        fx_streak = 0
        fx_alerted = False  # 復帰したら次死で再アラート可
        created_tasks.pop("dead-src-fixupx", None)
    state["fixupx_streak"] = fx_streak
    state["fixupx_alerted"] = fx_alerted
    if fx_streak >= DEAD_STREAK_THRESHOLD and not fx_alerted:
        idem = "dead-src-fixupx"
        fx_alerted = True
        state["fixupx_alerted"] = True
        msg = (
            f"[DEAD-SOURCE] fixupx: {fx_streak}収集連続でエラー{fixupx_errors}件/"
            "成功0件 — dead URL残存or上流障害、要調査"
        )
        alerts.append(msg)
        out(msg)
        body = (
            f"critic v71 dead-source alert（自動検出 {now_iso}）\n\n"
            f"fixupx フォールバックが {fx_streak} 収集連続で全件エラー（直近{fixupx_errors}件）。\n"
            f"対応: 対象URLのブラックリスト確認（data/fixupx_guard.json）、または fixupx 退役判断。\n"
            f"state: {state_path}"
        )
        ok, detail = create(f"[dead-source] fixupx が{fx_streak}収集連続全エラー — 要調査", body, idem)
        created_tasks[idem] = {"ok": ok, "detail": detail, "at": now_iso}
        if not ok:
            state["fixupx_alerted"] = False  # 投入失敗→次収集で再試行
        out(f"  [DEAD-SOURCE] kanban投入(fixupx): {'OK' if ok else '失敗'} — {detail[:120]}")

    state["last_run"] = now_iso
    _save_state(state_path, state)
    return alerts
