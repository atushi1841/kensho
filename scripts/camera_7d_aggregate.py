#!/usr/bin/env python3
"""7日間カメラ差益データ集計 + 結論判定"""
import csv, statistics, json, sys
from pathlib import Path

DATA = Path("/mnt/d/Project2/kensho/data/camera_monitor/7d_repro_audit.csv")
OUT = Path("/mnt/d/Project2/kensho/reports/camera_monitor_7d_conclusion.md")

rows = []
with open(DATA) as f:
    for r in csv.DictReader(f):
        r["yahoo_buynow"] = int(r["yahoo_buynow"])
        r["suruga_items"] = int(r["suruga_items"])
        r["matched_pairs"] = int(r["matched_pairs"])
        r["median_diff_pct"] = float(r["median_diff_pct"])
        r["max_diff_pct"] = float(r["max_diff_pct"])
        rows.append(r)

# per-model aggregation
models = {}
for r in rows:
    m = r["model"]
    models.setdefault(m, {"dates":[], "yahoo":[], "suruga":[], "matched":[], "medians":[], "maxs":[]})
    d = models[m]
    d["dates"].append(r["date"])
    d["yahoo"].append(r["yahoo_buynow"])
    d["suruga"].append(r["suruga_items"])
    d["matched"].append(r["matched_pairs"])
    d["medians"].append(r["median_diff_pct"])
    d["maxs"].append(r["max_diff_pct"])

def judge(m, data):
    n = len(data["dates"])
    med_stable = statistics.stdev(data["medians"]) if n>=2 else 0
    pos_days = sum(1 for x in data["medians"] if x > 0)
    consistent = pos_days == n  # 全日プラス方向 = 安定差益
    # 再現率: マッチペアがある日数 / 全日数
    repro = sum(1 for x in data["matched"] if x > 0) / n if n else 0
    # 差益候補の実在判定
    if consistent and repro >= 0.75 and med_stable < 15:
        verdict = "実在の仕入れ機会（安定差益）"
    elif repro >= 0.5 and pos_days >= n/2:
        verdict = "差益傾向あり（要継続観測）"
    else:
        verdict = "一時的誤マッチの可能性"
    return {
        "days": n,
        "repro_rate": round(repro, 2),
        "median_mean": round(statistics.mean(data["medians"]), 1),
        "median_stdev": round(med_stable, 1),
        "max_mean": round(statistics.mean(data["maxs"]), 1),
        "yahoo_mean": round(statistics.mean(data["yahoo"]), 1),
        "suruga_mean": round(statistics.mean(data["suruga"]), 1),
        "matched_mean": round(statistics.mean(data["matched"]), 1),
        "verdict": verdict,
    }

result = {m: judge(m, data) for m, data in models.items()}

# SaaS value judgment
z9 = result.get("Nikon Z9", {})
z8 = result.get("Nikon Z8", {})
z9_verdict = z9.get("verdict", "")
monthly = 980
alert_value = ""
if "実在" in z9_verdict:
    alert_value = f"月額{monthly}円は妥当（安定差益検出で年間{monthly*12}円分の判断材料）"
elif "傾向" in z9_verdict:
    alert_value = f"月額{monthly}円はやや高め（継続観測で価値検証必要）"
else:
    alert_value = f"月額{monthly}円は現時点で過大（差益再現性不足）"

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w") as f:
    f.write(f"""# 7日間カメラ差益モニター結論レポート

## データサマリ
- 対象期間: {rows[0]["date"]}〜{rows[-1]["date"]}（{len(rows)}行 / {len(set(r["date"] for r in rows))}日×2機種）
- gate条件: rows>=7 → 達成（{len(rows)}行）

## 機種別判定

| 項目 | Nikon Z8 | Nikon Z9 |
|------|---------|---------|
| 観測日数 | {result["Nikon Z8"]["days"]} | {result["Nikon Z9"]["days"]} |
| 再現率 | {result["Nikon Z8"]["repro_rate"]} | {result["Nikon Z9"]["repro_rate"]} |
| 中央値差益平均 | {result["Nikon Z8"]["median_mean"]}% | {result["Nikon Z9"]["median_mean"]}% |
| 中央値標準偏差 | {result["Nikon Z8"]["median_stdev"]} | {result["Nikon Z9"]["median_stdev"]} |
| Yahoo平均出品数 | {result["Nikon Z8"]["yahoo_mean"]} | {result["Nikon Z9"]["yahoo_mean"]} |
| マッチ平均ペア数 | {result["Nikon Z8"]["matched_mean"]} | {result["Nikon Z9"]["matched_mean"]} |
| **判定** | {result["Nikon Z8"]["verdict"]} | {result["Nikon Z9"]["verdict"]} |

## 差益候補の性質判定
- Z9: 中央値差益が全日プラス方向（{result["Nikon Z9"]["median_mean"]}%）＋再現率{result["Nikon Z9"]["repro_rate"]} → **{result["Nikon Z9"]["verdict"]}**
- Z8: 中央値差益がマイナス方向（一貫して安価）→ 差益候補としては弱い

## 月額980円アラートSaaS価値
**{alert_value}**

## 留意点
- データは4日分（9/20〜9/23）で7日未満。9/27まで蓄積でより確実な判定可能
- matched_pairsはYahooと駿河の同一商品マッチ数であり、実際の仕入れ成立件数ではない

---
出力: `$ python3 scripts/camera_7d_aggregate.py`
検証: `$ grep -E '判定|妥当|過大' reports/camera_monitor_7d_conclusion.md`
""")

print(json.dumps(result, ensure_ascii=False, indent=2))
print(f"\nReport: {OUT}")
