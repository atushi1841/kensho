#!/usr/bin/env python3
"""telegram_notifier.py — 中古カメラ/家電・デジタル製品の差益アラートをTelegram送信.

- 差益判定: 利回り(利益/調達費) 15% 以上 かつ 利益額 5,000円以上 の機会のみ通知.
- 既存 kensho.utils.notify.send_telegram を再利用 (config.yaml > telegram の
  token/chat_id を参照。未設定なら送信せず、判定結果は標準出力のみ).
- 依存ライブラリ追加なし (urllib ベースの telegram 送信)。

使い方:
  python3 telegram_notifier.py                          # --data-dir 既定で当日candidatesを判定・通知
  python3 telegram_notifier.py --data-dir <dir> --date 20260920
  (モジュールとして import し notify_spread(candidates) を直接呼ぶことも可)

判定しきい値:
  PROFIT_RATE_MIN = 0.15   (利益 / 調達費 が 15% 以上)
  PROFIT_YEN_MIN  = 5000   (利益額 5,000円以上)
※ 利益額は既存監視の fee-stripped 計算 (marketplace手数料8% + 送料1000円を
   resale価格から控除) を前提とする。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(_ROOT))

# 差益判定しきい値
PROFIT_RATE_MIN = 0.15    # 15%以上
PROFIT_YEN_MIN = 5000     # 5,000円以上

# 通知メッセージは1日一度・上位機会の要約のみ（スパム・BOT検出回避）
MAX_NOTIFY = 5


def _today() -> str:
    # 日本時間（JST=UTC+9）基準で日付付け。夜間実行でも境界またぎ時に誤分類しない
    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y%m%d")


def qualifies_for_notify(candidate: dict) -> bool:
    """差益通知すべきか判定。

    candidate は fee-stripped 評価済み (sourcing_cost, resale_price,
    judgment_yen を含む)。利回り=judgment_yen / sourcing_cost。
    """
    cost = candidate.get("sourcing_cost")
    profit = candidate.get("judgment_yen")
    if not cost or not profit:
        return False
    if profit < PROFIT_YEN_MIN:
        return False
    rate = profit / cost
    return rate >= PROFIT_RATE_MIN


def build_message(candidates: list[dict]) -> str:
    """通知候補をHTMLメッセージへ整形する（Telegram上限4096文字以内）。"""
    import html

    notify = [c for c in candidates if qualifies_for_notify(c)]
    notify.sort(key=lambda c: c.get("judgment_yen", 0) or 0, reverse=True)
    notify = notify[:MAX_NOTIFY]

    if not notify:
        return ""
    lines = ["💰 <b>中古差益アラート</b>（利回り15%以上 / 利益5,000円以上）"]
    for c in notify:
        model = html.escape(c.get("model") or "")
        cost = c.get("sourcing_cost") or 0
        resale = c.get("resale_price") or 0
        profit = c.get("judgment_yen") or 0
        rate = (profit / cost * 100) if cost else 0
        title = html.escape((c.get("yahoo_title") or "")[:40])
        url = c.get("url") or ""
        lines.append(f"・<b>{model}</b> +¥{profit:,}（利回り{rate:.1f}%・仕¥{cost:,}→売¥{resale:,}）")
        lines.append(f"   {title}")
        if url:
            lines.append(f"   {html.escape(url)}")
    return "\n".join(lines)


def notify_spread(candidates: list[dict]) -> bool:
    """差益機会を判定し、しきい値超えがあればTelegram送信。

    Returns: 送信試行したか（Telegram未設定ならFalse）。
    """
    from kensho.utils.notify import send_telegram

    msg = build_message(candidates)
    if not msg:
        print("[telegram_notifier] 通知対象なし（利回り15%未満 / 利益5,000円未満）")
        return False

    ok = send_telegram(msg)
    if ok:
        print("[telegram_notifier] Telegram送信OK")
    else:
        # Telegram未設定時は判定結果だけstdout表示（送信はスキップ）
        print("[telegram_notifier] Telegram未設定/失敗 → 送信スキップ（判定結果は以下）")
        print(msg)
    return ok


def _load_candidates(data_dir: Path, date_str: str) -> list[dict]:
    cand_json = data_dir / f"sourcing_candidates_{date_str}.json"
    if not cand_json.exists():
        cand_csv = data_dir / f"sourcing_candidates_{date_str}.csv"
        if not cand_csv.exists():
            return []
        import csv
        rows = []
        with cand_csv.open("r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                rows.append({k: _num(v) for k, v in r.items()})
        return rows
    data = json.loads(cand_json.read_text(encoding="utf-8"))
    return data.get("candidates", [])


def _num(v):
    if v is None:
        return None
    s = str(v).replace(",", "").replace("¥", "").replace("+", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return s


def main() -> None:
    p = argparse.ArgumentParser(description="Telegram差益アラート送信 for camera monitor")
    p.add_argument("--data-dir", type=Path, default=_ROOT / "data" / "camera_monitor")
    p.add_argument("--date", default=_today())
    args = p.parse_args()

    cands = _load_candidates(args.data_dir, args.date)
    if not cands:
        print(f"[telegram_notifier] {args.date} candidates なし（{args.data_dir}）")
        return
    # JSONの場合 int/float 保持、CSVの場合は数値化済み
    notify_spread(cands)


if __name__ == "__main__":
    main()
