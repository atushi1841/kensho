#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os

# ── cp932ガード + コンソール非表示（共通ユーティリティ経由）──
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from kensho.core.encoding import guard_stdio

guard_stdio()
# ──────────────────────────────────────────────
"""
Kensho 懸賞自動収集スクリプト — Thin CLI Wrapper
knshow.comからX懸賞の一覧を取得 → collector.collect() に委譲

v4.1: argparse 対応

使い方: python kensho_collect.py [-h] [--max-items N] [--pages N] [--all]
"""
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from kensho.core.config import load as load_config  # noqa: E402
from kensho.scraping.collector import collect  # noqa: E402

MAX_ITEMS = 200
MAX_PAGES = 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Kensho 懸賞自動収集 — knshow.comからX懸賞URLを収集",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="例: %(prog)s --max-items 10 --pages 1",
    )
    p.add_argument("--max-items", type=int, default=MAX_ITEMS, help="最大処理件数（デフォルト: %(default)s）")
    p.add_argument("--pages", type=int, default=MAX_PAGES, help="取得する一覧ページ数（デフォルト: %(default)s）")
    p.add_argument("--all", action="store_true", help="全ページ取得")
    p.add_argument("--version", action="version", version="Kensho v3.5")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    max_items: int = args.max_items
    max_pages: int = 99 if args.all else args.pages

    print(f"[Kensho Collection] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  最大件数: {max_items}, 最大ページ: {'全ページ' if max_pages >= 99 else max_pages}")

    # configを読み込み、CLI引数で上書き
    cfg = load_config()
    cfg.setdefault("collection", {})["max_items"] = max_items

    # collector.collect() に委譲（log=None → print出力）
    success, errors, total = collect(cfg=cfg, log=None, max_pages=max_pages)

    print(f"\n{'=' * 50}")
    print("完了")
    print(f"  成功: {success}件")
    print(f"  エラー: {errors}件")
    print(f"  累計収集: {total}件")
    print("  データ保存: data/collected.json")


if __name__ == "__main__":
    main()
