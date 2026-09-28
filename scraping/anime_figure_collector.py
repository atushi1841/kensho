#!/usr/bin/env python3
"""Anime Figure Price Data Collector — MyFigureList.com から価格履歴を収集

実際の本番コレクター: MyFigureList sitemap から全フィギュアURLを発見し、
JSON-LD (Product + AggregateOffer) から価格・在庫・発売日等を抽出。
Hpoi/figurememo は現状 DNS/接続不可のため除外（将来復活時はモジュール拡張可）。

出力: data/anime_figure_prices.jsonl (JSON Lines)
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from kensho.scraping.common import HEADERS
from kensho.scraping.socks_rotation import make_rotator_from_config
from kensho.utils.backup import safe_save_json

logger = logging.getLogger(__name__)


@dataclass
class ShopOffer:
    """個別ショップのオファー情報"""
    shop_name: str
    price_jpy: int
    availability: str  # InStock / OutOfStock / PreOrder / Unknown
    url: str
    condition: str = "NewCondition"
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FigurePrice:
    """フィギュア価格情報（正規化済み）"""
    # 識別情報
    figure_id: str
    source_url: str

    # 基本情報
    name: str
    series: str | None = None
    character: str | None = None
    manufacturer: str | None = None
    category: str | None = None
    release_date: str | None = None
    scale: str | None = None
    sculptor: str | None = None
    height_cm: int | None = None
    jan_code: str | None = None
    image_url: str | None = None

    # 価格・在庫情報
    offers: list[ShopOffer] = field(default_factory=list)
    msrp_jpy: int | None = None
    lowest_price_jpy: int | None = None
    highest_price_jpy: int | None = None
    in_stock_count: int = 0
    total_offers_count: int = 0

    # メタデータ
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        in_stock_offers = [o for o in self.offers if o.availability == "InStock"]
        if in_stock_offers:
            self.lowest_price_jpy = min(o.price_jpy for o in in_stock_offers)
            self.highest_price_jpy = max(o.price_jpy for o in in_stock_offers)
            self.in_stock_count = len(in_stock_offers)
        self.total_offers_count = len(self.offers)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class MyFigureListCollector:
    """MyFigureList.com からフィギュア価格データを収集"""

    def __init__(
        self,
        proxy_url: str | None = None,
        rate_limit_rpm: int = 30,
        cache_ttl: int = 3600,
        max_concurrent: int = 5,
    ):
        self.base_url = "https://myfigurelist.com"
        self.proxy_url = proxy_url
        self.rate_limit_rpm = rate_limit_rpm
        self.cache_ttl = cache_ttl
        self.max_concurrent = max_concurrent

        self._client: httpx.AsyncClient | None = None
        self._sitemap_cache: list[str] | None = None
        self._sitemap_fetched_at: float = 0
        self._last_request_at: float = 0
        self._rate_limit_semaphore: asyncio.Semaphore | None = None

    async def __aenter__(self) -> "MyFigureListCollector":
        timeout = httpx.Timeout(30.0, connect=15.0)
        limits = httpx.Limits(max_connections=self.max_concurrent, max_keepalive_connections=5)
        proxy = self.proxy_url if self.proxy_url else None
        self._client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            proxy=proxy,
            headers=HEADERS,
            follow_redirects=True,
        )
        self._rate_limit_semaphore = asyncio.Semaphore(self.max_concurrent)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
        self._client = None

    async def _rate_limit(self) -> None:
        """レート制限: 分間リクエスト数を守る"""
        now = time.time()
        min_interval = 60.0 / self.rate_limit_rpm
        elapsed = now - self._last_request_at
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_at = time.time()

    async def _fetch_html(self, url: str) -> BeautifulSoup | None:
        """HTML取得→BeautifulSoup返却"""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        await self._rate_limit()
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"MFL: 404 Not Found: {url}")
            else:
                logger.warning(f"MFL HTTP {e.response.status_code}: {url}")
            return None
        except Exception as e:
            logger.warning(f"MFL fetch error {url}: {type(e).__name__}: {e}")
            return None

    def _extract_json_ld(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """ページから JSON-LD を全抽出"""
        scripts = soup.find_all("script", type="application/ld+json")
        results = []
        for script in scripts:
            try:
                data = json.loads(script.string or "{}")
                if isinstance(data, list):
                    results.extend(data)
                elif isinstance(data, dict):
                    results.append(data)
            except json.JSONDecodeError:
                continue
        return results

    def _parse_product_json_ld(self, data: dict[str, Any], url: str, breadcrumb: dict[str, Any] | None = None) -> FigurePrice | None:
        """Product JSON-LD から FigurePrice を構築"""
        if data.get("@type") != "Product":
            return None

        name = data.get("name", "").strip()
        if not name:
            return None

        figure_id = self._extract_figure_id(url)
        image_url = data.get("image")
        if isinstance(image_url, list):
            image_url = image_url[0] if image_url else None

        # JAN/GTIN/SKU
        jan_code = data.get("gtin13") or data.get("gtin") or data.get("sku")

        # オファー解析
        offers_data = data.get("offers", {})
        offers = []
        msrp_jpy = None

        if isinstance(offers_data, dict):
            if offers_data.get("@type") == "AggregateOffer":
                nested_offers = offers_data.get("offers", [])
                for offer in nested_offers:
                    if not isinstance(offer, dict):
                        continue
                    seller = offer.get("seller", {})
                    shop_name = seller.get("name", "Unknown Shop") if isinstance(seller, dict) else "Unknown Shop"
                    price = offer.get("price")
                    availability_url = offer.get("availability", "")
                    availability = self._parse_availability(availability_url)
                    offer_url = offer.get("url", "")
                    condition = offer.get("itemCondition", "NewCondition").split("/")[-1]

                    if price is not None and shop_name:
                        offers.append(ShopOffer(
                            shop_name=shop_name,
                            price_jpy=int(price),
                            availability=availability,
                            url=offer_url,
                            condition=condition,
                        ))
            elif offers_data.get("@type") == "Offer":
                seller = offers_data.get("seller")
                if not seller:
                    price = offers_data.get("price")
                    if price is not None:
                        msrp_jpy = int(price)
                else:
                    shop_name = seller.get("name", "Unknown Shop") if isinstance(seller, dict) else "Unknown Shop"
                    price = offers_data.get("price")
                    availability_url = offers_data.get("availability", "")
                    availability = self._parse_availability(availability_url)
                    offer_url = offers_data.get("url", "")
                    condition = offers_data.get("itemCondition", "NewCondition").split("/")[-1]

                    if price is not None:
                        offers.append(ShopOffer(
                            shop_name=shop_name,
                            price_jpy=int(price),
                            availability=availability,
                            url=offer_url,
                            condition=condition,
                        ))

        # シリーズ・キャラクター・カテゴリ・メーカー
        manufacturer = data.get("brand", {}).get("name") if isinstance(data.get("brand"), dict) else data.get("brand")
        category = data.get("category")

        # additionalProperty から scale / sculptor / height 抽出
        scale = None
        sculptor = None
        height_cm = None
        for prop in data.get("additionalProperty", []):
            if isinstance(prop, dict):
                pname = prop.get("name", "")
                pval = prop.get("value", "")
                if "scale" in pname.lower():
                    scale = pval
                elif "sculptor" in pname.lower():
                    sculptor = pval
                elif "height" in pname.lower() and isinstance(pval, (int, float)):
                    height_cm = int(pval)

        # series / character は breadcrumb から抽出
        series = None
        character = None
        if breadcrumb and breadcrumb.get("@type") == "BreadcrumbList":
            for item in breadcrumb.get("itemListElement", []):
                item_name = item.get("name", "")
                item_url = item.get("item", "")
                if "/series/" in item_url:
                    series = item_name
                elif "/character/" in item_url:
                    character = item_name

        # URLからカテゴリ推定
        if not category:
            category = self._guess_category(name, url)

        return FigurePrice(
            figure_id=figure_id,
            source_url=url,
            name=name,
            series=series,
            character=character,
            manufacturer=manufacturer,
            category=category,
            release_date=data.get("releaseDate"),
            scale=scale,
            sculptor=sculptor,
            height_cm=height_cm,
            jan_code=jan_code,
            image_url=image_url,
            offers=offers,
            msrp_jpy=msrp_jpy,
            raw_data=data,
        )

    def _parse_availability(self, availability_url: str) -> str:
        if "InStock" in availability_url:
            return "InStock"
        elif "OutOfStock" in availability_url:
            return "OutOfStock"
        elif "PreOrder" in availability_url:
            return "PreOrder"
        return "Unknown"

    def _extract_figure_id(self, url: str) -> str:
        match = re.search(r"/figure/(\d+)", url)
        return match.group(1) if match else url

    def _guess_category(self, name: str, url: str) -> str | None:
        name_lower = name.lower()
        url_lower = url.lower()
        categories = {
            "nendoroid": ["nendoroid", "ねんどろいど"],
            "figma": ["figma", "フィグマ"],
            "scale-figure": ["scale", "スケール", "1/"],
            "pop-up-parade": ["pop up parade", "pop-up parade", "popupparade"],
            "prize": ["prize", "プライズ", "一番くじ", "ichiban kuji"],
            "garage-kit": ["garage kit", "ガレキ", "ガレージキット"],
            "statue": ["statue", "スタチュー"],
            "doll": ["doll", "ドール", "azone", "アゾン"],
        }
        for cat, keywords in categories.items():
            if any(kw in name_lower or kw in url_lower for kw in keywords):
                return cat
        return None

    async def _discover_urls_from_sitemap(self, max_urls: int | None = None) -> list[str]:
        """sitemap.xml からフィギュア詳細URLを発見"""
        now = time.time()
        if self._sitemap_cache and (now - self._sitemap_fetched_at) < self.cache_ttl:
            urls = self._sitemap_cache
        else:
            try:
                resp = await self._client.get(f"{self.base_url}/sitemap.xml")
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "xml")
                sitemap_urls = [loc.text.strip() for loc in soup.find_all("loc")]

                figure_sitemaps = [u for u in sitemap_urls if "/sitemaps/figure-" in u]

                all_urls = []
                for fs_url in figure_sitemaps:
                    try:
                        fs_resp = await self._client.get(fs_url)
                        fs_resp.raise_for_status()
                        fs_soup = BeautifulSoup(fs_resp.text, "xml")
                        urls = [loc.text.strip() for loc in fs_soup.find_all("loc") if "/figure/" in loc.text]
                        all_urls.extend(urls)
                    except Exception as e:
                        logger.warning(f"MFL sitemap fetch failed {fs_url}: {e}")

                self._sitemap_cache = all_urls
                self._sitemap_fetched_at = now
                urls = all_urls
            except Exception as e:
                logger.error(f"MFL main sitemap fetch error: {e}")
                urls = self._sitemap_cache or []

        if max_urls:
            urls = urls[:max_urls]
        return urls

    async def fetch_figure(self, url: str) -> FigurePrice | None:
        """フィギュア詳細ページから価格取得"""
        soup = await self._fetch_html(url)
        if not soup:
            return None

        json_ld_list = self._extract_json_ld(soup)

        # BreadcrumbList を事前取得
        breadcrumb = None
        for ld in json_ld_list:
            if ld.get("@type") == "BreadcrumbList":
                breadcrumb = ld
                break

        for data in json_ld_list:
            result = self._parse_product_json_ld(data, url, breadcrumb)
            if result:
                logger.info(f"MFL: {result.name} (¥{result.lowest_price_jpy}~) offers={result.total_offers_count}")
                return result

        logger.debug(f"MFL: no Product JSON-LD at {url}")
        return None

    async def collect_batch(
        self,
        urls: list[str],
        progress_cb=None,
    ) -> list[FigurePrice]:
        """URLリストから並列収集"""
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_one(url: str) -> FigurePrice | None:
            async with semaphore:
                return await self.fetch_figure(url)

        tasks = [fetch_one(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        collected = []
        for i, r in enumerate(results):
            if isinstance(r, FigurePrice):
                collected.append(r)
            elif isinstance(r, Exception):
                logger.warning(f"MFL fetch exception: {r}")
            if progress_cb:
                progress_cb(i + 1, len(urls))

        return collected


async def run_collection(
    out_dir: str = "data",
    max_figures: int = 10000,
    proxy_url: str | None = None,
    rate_limit_rpm: int = 30,
) -> list[FigurePrice]:
    """メイン収集関数"""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    output_file = out_path / "anime_figure_prices.jsonl"

    # 既存データから既収集 figure_id を読み込み（重複回避）
    existing_ids: set[str] = set()
    if output_file.exists():
        with output_file.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    if d.get("figure_id"):
                        existing_ids.add(d["figure_id"])
                except json.JSONDecodeError:
                    continue
        logger.info(f"MFL: Loaded {len(existing_ids)} existing figure_ids for deduplication")

    async with MyFigureListCollector(
        proxy_url=proxy_url,
        rate_limit_rpm=rate_limit_rpm,
    ) as collector:
        logger.info(f"MFL: Discovering figure URLs from sitemap (target: {max_figures})...")
        urls = await collector._discover_urls_from_sitemap(max_urls=max_figures * 3)  # 3倍取ってフィルタ
        logger.info(f"MFL: Found {len(urls)} figure URLs")

        if not urls:
            logger.warning("MFL: No URLs found, exiting")
            return []

        # 既収集を除外
        filtered_urls = []
        for u in urls:
            fid = re.search(r"/figure/(\d+)", u)
            if fid and fid.group(1) not in existing_ids:
                filtered_urls.append(u)
        urls = filtered_urls
        logger.info(f"MFL: After dedup, {len(urls)} new URLs to collect")

        if not urls:
            logger.info("MFL: All URLs already collected")
            return []

        # シャッフルして偏りなく収集
        random.shuffle(urls)

        collected: list[FigurePrice] = []
        batch_size = 50
        total_batches = (len(urls) + batch_size - 1) // batch_size

        for batch_idx in range(total_batches):
            start = batch_idx * batch_size
            end = min(start + batch_size, len(urls))
            batch_urls = urls[start:end]

            logger.info(f"MFL: Batch {batch_idx+1}/{total_batches} ({len(batch_urls)} items)")
            batch_results = await collector.collect_batch(batch_urls)

            # 即時書き出し（JSONL追記）
            with output_file.open("a", encoding="utf-8") as f:
                for item in batch_results:
                    f.write(item.to_jsonl() + "\n")

            collected.extend(batch_results)
            logger.info(f"MFL: Batch {batch_idx+1} done, total collected this run: {len(collected)}")

            if len(collected) >= max_figures:
                break

            # バッチ間の小休止
            await asyncio.sleep(2.0)

    logger.info(f"MFL: Collection complete. Total new: {len(collected)} figures saved to {output_file}")
    return collected


if __name__ == "__main__":
    import argparse
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(description="Collect anime figure prices from MyFigureList")
    parser.add_argument("--max", type=int, default=10000, help="Max figures to collect")
    parser.add_argument("--out", type=str, default="data", help="Output directory")
    parser.add_argument("--rpm", type=int, default=30, help="Rate limit requests per minute")
    parser.add_argument("--proxy", type=str, default=os.environ.get("SOCKS5_PROXY"), help="SOCKS5 proxy URL")
    args = parser.parse_args()

    asyncio.run(run_collection(
        out_dir=args.out,
        max_figures=args.max,
        proxy_url=args.proxy,
        rate_limit_rpm=args.rpm,
    ))