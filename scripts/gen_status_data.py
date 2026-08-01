import glob
import json
import os
import re
from datetime import date, datetime, timedelta

today = date.today()
now = datetime.now()
week_end = today + timedelta(days=(6 - today.weekday()))

PROJECT_DIR = os.environ.get("PROJECT_DIR", "/mnt/d/Project2/kensho")
DATA_FILE = os.path.join(PROJECT_DIR, "data/collected.json")
COUNT_FILE = os.path.join(PROJECT_DIR, "data/daily_counts.json")
OUTPUT_FILE = os.path.join(PROJECT_DIR, "kensho-status.html")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")

accounts = ["atushi16", "kudou", "atushi1840", "zin20120731", "TankanNotes", "inobase1-4"]

NG_WORDS = [
    "応募フォーム",
    "クイズ",
    "URL",
    "問題",
    "動画",
    "LINE",
    "結果を確認",
    "画像",
    "応募はこちら",
    "引用",
    "結果確認",
    "url",
    "リンク先",
    "チェック",
    "合言葉",
    "アンケート",
    "抽選結果",
    "リンク",
    "シェア",
]
REQUIRED_WORDS = ["フォロー"]
SKIP_URL_POSTS = True


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
except:
    items = []

try:
    with open(COUNT_FILE) as f:
        dc = json.load(f)
    daily_counts = dc.get("counts", {})
except:
    daily_counts = {}

result = {"accounts": {}, "stats": {}}

for ac in accounts:
    today_dl = this_week_dl = future_dl = no_dl = 0
    filter_passed = filter_failed = filter_unknown = 0

    for it in items:
        dl = it.get("deadline", "")
        applied = it.get("applied", {})
        is_applied = isinstance(applied, dict) and isinstance(applied.get(ac), str) and today.isoformat() in applied[ac]
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
            except:
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
    applied_today = sum(
        1
        for it in items
        if isinstance(it.get("applied", {}), dict)
        and isinstance(it["applied"].get(ac), str)
        and today_str in it["applied"][ac]
    )

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
        except:
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
    try:
        run_dt = datetime.strptime(bn, "%Y%m%d_%H%M%S")
    except:
        continue
    try:
        with open(lf) as fh:
            log_text = fh.read()
    except:
        continue
    if "今回処理:" not in log_text:
        continue
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
    for line in log_text.split("\n"):
        m = re.search(r"\[OK\] 完了:\s*(\d+)成功\s*/\s*(\d+)エラー", line)
        if m:
            entry["success"] = int(m.group(1))
            entry["error"] = int(m.group(2))
        m2 = re.search(r"本日累計:\s*フォロー(\d+)\s+RT(\d+)\s+いいね(\d+)", line)
        if m2:
            entry["follow"] = int(m2.group(1))
            entry["rt"] = int(m2.group(2))
            entry["like"] = int(m2.group(3))
        m3 = re.search(r"\s*今回処理:\s*(\d+)垢", line)
        if m3:
            entry["accounts"] = int(m3.group(1))
        m4 = re.search(r"⚠️|FAIL|ERROR|失敗", line)
        if m4:
            entry["status"] = "warn"
        m5 = re.search(r"❌|FATAL", line)
        if m5:
            entry["status"] = "error"
    recent_runs.append(entry)
result["recent_runs"] = recent_runs

# ── パイプライン健全性 ──
pipeline_status = {"last_run": None, "last_status": None, "updated": now.isoformat()}
if recent_runs:
    pipeline_status["last_run"] = recent_runs[0]["time"]
    pipeline_status["last_status"] = recent_runs[0]["status"]
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

with open("/tmp/kensho_status_data.json", "w") as f:
    json.dump(result, f, ensure_ascii=False, default=str)

print("DATA_OK")
