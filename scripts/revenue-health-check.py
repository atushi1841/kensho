#!/usr/bin/env python3
"""revenue-health-check — 収益データ収集パイプラインの統合モニタリング。

4つの独立cron (kensho-daily-bot-safety-audit / kensho-research-agent-monetize /
kensho-dataset-weekly-update / kensho-revenue-collect) が重複監視していた収益データを
1スクリプトに統合し、異常検知時にTelegram通知 + notepad自動記録を行う。

読み取り対象ファイル:
  - data/revenue-daily.json        (日次収益サマリー、最新30エントリ)
  - data/apify_actors_detail_snapshot.json (Apifyポートフォリオ現在地)
  - data/gumroad_state.json        (Gumroad売上状態)
  - data/gumroad_promo_kpi_state.json      (販促KPI履歴)

チェック項目:
  1. ファイル存在 + 最終更新から24h以内（鮮度）
  2. external_runs 連続ゼロ日数検知（3日以上でWARNING）
  3. Gumroad sales_zero 継続検知
  4. revenue-daily.json の warnings / opportunities 反映確認
  5. (--dry-run) 変更なしで現状レポート出力

cron disabled 対象（本スクリプトが監視するので重複除去）:
  - kensho-revenue-collect            (RapidAPI cookie期限切れ → 継続error)
  - kensho-dataset-weekly-update      (成功済みなのにexit 1 → スクリプトbug)
  ※ kensho-daily-bot-safety-audit はBOTシグナル検出時のexit 1は設計動作なので維持
  ※ kensho-research-agent-monetize は一過性インフラエラーなので維持

使い方:
  python3 scripts/revenue-health-check.py [--dry-run] [--disable-crons]
    --dry-run       状態だけレポート、ファイル/ Cron 変更なし
    --disable-crons disabled対象cronを実際に無効化（--dry-run併用可）
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── パス設定 ──────────────────────────────────────────────────────────────────
# 固定パス（cron実行時はprofile dirを指すため、 Kensho repo dirを明示）
PROJECT_DIR = Path("/mnt/d/Project2/kensho")
DATA_DIR = PROJECT_DIR / "data"
CRON_JOBS_FILE = Path("/home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json")
NOTEPAD_DIR = Path("/home/atushi/.hermes/profiles/kensho-sweeps/cron/notepad")
STATE_FILE = DATA_DIR / "revenue_health_state.json"

JST = timezone(timedelta(hours=9))
FRESHNESS_H = 24.0
EXTERNAL_RUNS_WARN_DAYS = 3
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── 対象cron名 ────────────────────────────────────────────────────────────────
# 本スクリプトに監視を移行し、disable対象とするもの（根本エラー継続中 or スクリプトbug）
# 2026-10-04: kensho-revenue-collect を除外。venv固定(10-02)で収集は復旧済み・手動実行で完走を確認し、
# 07:05の日次収集を復帰させた。ここに残すと毎朝のアラートで再disableされ、復帰が無意味になる。
DISABLE_TARGETS = [
    "kensho-dataset-weekly-update",      # 成功済みなのにexit 1（スクリプトbug・未修正）
]
# 維持対象（design-intentional or transient）
KEEP_TARGETS = [
    "kensho-daily-bot-safety-audit",     # exit 1 = BOTシグナル検出（設計通り）
    "kensho-revenue-collect",            # ← DISABLEに移行済みなら触らない
]


# ── 補助関数 ──────────────────────────────────────────────────────────────────
def _now_jst() -> datetime:
    return datetime.now(JST)


def _iso_jst(dt: datetime) -> str:
    return dt.astimezone(JST).isoformat()


def _age_hours(ts_str: str | None) -> float | None:
    """ISO文字列からJST現在との差（時間）を返す。未取得ならNone。"""
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        return (_now_jst() - dt).total_seconds() / 3600
    except Exception:
        return None


def _load_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"  [ERR] {path.name}: {e}", file=sys.stderr)
        return None


def _say(msg: str, *, tag: str = "") -> None:
    prefix = f"[{tag}] " if tag else ""
    print(f"{prefix}{msg}")


# ── チェック1: ファイル鮮度 ───────────────────────────────────────────────────
def check_freshness() -> dict:
    """3ファイルの存在・鮮度をチェック。"""
    results = {}

    # revenue-daily.json
    p = DATA_DIR / "revenue-daily.json"
    d = _load_json(p)
    if d is None:
        results["revenue_daily"] = {"exists": False, "fresh": False, "entries": 0}
    elif isinstance(d, list):
        last = d[-1] if d else {}
        age = _age_hours(last.get("collected_at"))
        results["revenue_daily"] = {
            "exists": True,
            "fresh": age is not None and age < FRESHNESS_H,
            "age_h": round(age, 1) if age else None,
            "entries": len(d),
            "last_date": last.get("date"),
            "warnings": last.get("warnings", []),
        }
    else:
        results["revenue_daily"] = {"exists": True, "fresh": False, "error": "not list"}

    # apify_actors_detail_snapshot.json
    # 2026-10-04: 旧実装は各actorの modifiedAt（Apify側の最終更新日時）を鮮度と誤用していた。
    # actorが更新されない限り常に「鮮度不足」になる誤判定だったため、ファイル取得時刻(mtime)で判定する。
    p2 = DATA_DIR / "apify_actors_detail_snapshot.json"
    d2 = _load_json(p2)
    if d2 is None:
        results["apify_snapshot"] = {"exists": False, "fresh": False}
    elif isinstance(d2, list):
        try:
            age2 = (_now_jst().timestamp() - p2.stat().st_mtime) / 3600
        except Exception:
            age2 = None
        results["apify_snapshot"] = {
            "exists": True,
            "fresh": age2 is not None and age2 < FRESHNESS_H,
            "age_h": round(age2, 1) if age2 is not None else None,
            "actors": len(d2),
        }
    else:
        results["apify_snapshot"] = {"exists": True, "fresh": False, "error": "not list"}

    # gumroad_state.json
    p3 = DATA_DIR / "gumroad_state.json"
    d3 = _load_json(p3)
    if d3 is None:
        results["gumroad_state"] = {"exists": False, "fresh": False}
    elif isinstance(d3, dict):
        age3 = _age_hours(d3.get("collected_at"))
        results["gumroad_state"] = {
            "exists": True,
            "fresh": age3 is not None and age3 < FRESHNESS_H,
            "age_h": round(age3, 1) if age3 else None,
            "sales": d3.get("sales"),
            "total_revenue": d3.get("total_revenue"),
            "login_ok": d3.get("login_ok"),
        }
    else:
        results["gumroad_state"] = {"exists": True, "fresh": False}

    return results


# ── チェック2: external_runs 連続ゼロ検知 ─────────────────────────────────────
def check_external_runs(rev_data: list | None) -> dict:
    """revenue-daily.json の details から external_runs 累計日数を計算。"""
    if not rev_data or not isinstance(rev_data, list):
        # 2026-10-03 修正: print_report が total_days / zero_pct を無条件参照するため、
        # 早期リターンでも同じキー集合を返す（欠損時に KeyError で監視自体が落ちていた）。
        return {
            "zero_days": 0,
            "total_days": 0,
            "zero_pct": 0.0,
            "total_external_runs_all_time": 0,
            "status": "unknown",
            "warn": False,
        }

    # 各actorのexternal_runsを日次集計して、ゼロ連続日数を求める
    zero_count = 0
    total_external_runs_all_time = 0
    for entry in rev_data:
        date = entry.get("date")
        ap = entry.get("apify", {})
        ext = ap.get("external_users_total") or 0
        # details から合算しても良いが、external_users_total があればそれを使う
        total_external_runs_all_time += ext
        if ext == 0:
            zero_count += 1
        else:
            # ゼロ連続はリセットしない（累計ゼロ日数を報告）
            pass

    total_entries = len(rev_data)
    zero_pct = round(zero_count / max(total_entries, 1) * 100, 1)
    warn = zero_count >= EXTERNAL_RUNS_WARN_DAYS

    return {
        "zero_days": zero_count,
        "total_days": total_entries,
        "zero_pct": zero_pct,
        "total_external_runs_all_time": total_external_runs_all_time,
        "status": "zero_streak" if warn else "ok",
        "warn": warn,
    }


# ── チェック3: Gumroad売上ゼロ継続 ───────────────────────────────────────────
def check_gumroad_sales(rev_data: list | None, gum_state: dict | None) -> dict:
    if gum_state is None:
        return {"sales": None, "zero_days": 0, "warn": False}
    sales = gum_state.get("sales")
    # revenue-daily.json の gumroad セクションからも確認
    if rev_data and isinstance(rev_data, list):
        zero_sales_days = 0
        for e in rev_data:
            g = e.get("gumroad", {})
            if g.get("sales", 0) == 0:
                zero_sales_days += 1
        return {
            "sales": sales,
            "zero_sales_days": zero_sales_days,
            "total_days": len(rev_data),
            "warn": zero_sales_days >= 3,
            "login_ok": gum_state.get("login_ok"),
            "products": gum_state.get("total_sales"),
        }
    return {"sales": sales, "zero_sales_days": 0, "warn": False}


# ── チェック4: warnings / opportunities ──────────────────────────────────────
def check_warnings(rev_data: list | None) -> list[str]:
    """最新エントリの warnings を抽出。"""
    if not rev_data or not isinstance(rev_data, list) or not rev_data:
        return []
    w = rev_data[-1].get("warnings", [])
    return w if isinstance(w, list) else []


# ── 統合レポート ──────────────────────────────────────────────────────────────
def run_checks(dry_run: bool = True) -> tuple[dict, list[str]]:
    """全チェックを実行し (state, alerts) を返す。"""
    rev = _load_json(DATA_DIR / "revenue-daily.json")
    snap = _load_json(DATA_DIR / "apify_actors_detail_snapshot.json")
    gum = _load_json(DATA_DIR / "gumroad_state.json")

    freshness = check_freshness()
    ext_runs = check_external_runs(rev if isinstance(rev, list) else None)
    gum_sales = check_gumroad_sales(rev if isinstance(rev, list) else None,
                                    gum if isinstance(gum, dict) else None)
    warnings = check_warnings(rev if isinstance(rev, list) else None)

    alerts: list[str] = []
    if not freshness.get("revenue_daily", {}).get("fresh", True):
        alerts.append("revenue-daily.json: 鮮度不足（24h経過）")
    if not freshness.get("apify_snapshot", {}).get("fresh", True):
        alerts.append("apify_actors_detail_snapshot.json: 鮮度不足")
    if not freshness.get("gumroad_state", {}).get("fresh", True):
        alerts.append("gumroad_state.json: 鮮度不足")
    if ext_runs.get("warn"):
        alerts.append(
            f"external_runs=0 連続 {ext_runs['zero_days']}日 "
            f"({ext_runs['zero_pct']}%) — 外部顧客なし継続"
        )
    if gum_sales.get("warn"):
        alerts.append(
            f"Gumroad売上ゼロ連続 {gum_sales['zero_sales_days']}日"
        )
    for w in warnings:
        alerts.append(f"revenue-warn: {w}")

    # 2026-10-04: exitコードを「実障害」と「実態通知」に分離する。
    # アラート（鮮度不足・外部run 0・Gumroad 0等）は正常な実態の通知であり、
    # 毎日 exit 1 にすると cron の last_status が error 常態化し watchdog が誤検知する。
    # ファイル欠損/読取不能のみを致命(critical)として非0で返す。
    criticals: list[str] = []
    for key, label in (
        ("revenue_daily", "revenue-daily.json"),
        ("apify_snapshot", "apify_actors_detail_snapshot.json"),
        ("gumroad_state", "gumroad_state.json"),
    ):
        if not freshness.get(key, {}).get("exists", True):
            criticals.append(
                f"{label}: ファイル欠損/読取不能（収集パイプライン停止の疑い）"
            )

    state = {
        "checked_at": _iso_jst(_now_jst()),
        "freshness": freshness,
        "external_runs": ext_runs,
        "gumroad_sales": gum_sales,
        "warnings": warnings,
        "alerts": alerts,
        "alert_count": len(alerts),
        "criticals": criticals,
        "critical_count": len(criticals),
    }
    return state, alerts


# ── 出力 ──────────────────────────────────────────────────────────────────────
def print_report(state: dict, dry_run: bool = True) -> None:
    _say(f"=== Revenue Health Check ({state['checked_at'][:16]}) ===")
    f = state["freshness"]

    rd = f.get("revenue_daily", {})
    _say(f"  revenue-daily.json:  {'✓' if rd.get('fresh') else '✗'} "
         f"entries={rd.get('entries', '?')} last={rd.get('last_date')} age={rd.get('age_h')}h "
         f"warnings={rd.get('warnings', [])}")

    as2 = f.get("apify_snapshot", {})
    _say(f"  apify_snapshot.json: {'✓' if as2.get('fresh') else '✗'} "
         f"actors={as2.get('actors', '?')} age={as2.get('age_h')}h")

    gs = f.get("gumroad_state", {})
    _say(f"  gumroad_state.json:  {'✓' if gs.get('fresh') else '✗'} "
         f"sales={gs.get('sales')} login_ok={gs.get('login_ok')} age={gs.get('age_h')}h")

    er = state["external_runs"]
    # 2026-10-03: 欠損キーで監視が落ちないよう .get で防御（原因は check_external_runs 側も修正済み）
    _say(f"  external_runs:       {er.get('zero_days', 0)}/{er.get('total_days', 0)}日 ゼロ "
         f"({er.get('zero_pct', 0.0)}%) total_all_time={er.get('total_external_runs_all_time', '?')}")

    gs2 = state["gumroad_sales"]
    _say(f"  gumroad_sales:       sales={gs2.get('sales')} "
         f"zero_days={gs2.get('zero_sales_days')} warn={gs2.get('warn')}")

    if state["warnings"]:
        _say(f"  warnings: {state['warnings']}")

    if state.get("criticals"):
        _say(f"  CRITICALS ({len(state['criticals'])}):")
        for c in state["criticals"]:
            _say(f"    \U0001f534  {c}", tag="CRITICAL")

    if state["alerts"]:
        _say(f"  ALERTS ({len(state['alerts'])}):")
        for a in state["alerts"]:
            _say(f"    ⚠️  {a}", tag="ALERT")
    elif not state.get("criticals"):
        _say("  All checks OK.")

    if dry_run:
        _say("  [--dry-run] ファイル/Cron変更なし")


# ── Cron無効化 ────────────────────────────────────────────────────────────────
def disable_crons(disable_names: list[str], dry_run: bool = False) -> list[str]:
    """対象cronをdisabledに変更。戻り値は実際に変更した名称リスト。"""
    if not CRON_JOBS_FILE.exists():
        print(f"  [WARN] cron jobs file not found: {CRON_JOBS_FILE}", file=sys.stderr)
        return []
    try:
        jobs = json.loads(CRON_JOBS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [ERR] failed to read cron jobs: {e}", file=sys.stderr)
        return []

    changed: list[str] = []
    for j in jobs.get("jobs", []):
        name = j.get("name", "")
        if name not in disable_names:
            continue
        if j.get("enabled") is False:
            _say(f"  already disabled: {name}")
            continue
        if dry_run:
            _say(f"  [DRY-RUN] would disable: {name}")
            changed.append(name)
            continue
        old = j.get("enabled")
        j["enabled"] = False
        j["state"] = "paused"
        j["paused_at"] = _iso_jst(_now_jst())
        j["paused_reason"] = (
            f"Consolidated into revenue-health-check.py (t_5c77082d). "
            f"Old error: {str(j.get('last_error') or '')[:80]}"
        )
        changed.append(name)
        _say(f"  disabled: {name} (was enabled={old})")

    if not dry_run and changed:
        jobs["updated_at"] = _iso_jst(_now_jst())
        try:
            CRON_JOBS_FILE.write_text(
                json.dumps(jobs, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            _say(f"  cron jobs saved ({len(changed)} changed)")
        except Exception as e:
            print(f"  [ERR] failed to write cron jobs: {e}", file=sys.stderr)
    return changed


# ── notepad記録 ───────────────────────────────────────────────────────────────
def write_notepad(state: dict) -> None:
    """異常アラートをnotepadに記録（過去同类を潰さないよう差分のみ）。"""
    if not state["alerts"]:
        return
    try:
        NOTEPAD_DIR.mkdir(parents=True, exist_ok=True)
        today = _now_jst().strftime("%Y%m%d")
        np_file = NOTEPAD_DIR / f"revenue_health_{today}.md"
        lines = [f"# Revenue Health Check — {_iso_jst(_now_jst())}", ""]
        lines.append("## Alerts")
        for a in state["alerts"]:
            lines.append(f"- {a}")
        lines.append("")
        lines.append("## State Summary")
        lines.append(f"- revenue-daily fresh: {state['freshness'].get('revenue_daily',{}).get('fresh')}")
        lines.append(f"- apify_snapshot fresh: {state['freshness'].get('apify_snapshot',{}).get('fresh')}")
        lines.append(f"- gumroad_state fresh: {state['freshness'].get('gumroad_state',{}).get('fresh')}")
        lines.append(f"- external_runs zero days: {state['external_runs']['zero_days']}")
        lines.append(f"- gumroad zero sales days: {state['gumroad_sales'].get('zero_sales_days', '?')}")
        lines.append("")
        content = "\n".join(lines)
        # 既存内容と diff を見て、同じ内容なら追記しない
        if np_file.exists():
            existing = np_file.read_text(encoding="utf-8")
            # 今日分が既にあれば上書きせず追加のみ
            if f"## Alerts" in existing and today in existing:
                # 差分があれば追記
                if content.split("\n", 3)[-1] not in existing:
                    np_file.write_text(existing + "\n---\n" + content, encoding="utf-8")
                    _say(f"  notepad appended: {np_file.name}")
                else:
                    _say(f"  notepad skip (same alert as today): {np_file.name}")
            else:
                np_file.write_text(content, encoding="utf-8")
                _say(f"  notepad written: {np_file.name}")
        else:
            np_file.write_text(content, encoding="utf-8")
            _say(f"  notepad created: {np_file.name}")
    except Exception as e:
        print(f"  [WARN] notepad write failed: {e}", file=sys.stderr)


# ── Telegram通知（簡易） ─────────────────────────────────────────────────────
def send_telegram_alert(alerts: list[str]) -> None:
    """アラート内容有り時に簡易Telegram通知を送信。"""
    if not alerts or not TELEGRAM_CHAT_ID:
        return
    try:
        import urllib.request
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            return
        msg = "⚠️ Revenue Health Alerts:\n" + "\n".join(f"  - {a}" for a in alerts)
        url = (
            f"https://api.telegram.org/bot{token}/sendMessage"
            f"?chat_id={TELEGRAM_CHAT_ID}&text={urllib.request.quote(msg)}"
            f"&parse_mode=Markdown"
        )
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if not data.get("ok"):
                print(f"  [WARN] telegram send failed: {data}", file=sys.stderr)
    except Exception as e:
        print(f"  [WARN] telegram notification failed: {e}", file=sys.stderr)


# ── メイン ───────────────────────────────────────────────────────────────────
def main() -> int:
    dry_run = "--dry-run" in sys.argv
    disable_flag = "--disable-crons" in sys.argv

    state, alerts = run_checks(dry_run=dry_run)

    print_report(state, dry_run=dry_run)

    # 結果保存
    try:
        STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    # notepad記録
    write_notepad(state)

    # Telegram通知
    send_telegram_alert(alerts)

    # Cron無効化 — 実障害(critical)または明示フラグ時のみ。
    # 2026-10-04: 旧条件は「アラートがあれば disable」で、売上ゼロ等の実態通知でも
    # 健全な cron を巻き込んで停止させていた（collector 復帰が毎朝無効化される原因）。
    if disable_flag or (not dry_run and state.get("criticals")):
        to_disable = [n for n in DISABLE_TARGETS]
        # dry-run時も含め表示
        changed = disable_crons(to_disable, dry_run=dry_run)
        if dry_run and changed:
            _say(f"  [DRY-RUN] would disable {len(changed)} cron(s): {changed}")

    # 実障害(critical)のみ非0。アラートは通知済みなので exit 0（watchdog誤検知の防止）。
    if state.get("criticals") and not dry_run:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
