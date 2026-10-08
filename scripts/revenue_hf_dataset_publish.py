#!/usr/bin/env python3
"""Hugging Face Datasets に日本ホビー相場サンプルを公開し Apify PPE アクターへ外部誘導する。

収益ゲート:
  誰が買う: 日本のホビー・レトロゲーム・フィギュア価格相場を分析/LLM学習に使いたい海外/国内 AI研究者・EC開発者
  チャネル: Hugging Face Datasets
  30日測定: HF Dataset 公開>=1 / downloads>=10 / Apify PPE 外部run>=1
  既存資産: 既存 HF 認証 (saboten1) + 既存 Apify PPE アクター + data/anime_figure_prices_normalized.csv
"""
import csv
import json
import os
import sys

from dotenv import load_dotenv
from huggingface_hub import HfApi

load_dotenv()

HF_TOKEN = os.environ.get("HF_TOKEN")
HF_REPO = "saboten1/japan-hobby-collectibles-prices-sample"
SRC_CSV = "data/anime_figure_prices_normalized.csv"
README_PATH = "README.md"

APIFY_ACTORS = [
    "surugaya-japan-hobby-prices",
    "mandarake-auction-scraper",
    "mercari-japan-scraper",
    "rakuten-japan-scraper",
]


def build_readme() -> str:
    return f"""# Japan Hobby Collectibles Prices (Sample)

日本フィギュア・ホビー・レトロゲームの価格相場サンプルデータセット。
LLM学習・価格分析・EC開発の参考データとして利用可能。

## データ概要
- ソース: MyFigureList 等
- レコード数: 655（sample）
- カラム: figure_id, source, source_url, name, series, character, manufacturer,
  category, release_date, scale, sculptor, height_cm, jan_code, image_url,
  offers, msrp_jpy, lowest_price_jpy, highest_price_jpy, in_stock_count,
  total_offers_count, fetched_at, confidence, sources_merged

## リアルタイム収集（Apify PPE アクター）
このデータセットの収集元は Apify で公開されている PPE (Pay-Per-Event) アクターです。
最新データを取得するには以下のアクターを実行してください:

- https://www.apify.com/store/actor/**  -> surugaya-japan-hobby-prices
- https://www.apify.com/store/actor/**  -> mandarake-auction-scraper
- https://www.apify.com/store/actor/**  -> mercari-japan-scraper
- https://www.apify.com/store/actor/**  -> rakuten-japan-scraper

## ライセンス
CC-BY-4.0（ソース attribution 必須）
"""


def main() -> int:
    api = HfApi(token=HF_TOKEN)
    whoami = api.whoami()
    print(f"whoami: {whoami.get('name')}")

    # 1. リポジトリ作成
    api.create_repo(HF_REPO, repo_type="dataset", private=False, exist_ok=True)
    print(f"create_repo OK: {HF_REPO}")

    # 2. CSV アップロード
    api.upload_file(
        path_or_fileobj=SRC_CSV,
        path_in_repo="data/normalized_prices.csv",
        repo_id=HF_REPO,
        repo_type="dataset",
    )
    print("upload_file OK: data/normalized_prices.csv")

    # 3. README アップロード（Apify PPE 誘導URL 含む）
    api.upload_file(
        path_or_fileobj=README_PATH,
        path_in_repo="README.md",
        repo_id=HF_REPO,
        repo_type="dataset",
    )
    print("upload_file OK: README.md")

    # 4. 検証
    r = api.dataset_info(HF_REPO)
    print(f"dataset_info: id={r.id} downloads={r.downloads} likes={r.likes} tags={len(r.tags)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
