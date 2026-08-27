import glob
import json
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

today = date.today()
today_str = today.isoformat()
now = datetime.now()
week_end = today + timedelta(days=(6 - today.weekday()))

PROJECT_DIR = os.environ.get("PROJECT_DIR", "/mnt/d/Project2/kensho")
DATA_FILE = os.path.join(PROJECT_DIR, "data/collected.json")
COUNT_FILE = os.path.join(PROJECT_DIR, "data/daily_counts.json")
OUTPUT_FILE = os.path.join(PROJECT_DIR, "kensho-status.html")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")

accounts = ["atushi16", "kudou", "chugakujuken", "zin20120731", "TankanNotes", "inobase1-4"]

# ── UNUSED（応募停止済み）アカウント記録 ──
# cron再生成でも維持されるようハードコード（2026-08-17現在は応募停止垢なし）
UNUSED_ACCOUNTS: list[dict[str, str]] = []

# ── 表示用フィルタ（実応募条件 = config.yaml 準拠に統一）──
# 2026-08-20 修正: 従来は19項目NG+URL除外で厳しすぎ、実際の応募可否と乖離していた。
# 実応募(applier.py)は config の ng_words(5項目) + skip_url_posts=false で判定されるため、
# ダッシュボードの「有効数」もここに合わせる。
NG_WORDS = [
    "応募フォーム",
    "クイズ",
    "アンケート",
    "合言葉",
    "応募はこちら",
]
REQUIRED_WORDS = ["フォロー"]
# config.skip_url_posts=false → 表示でもURL投稿を除外しない
SKIP_URL_POSTS = False


def passes_filter(text):
    if not text or not text.strip():
        return None
    for ng in NG_WORDS:
        if ng in text:
            return False
    if not any(rw in text for rw in REQUIRED_WORDS):
        return None
    if SKIP_URL_POSTS:
        if re.search(r"https?://|t\\.co/", text):
            return False
    return True


try:
    with open(DATA_FILE) as f:
        raw = json.load(f)
    items = raw.get("collected", [])
except Exception:
    items = []

try:
    with open(COUNT_FILE) as f:
        dc = json.load(f)
    daily_counts = dc.get("counts", {})
except Exception:
    daily_counts = {}

# ★ 2026-08-23修正: 「本日応募」を audit.jsonl(追記専用・消えない完全履歴)から正確に算出。
#   collected.applied は保存競合+None汚染で過小化し、実応募と乖離するため dashboard はこれを使う。
#   フォロー成功1件 = 応募成立1件（懸賞応募の主条件）として垢別に数える。
_applied_today_per_account: dict[str, int] = defaultdict(int)
try:
    _audit_file = os.path.join(PROJECT_DIR, "data/audit.jsonl")
    with open(_audit_file, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("status") != "success":
                continue
            ts = r.get("timestamp", "")
            if not ts.startswith(today_str):
                continue
            if r.get("action_type") == "follow":
                _applied_today_per_account[r.get("account", "")] += 1
except Exception:
    pass

result: dict[str, Any] = {"accounts": {}, "stats": {}}

for ac in accounts:
    today_dl = this_week_dl = future_dl = no_dl = 0
    filter_passed = filter_failed = filter_unknown = 0

    for it in items:
        dl = it.get("deadline", "")
        applied = it.get("applied", {})
        # 2026-08-20 修正: 応募済み判定を「その垢に応募日時(DEFER含む)が記録されているか」に変更。
        # 従来「今日日付を含むか」だったため、過去に応募済みの投稿でも期限が今日以降なら
        # pending有効数に入ってしまい、全垢で有効数が同数(同一内訳)になる歪みがあった。
        ap_val = applied.get(ac) if isinstance(applied, dict) else None
        is_applied = isinstance(ap_val, str)  # 日時 or DEFER:xxx が記録済み = この垢では処理済み
        pending = not is_applied
        if dl:
            try:
                dl_d = datetime.strptime(dl, "%Y-%m-%d").date()
                days_left = (dl_d - today).days
                if pending:
                    if days_left < 0:
                        pass
                    elif days_left == 0:
                        today_dl += 1
                    elif days_left <= 3:
                        this_week_dl += 1
                    elif days_left <= 7:
                        future_dl += 1
                    else:
                        future_dl += 1
            except Exception:
                no_dl += 1
        elif pending:
            no_dl += 1

        tweet_text = it.get("tweet_text", "") or ""
        if tweet_text.strip():
            _filter_result = passes_filter(tweet_text)
            if _filter_result is True:
                filter_passed += 1
            elif _filter_result is False:
                filter_failed += 1
            else:
                filter_unknown += 1
        else:
            filter_unknown += 1

    total_pending = today_dl + this_week_dl + future_dl + no_dl
    today_str = today.isoformat()
    # ★ 2026-08-23修正: 「本日応募」を audit.jsonl(追記専用・消えない完全履歴)から算出。
    #   従来 collected.applied ベースだったが、None汚染+保存競合で実際の応募が過小表示され、
    #   実態(応募成功率)と大きく乖離していた。フォロー成功1件=応募成立1件として数える。
    applied_today = _applied_today_per_account.get(ac, 0)

    defer_count = sum(
        1
        for it in items
        if isinstance(it.get("applied", {}), dict)
        and isinstance(it["applied"].get(ac), str)
        and it["applied"][ac].startswith("DEFER:")
    )

    total_applied_all = sum(
        1
        for it in items
        if isinstance(it.get("applied", {}), dict)
        and isinstance(it["applied"].get(ac), str)
        and not it["applied"][ac].startswith("DEFER:")
    )

    c = daily_counts.get(ac, {})
    follow = c.get("follow", 0)
    rt = c.get("rt", 0)
    like = c.get("like", 0)

    result["accounts"][ac] = {
        "pending": {
            "total": total_pending,
            "today_deadline": today_dl,
            "this_week_deadline": this_week_dl,
            "future_deadline": future_dl,
            "no_deadline": no_dl,
        },
        "today_counts": {"applied": applied_today, "total": applied_today + total_pending},
        "applied_today": applied_today,
        "total_applied_all": total_applied_all,
        "daily": {"follow": follow, "rt": rt, "like": like},
        "defer_count": defer_count,
        "filter": {"passed": filter_passed, "failed": filter_failed, "unknown": filter_unknown},
    }

# ── 収集ソース分布 ──
source_dist = {}
for it in items:
    src = it.get("source", "unknown")
    source_dist[src] = source_dist.get(src, 0) + 1
result["stats"]["source_dist"] = source_dist

# ── 期限分布 ──
dl_dist = {"expired": 0, "today": 0, "3days": 0, "week": 0, "future": 0, "no_deadline": 0}
for it in items:
    dl = it.get("deadline", "")
    if dl:
        try:
            dl_d = datetime.strptime(dl, "%Y-%m-%d").date()
            days_left = (dl_d - today).days
            if days_left < 0:
                dl_dist["expired"] += 1
            elif days_left == 0:
                dl_dist["today"] += 1
            elif days_left <= 3:
                dl_dist["3days"] += 1
            elif days_left <= 7:
                dl_dist["week"] += 1
            else:
                dl_dist["future"] += 1
        except Exception:
            dl_dist["no_deadline"] = dl_dist.get("no_deadline", 0) + 1
    else:
        dl_dist["no_deadline"] += 1
result["stats"]["deadline_dist"] = dl_dist

# ── 賞品価値分布 ──
prize_dist = {"high(3.0)": 0, "mid_high(2.5)": 0, "mid(2.0)": 0, "low(1.5)": 0, "none(1.0)": 0, "unscored": 0}
for it in items:
    ps = it.get("prize_score", {})
    if ps:
        p = ps.get("priority", 1.0)
        if p >= 3.0:
            prize_dist["high(3.0)"] += 1
        elif p >= 2.5:
            prize_dist["mid_high(2.5)"] += 1
        elif p >= 2.0:
            prize_dist["mid(2.0)"] += 1
        elif p >= 1.5:
            prize_dist["low(1.5)"] += 1
        else:
            prize_dist["none(1.0)"] += 1
    else:
        prize_dist["unscored"] += 1
result["stats"]["prize_dist"] = prize_dist

# ── 最終実行ログから実行履歴抽出 ──
log_files = sorted(glob.glob(os.path.join(LOG_DIR, "auto_*.log")), key=os.path.getmtime)
recent_runs = []
for lf in log_files[-60:]:
    bn = os.path.basename(lf).replace("auto_", "").replace(".log", "")
    run_dt = None
    try:
        run_dt = datetime.strptime(bn, "%Y%m%d_%H%M%S")
    except ValueError:
        pass
    if run_dt is None:
        # 日次ログ auto_YYYYMMDD.log 対応
        try:
            if len(bn) == 8 and bn.isdigit():
                run_dt = datetime.strptime(bn, "%Y%m%d")
        except ValueError:
            pass
    try:
        with open(lf) as fh:
            log_text = fh.read()
    except Exception:
        continue
    if "今回処理:" not in log_text:
        continue
    if run_dt is None or (len(bn) == 8 and bn.isdigit()):
        # 日次ログ: 最後のタイムスタンプ付き行の時刻を実行時刻として使う
        ts_matches = list(re.finditer(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)", log_text))
        if not ts_matches:
            continue
        ts_str = ts_matches[-1].group(1)
        run_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
    if "処理待ちのバッチなし" in log_text and "今回処理: 0垢" in log_text:
        continue
    entry = {
        "time": run_dt.strftime("%H:%M"),
        "success": 0,
        "error": 0,
        "accounts": 0,
        "follow": 0,
        "rt": 0,
        "like": 0,
        "status": "ok",
        "status_text": "",
    }
    # 各パターンは「最後のマッチ」を採用する
    ok_matches = re.findall(r"\[OK\] 完了:\s*(\d+)成功\s*/\s*(\d+)エラー", log_text)
    if ok_matches:
        entry["success"] = int(ok_matches[-1][0])
        entry["error"] = int(ok_matches[-1][1])
    daily_matches = re.findall(r"本日累計:\s*フォロー(\d+)\s+RT(\d+)\s+いいね(\d+)", log_text)
    if daily_matches:
        entry["follow"] = int(daily_matches[-1][0])
        entry["rt"] = int(daily_matches[-1][1])
        entry["like"] = int(daily_matches[-1][2])
    acc_matches = re.findall(r"\s*今回処理:\s*(\d+)垢", log_text)
    if acc_matches:
        entry["accounts"] = int(acc_matches[-1])
    warn_matches = list(re.finditer(r"⚠️|FAIL|ERROR|失敗", log_text))
    error_matches = list(re.finditer(r"❌|FATAL", log_text))
    last_warn = warn_matches[-1] if warn_matches else None
    last_err = error_matches[-1] if error_matches else None
    if last_err and (not last_warn or last_err.start() > last_warn.start()):
        entry["status"] = "error"
    elif last_warn:
        entry["status"] = "warn"
    else:
        entry["status"] = "ok"
    recent_runs.append(entry)
result["recent_runs"] = recent_runs

# ── パイプライン健全性 ──
pipeline_status = {"last_run": None, "last_status": None, "updated": now.isoformat()}
if recent_runs:
    pipeline_status["last_run"] = recent_runs[-1]["time"]
    pipeline_status["last_status"] = recent_runs[-1]["status"]
result["pipeline"] = pipeline_status

# ── 全体サマリー ──
total_applied = sum(a["total_applied_all"] for a in result["accounts"].values())
total_pending_all = sum(a["pending"]["total"] for a in result["accounts"].values())
total_today = sum(a["today_counts"]["applied"] for a in result["accounts"].values())
total_defer = sum(a["defer_count"] for a in result["accounts"].values())
result["summary"] = {
    "total_items": len(items),
    "total_applied": total_applied,
    "total_pending": total_pending_all,
    "total_today": total_today,
    "total_defer": total_defer,
}

# ── しきい値超過チェック ──
over_limit = {}
for ac, data in result["accounts"].items():
    d = data["daily"]
    warnings = []
    if d["follow"] > 50:
        warnings.append(f"フォロー{d['follow']}")
    if d["rt"] > 15:
        warnings.append(f"RT{d['rt']}")
    if d["like"] > 80:
        warnings.append(f"いいね{d['like']}")
    if warnings:
        over_limit[ac] = warnings
result["over_limit"] = over_limit

# ── 日別×アカウント別 応募履歴（直近14日） ──
# ★ 2026-08-23修正: collected.applied(None汚染)ではなく audit のフォロー成功から算出。
#   応募成立=フォロー成功。action_history(全アクション)と区別するため apply_history はフォローのみ。
apply_history = defaultdict(lambda: defaultdict(int))
action_history = defaultdict(lambda: defaultdict(int))
# ★ 2026-08-27提案25: auditは重複RT等を全て記録するため、同一(垢,種別,対象)への
#   重複アクションは1回に数える（daily_countsが重複を除外して記録する実アクション数に揃える）。
_seen_actions: set[tuple[str, str, str, str]] = set()
try:
    with open(os.path.join(PROJECT_DIR, "data/audit.jsonl"), encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("status") != "success":
                continue
            day = (r.get("timestamp") or "")[:10]
            acct = r.get("account", "")
            at = r.get("action_type", "")
            tgt = r.get("target", "")
            if day and acct:
                _k = (day, acct, at, tgt)
                if _k in _seen_actions:
                    continue
                _seen_actions.add(_k)
                action_history[day][acct] += 1
                if at == "follow":
                    apply_history[day][acct] += 1
except Exception:
    pass

all_days = sorted(set(apply_history) | set(action_history))
history_days = all_days[-14:]
result["history"] = {
    "days": history_days,
    "applied": {d: dict(apply_history[d]) for d in history_days},
    "actions": {d: dict(action_history[d]) for d in history_days},
}

# ── UNUSED（応募停止済み）アカウントをJSONに含める ──
result["unused_accounts"] = UNUSED_ACCOUNTS

# ═══════════════════════════════════════════════
# ── WiFiテザリング状態（watchdogログから集計）──
# 2026-08-21 追加: kensho-wifi-watchdog.sh が記録する 接続済み[信号:Rssi] / 障害@時刻 を集計
# ═══════════════════════════════════════════════
WIFI_ADAPTER_TO_ACCOUNT = {
    "kudou_RM10JE_B": "kudou",
    "chugakujuken_RM10JE_S": "chugakujuken",
    "zin_AW6povo": "zin20120731",
    "Tankan_2_redmi_n9s": "TankanNotes",  # 旧アダプタ名（2_povo_tankanに改名済み・参照残は実害なし）
    "2_povo_tankan": "TankanNotes",
    "inobase1-4": "inobase1-4",
}
WIFI_ACCOUNT_SSID = {
    "kudou": "RM10JE_B",
    "chugakujuken": "RM10JE_S",
    "zin20120731": "AiR-WiFi_6_povo",
    "TankanNotes": "2_povo_HR01",
    "inobase1-4": "ino1_4_oppo_r5a",
}

_OK_RE = re.compile(r"✅\s+(\S+)\s+->\s+接続済み")
_SIG_RE = re.compile(r"信号:(\d+)\s*%\|(-?\d+)\b")
_FAIL_CUT_RE = re.compile(r"❌\s+(\S+)\s+->\s+切断")
_FAIL_FAIL_RE = re.compile(r"❌\s+(\S+)\s+->\s+再接続失敗")
_TS_RE = re.compile(r"@(\d{2}:\d{2}:\d{2})$")


def _wifi_date_from_name(bn: str):
    m = re.search(r"(\d{8})", bn)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


wifi_stats: dict[str, dict[str, Any]] = {}
for ac in WIFI_ACCOUNT_SSID:
    wifi_stats[ac] = {
        "adapter": "",
        "ssid": WIFI_ACCOUNT_SSID[ac],
        "signal": None,  # 最新の接続時 信号%
        "rssi": None,  # 最新の接続時 Rssi(dBm)
        "connected_now": None,  # 最新runでの接続状態 (True/False/None)
        "ok_today": 0,
        "fail_today": 0,
        "ok_last7d": 0,
        "fail_last7d": 0,
        "last_fail_time": "",  # 最新障害の時刻 (MM-DD HH:MM)
    }

# 今日の日付文字列
today_dt = datetime.now().date()
today_key = today_dt.strftime("%Y%m%d")


def _last_seen_hms_for_line(line: str) -> str | None:
    m = _TS_RE.search(line.rstrip())
    return m.group(1) if m else None


wifi_log_files = sorted(glob.glob(os.path.join(LOG_DIR, "wifi_watchdog_*.log")))
for wlf in wifi_log_files:
    bn = os.path.basename(wlf)
    fdate = _wifi_date_from_name(bn)
    if fdate is None:
        continue
    is_today = fdate == today_dt
    last7 = (today_dt - fdate).days <= 6
    try:
        with open(wlf, encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
    except Exception:
        continue
    for line in txt.splitlines():
        om = _OK_RE.search(line)
        if om:
            adapter = om.group(1)
            ac = WIFI_ADAPTER_TO_ACCOUNT.get(adapter)
            if ac is None:
                continue
            w = wifi_stats[ac]
            w["adapter"] = adapter
            # 信号値更新（同じrun内で複数回接続済みが出ても最後を採用）
            sm = _SIG_RE.search(line)
            if sm:
                try:
                    w["signal"] = int(sm.group(1))
                except ValueError:
                    pass
                try:
                    w["rssi"] = int(sm.group(2))
                except ValueError:
                    pass
            w["connected_now"] = True
            w["ok_today"] += 1 if is_today else 0
            w["ok_last7d"] += 1 if last7 else 0
            continue
        fm = _FAIL_CUT_RE.search(line) or _FAIL_FAIL_RE.search(line)
        if fm:
            adapter = fm.group(1)
            ac = WIFI_ADAPTER_TO_ACCOUNT.get(adapter)
            if ac is None:
                continue
            w = wifi_stats[ac]
            w["adapter"] = adapter
            w["connected_now"] = False
            w["fail_today"] += 1 if is_today else 0
            w["fail_last7d"] += 1 if last7 else 0
            hms = _last_seen_hms_for_line(line)
            if hms:
                w["last_fail_time"] = f"{fdate.strftime('%m-%d')} {hms}"
            continue

result["wifi"] = wifi_stats

with open("/tmp/kensho_status_data.json", "w") as f:
    json.dump(result, f, ensure_ascii=False, default=str)

print("DATA_OK")
