#!/usr/bin/env python3
from __future__ import annotations
# ── cp932ガード + コンソール非表示（共通ユーティリティ経由）──
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from core.encoding import guard_stdio, hide_console
guard_stdio()
hide_console()
# ──────────────────────────────────────────────
"""
Kensho 懸賞自動収集スクリプト — Thin CLI Wrapper
knshow.comからX懸賞の一覧を取得 → collector.collect() に委譲

v4.0: scraping/collector.py への委譲版（コード重複解消）

使い方: python kensho_collect.py [--max-items N] [--pages N]
  --max-items N: 最大処理件数（デフォルト: config.yamlの値）
  --pages N:     取得する一覧ページ数（デフォルト: 1、全ページ: --all）
  --all:         全ページ取得
"""
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from core.config import load as load_config
from scraping.collector import collect

MAX_ITEMS = 200
MAX_PAGES = 1


def main() -> None:
    max_items = MAX_ITEMS
    max_pages = MAX_PAGES

    # コマンドライン引数
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == '--max-items' and i + 1 < len(args):
            max_items = int(args[i + 1])
        elif arg == '--pages' and i + 1 < len(args):
            max_pages = int(args[i + 1])
        elif arg == '--all':
            max_pages = 99

    print(f"[Kensho Collection] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  最大件数: {max_items}, 最大ページ: {'全ページ' if max_pages >= 99 else max_pages}")

    # configを読み込み、CLI引数で上書き
    cfg = load_config()
    cfg.setdefault('collection', {})['max_items'] = max_items

    # collector.collect() に委譲（log=None → print出力）
    success, errors, total = collect(cfg=cfg, log=None, max_pages=max_pages)

    print(f"\n{'='*50}")
    print(f"完了")
    print(f"  成功: {success}件")
    print(f"  エラー: {errors}件")
    print(f"  累計収集: {total}件")
    print(f"  データ保存: data/collected.json")


if __name__ == '__main__':
    main()
