from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

DEFAULT_DB = "/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db"
DEFAULT_REPO = Path("/mnt/d/Project2/kensho")
DEFAULT_DAYS = 7
TARGET_RATE = 50.0

OUTCOME_REQUIRED_KEYS = ("metric", "before", "after")
_NUMERIC_KPI_RE = re.compile(r"[0-9]+\s*(%|％|件|本|回|円|B|GB|MB|KB|秒|分|人|日|倍|点)")

# 極性語彙: lower is better → 失敗/エラー/回数/秒/exit_code/残数 等
_LOWER_IS_BETTER = re.compile(
    r"(失敗|エラー|回数|秒|exit_code|残数|miss|retry|login_attempt|goto_failed|connect_timeout|timeout"
    r"|goto failed|failed 件数|parse_error|不一致|乖離|誤報告|誤検知|呼び出し|呼出箇所|diff 行数|exit code"
    r"|ログイン試行|elapsed|seconds|skip|スキップ|失敗率)",
    re.I,
)
# higher is better → 成功率/Score/AP/Value/Progress/Growth/Revenue/倍/点
_HIGHER_IS_BETTER = re.compile(
    r"(成功率|Score|AP|Value|Progress|Growth|Revenue|倍|点|percent|Rate|RPU"
    r"|passed|passing|spans_valid|endpoints|実測|計測|投稿|宣言|回帰|エントリ数|配線|ステップ|日数"
    r"|記録率|確認率|検出率|有効|復帰率|復旧率|達成率|完了率|検出件数|emitted|blocked|spans)",
    re.I,
)
# ※「件」は入れない: 「総件数」のように up=良 と言えない指標に誤爆し、偽の「悪化疑い」を作る。
#   （2026-09-25 t_e07dab2a のテスト実測: 総件数 10→5 が unknown こと）。
# ※「率」も単体では入れない: 「失敗率」は down だが「記録率」「確認率」は up。率系は
#   _DIRECTION_PATTERNS の優先順で具体的複合語として先評価し、「失敗」の誤爆を防ぐ。
#   （2026-09-26 t_fa208e37: 「push失敗の理由記録率 0→100」が「失敗」で down→悪化疑いに
#   誤認されたのを修正。実際は記録率の上昇＝改善。）
# 単位：equal（変化なし）または決定不能

# 方向推測の優先順。より具体的な複合語を先に評価し、一般語の誤爆を防止する。
# - up 率系（記録率/確認率/検出率/復帰率 等）を「失敗」より先に判定する。
# - 「検出率|検出件数」は up だが「検出回数」は down（スキップ検出の発生回数）のため、
#   「検出」単体ではなく「検出率|検出件数」に絞る（「圏外垢応募前スキップ…検出回数」対策）。
# - 「行数」単体は入れない（「diff 行数」=down と「方向: 行数」=up が混在するため、
#   「方向: 行数」のみを明示的 up パターンとして優先判定する）。
# - elapsed/seconds/sec/回数/件数 などの「数量が増える=悪化」系を「実測/計測」等の up 系より
#   先に判定し、「1失敗あたり実測試行回数」「step1_elapsed_sec」等の誤判定を防ぐ。
# - 語境界を意識: 「ステップ」は単語として独立している場合のみ up（「step1_elapsed_sec」の
#   step にはマッチさせない）。投稿数/日数/宣言系統数/ケース数/検証ケース数 等は
#   具体的複合語として先評価し、裸の「数/件数/回数」は判定しない。
# - 「Revenue」「Rate」「AP」等の英単語は語境界必須（「revenue_collect」「elapsed」「pricing」に誤爆防止）。
# - 日本語語境界(\b)は日本語間で効かないため、明示的複合語（発動件数/発動回数 等）で判定する。
# - 「カウンタ/counter/scripts/diff」等は独立語または明確な複合語のみ（"failure-ceiling counter"、"diff 行数" に誤爆防止）。
# - 「cache/pricing/coverage/data」は具体的複合語のみ（単体で up とは限らないため）。
# - 「件数」単体は down だが、データ充実を表す複合語（全件数/pricing 件数/cache 件数/データ件数/カバレッジ件数 等）は up として先評価する。
# - 「発動/起動/稼働/復旧/復元/復帰/縮退」は明確な複合語（発動件数/発動回数/稼働数 等）のみ。
# - 「成功/誤検知/誤報告」は件数/回数が減る=改善（up）として先評価する。
_DIRECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # --- higher is better: 明確な up 系（率・達成系・明確な改善指標）を最優先 ---
    # 「方向:` 行数」「方向： 行数」等のバッククォート/全角コロン付きも拾う
    # ※バッククォートで囲まれた `方向:` も拾う
    (
        re.compile(
            r"(記録率|確認率|検出率|有効|復帰率|復旧率|達成率|完了率|成功率|当選率|検出件数|`方向:`\s*行数|方向[：:`]\s*行数)",
            re.I,
        ),
        "up",
    ),
    # 「発動/起動/稼働/復旧/復元/復帰/縮退」等の明確な複合語：「機能している」指標は up。
    # 「self_heal 発動件数 0→36」「システム稼働数 3→5」等。裸の「発動」等では判定しない（「縮退の有無」対策）。
    (
        re.compile(
            r"(発動件数|発動回数|発動数|起動件数|起動回数|稼働件数|稼働回数|稼働数|復旧件数|復旧回数|復元件数|復元回数|復帰件数|復帰回数|縮退件数|縮退回数|活性化件数|活性化回数)",
            re.I,
        ),
        "up",
    ),
    # カウンタ/スクリプト/ファイル/カード/エントリ/diff/set/check/test 系の「数が減る=整理された」指標は up。
    # 「bare hermes 実行呼出箇所数 6→0」「complete_watchdog 誤検知件数 54→0」等。
    # 「counter/scripts/diff」単体は判定せず、明確な複合語（呼出箇所数/スクリプト数/ファイル数/card数/エントリ数/diff数/set数/check数/test数 等）のみ。
    # ※「diff 行数」は down（行数が減る=改善）のため除外。
    (
        re.compile(
            r"(呼出箇所数|スクリプト数|ファイル数|カード数|エントリ数|diff数|set数|check数|test数|counter数)\b",
            re.I,
        ),
        "up",
    ),
    # 投稿数/日数/宣言系統数/実測ケース数/検証ケース数/endpoints数/回帰テスト数/ステップ数 等
    # ※「ステップ数」は語境界で独立語のみ（「step1_elapsed_sec」の step にはマッチさせない）
    (
        re.compile(
            r"(投稿数|日数|宣言系統数|ケース数|検証ケース数|実測ケース数|endpoints数|回帰テスト数|ステップ数\b|エントリ数"
            r"|配線箇所数|spans_valid|回帰テスト数)",
            re.I,
        ),
        "up",
    ),
    (
        re.compile(
            r"(passed|passing|spans_valid|endpoints|emitted|blocked|spans|投稿|宣言"
            r"|回帰|エントリ数|配線|ステップ|日数)",
            re.I,
        ),
        "up",
    ),
    (re.compile(r"(Score|AP\b|Value|Progress|Growth|Revenue\b|Rate\b|RPU|倍|点|percent)", re.I), "up"),
    # 「全件/全エントリ/全ファイル/全カード/カバレッジ/網羅/完全性/pricing/cache/データ」系の「件数/数が増える=データが充実した」指標は up。
    # 「apify_pricing_cache の pricing 件数 1→25」「全エントリ数 100→120」「cache件数 50→100」等。
    # 具体的複合語のみ（単体の pricing/cache/data は up とは限らないため除外）。
    # ※スペース付き「pricing 件数」も拾うため \s* を許容
    (
        re.compile(
            r"(全件数|全エントリ数|全ファイル数|全カード数|カバレッジ件数|網羅件数|完全性件数|pricing\s*件数|cache\s*件数|データ件数|coverage\s*件数)\b",
            re.I,
        ),
        "up",
    ),
    # 「成功回数/成功件数」は up（「成功」が「回数」より先にマッチするよう先評価）。
    # 「complete_watchdog 誤検知件数 54→0」は「誤検知」で down に誤爆するため、
    # 「誤検知件数/誤報告件数」自体を up として先評価する（偽陽性の件数が減る=改善）。
    (
        re.compile(
            r"(成功回数|成功件数|成功|誤検知件数|誤報告件数|誤検知|誤報告)",
            re.I,
        ),
        "up",
    ),
    # --- lower is better: 時間・回数・件数・失敗系を up 系「実測/計測」より先に ---
    (
        re.compile(
            r"(失敗率|failed\b|failed 件数|goto failed|skip|スキップ|parse_error|不一致|乖離|誤報告|誤検知"
            r"|呼び出し|呼出箇所|diff 行数|exit code|ログイン試行|elapsed|seconds?|sec\b"
            r"|失敗|エラー|回数|件数|秒|exit_code|残数|miss|retry|login_attempt|goto_failed|connect_timeout|timeout"
            r"|attempts|invocations|failures|retries|trials|checks?|\bcount\b)",
            re.I,
        ),
        "down",
    ),
    # 誤検知件数/誤報告件数/failed 件数 等の具体的複合語も down（上のパターンで漏れるケース対策）
    # ※「誤検知件数/誤報告件数」は up パターンで先に拾うためここには来ない
    # 「counter/scripts」単体も独立語なら down（数が減る=改善: 共有counter数減少、スクリプト数減少等）
    (
        re.compile(
            r"(failed 件数|parse_error 件数|再実行件数|検出回数|到達件数|呼び出し数|呼出箇所数|試行回数|ログイン回数|行数|キー数|総数|箇所数|呼び出し総数|\bcounter\b|\bscripts\b)",
            re.I,
        ),
        "down",
    ),
    # --- higher is better: 実測/計測/検証等（失敗/回数/件数/秒 より後で評価） ---
    (
        re.compile(r"(実測|計測|検証)", re.I),
        "up",
    ),
]


def _md_before_after_patterns() -> list[re.Pattern[str]]:
    """検証セクションの before→after 数値パターン（ガード条件(k) と同一）。"""
    num = r"-?\d+(?:[,.]\d+)?"
    unit = r"[%％,.;×x]?"
    return [
        re.compile(rf"before\s*[=:]\s*{num}{unit}\s*(?:→|->|から)?\s*after\s*[=:]\s*{num}{unit}", re.I),
        re.compile(rf"{num}\s*%\s*→\s*{num}\s*%"),
        re.compile(rf"改善前[：:]\s*{num}{unit}.*?改善後[：:]\s*{num}{unit}"),
        re.compile(rf"改修前[：:]\s*{num}{unit}.*?改修後[：:]\s*{num}{unit}"),
    ]


def looks_numeric_kpi(text: str) -> bool:
    """成功指標文字列が数値KPI（%・件・円 等）を含むか。"""
    return bool(_NUMERIC_KPI_RE.search(text or ""))


def outcome_entries(evidence_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """evidence.json の outcome フィールドを正規化して返す（単一dict / list 両対応）。"""
    if not isinstance(evidence_data, dict):
        return []
    raw = evidence_data.get("outcome")
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]


def _entries_complete(entries: list[dict[str, Any]]) -> bool:
    """全エントリが metric/before/after を持ち before/after が数値か。"""
    if not entries:
        return False
    for e in entries:
        if not all(k in e for k in OUTCOME_REQUIRED_KEYS):
            return False
        if not isinstance(e.get("before"), (int, float)) or isinstance(e.get("before"), bool):
            return False
        if not isinstance(e.get("after"), (int, float)) or isinstance(e.get("after"), bool):
            return False
    return True


def detect_md_before_after(evidence_text: str) -> list[str]:
    """検証セクション中の before→after 数値パターンにマッチした pattern を返す。"""
    hits: list[str] = []
    for p in _md_before_after_patterns():
        if p.search(evidence_text or ""):
            hits.append(p.pattern)
    return hits


def classify(evidence_text: str, evidence_data: dict[str, Any] | None) -> dict[str, Any]:
    """1タスクの事後効果測定状態を判定する（ガード条件(k) と同一規則）。

    status: pass / missing / na
    """
    entries = outcome_entries(evidence_data)
    md_hits = detect_md_before_after(evidence_text)
    outcome_ok = _entries_complete(entries)

    if outcome_ok or md_hits:
        return {
            "status": "pass",
            "outcome_ok": outcome_ok,
            "md_hits": md_hits,
            "entries": entries,
            "note": "before/after comparable metric present",
        }

    indicators: list[str] = []
    if isinstance(evidence_data, dict):
        si = evidence_data.get("success_indicators")
        if isinstance(si, list):
            indicators = [str(x) for x in si if x is not None]
    has_numeric_kpi = any(looks_numeric_kpi(s) for s in indicators)
    if not has_numeric_kpi:
        return {
            "status": "na",
            "outcome_ok": False,
            "md_hits": [],
            "entries": [],
            "note": "no numeric KPI in success_indicators (outcome review not applicable)",
        }
    return {
        "status": "missing",
        "outcome_ok": False,
        "md_hits": [],
        "entries": [],
        "note": "numeric success_indicators present but before/after real metrics missing",
    }


def auto_direction_from_metric(metric: str) -> str | None:
    """KPI名（例: 失敗回数、成功率）から方向を推測。

    lower is better (方向: down) と higher is better (方向: up) を返す。
    未知の場合は None。

    判定は _DIRECTION_PATTERNS の優先順に従う。より具体的な複合語を先に評価し、
    一般語（例: 「失敗」）の誤爆を防止する。たとえば「push失敗の理由記録率」は
    「記録率」が up として優先判定され、「失敗」で down に誤認されない。
    """
    for pattern, direction in _DIRECTION_PATTERNS:
        if pattern.search(metric):
            return direction
    return None


def partition_outcomes(
    entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """数値KPIエントリを「悪化疑い」と「方向未宣言」に**単一規則**で振り分ける。
    - 分母（操作開始数、収集run数等）が5件未満のKPIは統計的有意性なしとして方向未宣言から除外し、証拠として「統計的意味なし(n/a)」フラグを付けてdirection=equal扱いとする。
    - 方向未宣言時のみ metric 名の極性語彙で自動補完し、補完できた場合のみ悪化判定。
    """
    regressed: list[dict[str, Any]] = []
    undeclared: list[dict[str, Any]] = []
    for e in entries:
        b, a = e.get("before"), e.get("after")
        if not isinstance(b, (int, float)) or isinstance(b, bool):
            continue
        if not isinstance(a, (int, float)) or isinstance(a, bool):
            continue
        direction = e.get("direction")
        if direction == "equal":
            continue
        if direction not in ("up", "down"):
            # 未宣言 or 未知の direction 値 → metric 名から自動補完
            direction = auto_direction_from_metric(str(e.get("metric", "")).lower())
        # 分母閾値チェック: evidence.jsonのnoteに「分母N件」の記述があるか、Nが5未満と推定される場合
        note = str(e.get("note", "") or "")
        denom_match = (
            re.search(r"分母(\d+)件", note)
            or re.search(r"分母は(\d+)操作開始のみ", note)
            or re.search(r"denominator (\d+) items?", note.lower())
        )
        if denom_match:
            denom = int(denom_match.group(1))
            if denom < 5:
                # 統計的有意性なしとして方向未宣言扱い
                e["direction"] = "equal"
                e["note"] = f"{note} 統計的意味なし(n/a)"
                undeclared.append(e)
                continue
        if direction == "down":
            if a > b:
                regressed.append(e)
        elif direction == "up":
            if a < b:
                regressed.append(e)
        else:
            undeclared.append(e)
    return regressed, undeclared


def regressions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """「悪化疑い」のみを返す（partition_outcomes の後方互換ラッパ）。"""
    return partition_outcomes(entries)[0]


def direction_label(before: Any, after: Any) -> str | None:
    """数値before/afterの移動方向を返す。良悪ではなく上下のみを意味する。"""
    if not isinstance(before, (int, float)) or isinstance(before, bool):
        return None
    if not isinstance(after, (int, float)) or isinstance(after, bool):
        return None
    if after < before:
        return "方向: down"
    if after > before:
        return "方向: up"
    return "方向: equal"


def format_outcome_entry(entry: dict[str, Any]) -> str:
    """KPIのbefore→afterを表示し、数値時には上下を明記する。"""
    metric = str(entry.get("metric", "KPI"))
    before = entry.get("before")
    after = entry.get("after")
    change = f"{before}→{after}"
    direction = direction_label(before, after)
    suffix = f" ({direction})" if direction else ""
    return f"{metric} {change}{suffix}"


def fetch_done_tasks(db_path: Path, since_epoch: int, limit: int = 200) -> list[dict[str, Any]]:
    """completed_at >= since_epoch の done タスクを取得する。"""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.execute(
            "SELECT id, title, assignee, completed_at, result FROM tasks "
            "WHERE status='done' AND completed_at IS NOT NULL AND completed_at >= ? "
            "ORDER BY completed_at DESC LIMIT ?",
            (since_epoch, limit),
        )
        rows = cur.fetchall()
    finally:
        con.close()
    tasks: list[dict[str, Any]] = []
    for tid, title, assignee, completed_at, result in rows:
        tasks.append(
            {
                "id": str(tid),
                "title": str(title or ""),
                "assignee": str(assignee or ""),
                "completed_at": int(completed_at),
                "completed_date": _dt.datetime.fromtimestamp(int(completed_at)).strftime("%Y-%m-%d"),
                "result": str(result or ""),
            }
        )
    return tasks


def find_evidence(reports_dir: Path, task_id: str) -> Path | None:
    """reports/<task_id>_evidence.json を優先し、無ければ *<task_id>*evidence*.json を探す。"""
    exact = reports_dir / f"{task_id}_evidence.json"
    if exact.is_file():
        return exact
    cands = sorted(p for p in reports_dir.glob(f"*{task_id}*evidence*.json") if p.is_file())
    return cands[0] if cands else None


def find_verification(reports_dir: Path, task_id: str) -> Path | None:
    """reports/<task_id>_verification.md を優先し、無ければ *<task_id>*.md を探す。"""
    exact = reports_dir / f"{task_id}_verification.md"
    if exact.is_file():
        return exact
    cands = sorted(
        p for p in reports_dir.glob(f"*{task_id}*.md") if p.is_file() and "evidence" not in p.name
    )
    return cands[0] if cands else None


def audit_task(task: dict[str, Any], reports_dir: Path) -> dict[str, Any]:
    """1タスクを監査して判定結果を返す。"""
    tid = str(task["id"])
    ev_path = find_evidence(reports_dir, tid)
    md_path = find_verification(reports_dir, tid)

    evidence_data: dict[str, Any] | None = None
    if ev_path is not None:
        try:
            loaded = json.loads(ev_path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(loaded, dict):
                evidence_data = loaded
        except (json.JSONDecodeError, OSError):
            evidence_data = None

    evidence_text = ""
    if md_path is not None:
        try:
            evidence_text = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            evidence_text = ""

    state = classify(evidence_text, evidence_data)
    entries = state.get("entries") or []
    # 判定は partition_outcomes に一元化（悪化疑いと方向未宣言が別規則で乖離しないように）
    regressed, direction_undeclared = partition_outcomes(entries)

    return {
        "id": tid,
        "title": task["title"],
        "assignee": task["assignee"],
        "completed_date": task["completed_date"],
        "evidence_path": str(ev_path) if ev_path else None,
        "verification_path": str(md_path) if md_path else None,
        "status": state["status"],
        "outcome": entries,
        "regressions": regressed,
        "direction_undeclared": direction_undeclared,
        "note": state["note"],
    }


def summarize(records: list[dict[str, Any]], days: int, since_date: str) -> dict[str, Any]:
    """集計サマリを組み立てる。"""
    measured = [r for r in records if r.get("status") == "pass"]
    missing = [r for r in records if r.get("status") == "missing"]
    na = [r for r in records if r.get("status") == "na"]
    denom = len(measured) + len(missing)
    rate = (100.0 * len(measured) / denom) if denom else None

    # regressed は regressions フィールドから
    regressed_count = sum(1 for r in records if r.get("regressions"))
    direction_undeclared_count = sum(1 for r in records if r.get("direction_undeclared"))

    return {
        "days": days,
        "since": since_date,
        "counts": {
            "done": len(records),
            "measured": len(measured),
            "missing": len(missing),
            "na": len(na),
            "numeric_kpi_tasks": denom,
            "regressed": regressed_count,
            "direction_undeclared": direction_undeclared_count,
        },
        "measured_rate": rate,
        "target_rate": TARGET_RATE,
        "target_met": bool(rate is not None and rate >= TARGET_RATE),
        "measured": measured,
        "missing": missing,
        "na": na,
        "regressions": [r for r in records if r.get("regressions")],
        "direction_undeclared": [r for r in records if r.get("direction_undeclared")],
        "tasks": records,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    """critic プロンプト注入用のコンパクトな markdown を組み立てる。"""
    c = summary["counts"]
    rate = summary["measured_rate"]
    rate_txt = "n/a" if rate is None else f"{rate:.1f}%"
    lines = [
        f"### 事後効果測定（Outcome Review / 過去{summary['days']}日 done）",
        "- KPI方向性ルール: 各 before→after の末尾に `(方向: up/down/equal)` を明記する。"
        " この語は数値の上下のみを表し、良悪は指標の意味に依存する"
        "（例: 失敗回数・試行回数・所要秒数の down は改善 / 未pushコミット残数の up は悪化）。",
        f"- 対象: done={c['done']}件（{summary['since']}以降）/ 数値KPIあり={c['numeric_kpi_tasks']}件",
        f"- 実測確認: あり={c['measured']}件 / 未実測={c['missing']}件 / KPI非該当={c['na']}件",
        f"- 実測確認率: {rate_txt}（目標>{summary['target_rate']:.0f}%）"
        f" → {'達成' if summary['target_met'] else '未達'}",
    ]

    # 実測済みタスク（主内容）を警告より先に置く。各エントリに (方向: up/down/equal) を付ける。
    # 表示順は 実測済み → 警告 → 未実測。順序に依存するテスト（方向付与の全件検査）がこの前提。
    if summary["measured"]:
        lines.append("- 実測済みタスク:")
        for r in summary["measured"][:10]:
            if r["outcome"]:
                detail = ", ".join(format_outcome_entry(e) for e in r["outcome"])
            else:
                detail = "検証セクションに before→after 記載"
            lines.append(f"  - `{r['id']}` {detail}")

    # regressed + direction_undeclared をまとめて表示
    total_warnings = c.get("regressed", 0) + c.get("direction_undeclared", 0)
    if total_warnings > 0:
        lines.append(f"- ⚠️ after<before: {total_warnings}件（悪化疑い {c.get('regressed', 0)}件 / 方向未宣言 {c.get('direction_undeclared', 0)}件）")
    
    if c["regressed"]:
        lines.append("- 悪化疑いの詳細:")
        for r in summary["regressions"][:10]:
            for e in r["regressions"]:
                lines.append(f"  - `{r['id']}` {format_outcome_entry(e)}")
    
    if c.get("direction_undeclared", 0) > 0:
        lines.append("- 方向未宣言の詳細:")
        for r in summary.get("direction_undeclared", [])[:10]:
            for e in r["direction_undeclared"]:
                metric = str(e.get("metric", "KPI"))
                before = e.get("before")
                after = e.get("after")
                note = e.get("note", "")
                suffix = f" (方向未宣言)" + (f" [{note}]" if "統計的意味なし" in note else "")
                lines.append(f"  - `{r['id']}` {metric} {before}→{after}{suffix}")
    
    if summary["missing"]:
        lines.append("- 未実測タスク（before/after の数値を追記してクローズすること）:")
        for r in summary["missing"][:10]:
            lines.append(f"  - `{r['id']}` {r['title'][:60]}（{r['assignee']}）")
    
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Outcome Review 定期再確認（過去N日 done タスク）")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS, help="遡る日数（既定7）")
    ap.add_argument("--db", type=Path, default=Path(DEFAULT_DB), help="kanban DB パス")
    ap.add_argument("--reports-dir", type=Path, default=DEFAULT_REPO / "reports")
    ap.add_argument("--limit", type=int, default=200, help="取得する done タスク上限")
    ap.add_argument("--json", action="store_true", help="JSON で出力")
    ap.add_argument("--write-report", action="store_true", help="reports/outcome-review-<date>.md に保存")
    ap.add_argument("--strict", action="store_true", help="実測確認率が目標未達なら exit 1")
    args = ap.parse_args(argv)

    if not args.db.is_file():
        print(f"[outcome_review_check] kanban DB が見つかりません: {args.db}", file=sys.stderr)
        return 3

    now = _dt.datetime.now()
    since = now - _dt.timedelta(days=args.days)
    since_date = since.strftime("%Y-%m-%d")
    records = [audit_task(t, args.reports_dir) for t in fetch_done_tasks(args.db, int(since.timestamp()), args.limit)]
    summary = summarize(records, args.days, since_date)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(summary))

    if args.write_report:
        args.reports_dir.mkdir(parents=True, exist_ok=True)
        out = args.reports_dir / f"outcome-review-{now.strftime('%Y-%m-%d')}.md"
        body = [
            f"# Outcome Review 定期再確認 {now.strftime('%Y-%m-%d')}",
            "",
            f"対象: 過去{args.days}日間（{since_date}以降）に done になったタスク",
            "",
            render_markdown(summary),
            "",
            f"- 検証コマンド: `grep -c \"方向:\" reports/{out.name}`（≥5 で KPI方向性ルールの適用を確認）",
            "",
        ]
        out.write_text("\n".join(body), encoding="utf-8")
        if not args.json:
            print(f"\n- レポート保存: {out}")

    if args.strict and summary["measured_rate"] is not None and not summary["target_met"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())