"""Unified Anime Figure Pricing API — MyFigureList(JSON-LD) > Hpoi(API) > FigureMemo(HTML)
統合価格比較モジュール
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .common import HEADERS, _fetch_with_retry
from ..common import get_random_user_agent

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════

class PriceSource(str, Enum):
    """価格データソース識別子"""
    MYFIGURELIST = "myfigurelist"
    HPOI = "hpoi"
    FIGUREMEMO = "figurememo"


class AvailabilityStatus(str, Enum):
    """在庫状態（schema.org準拠）"""
    IN_STOCK = "InStock"
    OUT_OF_STOCK = "OutOfStock"
    PRE_ORDER = "PreOrder"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class ShopOffer:
    """個別ショップのオファー情報"""
    shop_name: str
    price_jpy: int
    availability: AvailabilityStatus
    url: str
    condition: str = "NewCondition"  # NewCondition / UsedCondition
    last_checked: datetime = field(default_factory=datetime.now)

    def is_buyable(self) -> bool:
        return self.availability == AvailabilityStatus.IN_STOCK


@dataclass(frozen=True)
class FigurePrice:
    """フィギュア価格情報（正規化済み）"""
    # 識別情報
    figure_id: str                    # 各サイト固有のID
    source: PriceSource               # データソース
    source_url: str                   # 元ページURL

    # 基本情報
    name: str                         # 商品名
    series: str | None = None         # シリーズ名
    character: str | None = None      # キャラクター名
    manufacturer: str | None = None   # メーカー
    category: str | None = None       # カテゴリ (scale-figure, nendoroid, figma等)
    release_date: str | None = None   # 発売日 (YYYY-MM-DD)

    # 価格・在庫情報
    offers: list[ShopOffer] = field(default_factory=list)
    msrp_jpy: int | None = None       # メーカー希望小売価格
    lowest_price_jpy: int | None = None   # 最安値(在庫ありのみ)
    highest_price_jpy: int | None = None  # 最高値(在庫ありのみ)
    in_stock_count: int = 0           # 在庫ありショップ数
    total_offers_count: int = 0       # 全オファー数

    # メタデータ
    image_url: str | None = None
    jan_code: str | None = None       # JAN/EANコード
    fetched_at: datetime = field(default_factory=datetime.now)
    raw_data: dict[str, Any] = field(default_factory=dict)  # デバッグ用生データ

    def __post_init__(self):
        # 計算フィールドの自動設定
        in_stock_offers = [o for o in self.offers if o.is_buyable()]
        if in_stock_offers:
            object.__setattr__(self, 'lowest_price_jpy', min(o.price_jpy for o in in_stock_offers))
            object.__setattr__(self, 'highest_price_jpy', max(o.price_jpy for o in in_stock_offers))
            object.__setattr__(self, 'in_stock_count', len(in_stock_offers))
        object.__setattr__(self, 'total_offers_count', len(self.offers))

    def to_dict(self) -> dict[str, Any]:
        """辞書化（JSONシリアライズ用）"""
        return {
            "figure_id": self.figure_id,
            "source": self.source.value,
            "source_url": self.source_url,
            "name": self.name,
            "series": self.series,
            "character": self.character,
            "manufacturer": self.manufacturer,
            "category": self.category,
            "release_date": self.release_date,
            "msrp_jpy": self.msrp_jpy,
            "lowest_price_jpy": self.lowest_price_jpy,
            "highest_price_jpy": self.highest_price_jpy,
            "in_stock_count": self.in_stock_count,
            "total_offers_count": self.total_offers_count,
            "image_url": self.image_url,
            "jan_code": self.jan_code,
            "fetched_at": self.fetched_at.isoformat(),
            "offers": [
                {
                    "shop_name": o.shop_name,
                    "price_jpy": o.price_jpy,
                    "availability": o.availability.value,
                    "url": o.url,
                    "condition": o.condition,
                    "last_checked": o.last_checked.isoformat(),
                }
                for o in self.offers
            ],
        }


# ═══════════════════════════════════════════════════════════════════════
# Base Client with Rate Limiting & Cache
# ═══════════════════════════════════════════════════════════════════════

class RateLimiter:
    """シンプルなトークンバケット型レートリミッタ"""

    def __init__(self, requests_per_minute: int = 30, burst: int = 5):
        self.rate = requests_per_minute / 60.0  # req/sec
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return

            # トークン不足 → 待機
            wait_time = (1 - self.tokens) / self.rate
            self.tokens = 0
        await asyncio.sleep(wait_time)


class BaseFigureClient:
    """フィギュア価格取得クライアント基底クラス"""

    def __init__(
        self,
        base_url: str,
        source: PriceSource,
        rate_limit_rpm: int = 30,
        timeout: float = 30.0,
        cache_ttl: int = 3600,
    ):
        self.base_url = base_url.rstrip("/")
        self.source = source
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[FigurePrice, float]] = {}  # url -> (data, timestamp)
        self._rate_limiter = RateLimiter(rate_limit_rpm)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "User-Agent": get_random_user_agent(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                },
                follow_redirects=True,
                verify=False,  # 一部サイトでSSL証明書問題のため
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "BaseFigureClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _get_cache_key(self, url: str) -> str:
        return url

    def _is_cache_valid(self, timestamp: float) -> bool:
        return (time.time() - timestamp) < self.cache_ttl

    async def _fetch(self, url: str, **kwargs) -> httpx.Response:
        """レート制限付きGETリクエスト"""
        await self._rate_limiter.acquire()
        client = await self._get_client()
        return await client.get(url, **kwargs)

    async def _fetch_json(self, url: str, **kwargs) -> dict[str, Any]:
        """JSONレスポンス取得"""
        resp = await self._fetch(url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def _fetch_html(self, url: str, **kwargs) -> BeautifulSoup:
        """HTMLパース済みレスポンス取得"""
        resp = await self._fetch(url, **kwargs)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def _get_cached(self, url: str) -> FigurePrice | None:
        key = self._get_cache_key(url)
        if key in self._cache:
            data, ts = self._cache[key]
            if self._is_cache_valid(ts):
                return data
            else:
                del self._cache[key]
        return None

    def _set_cache(self, url: str, data: FigurePrice) -> None:
        self._cache[self._get_cache_key(url)] = (data, time.time())

    async def fetch_figure(self, identifier: str) -> FigurePrice | None:
        """フィギュア価格取得（サブクラスで実装）"""
        raise NotImplementedError

    async def search_figures(self, query: str, limit: int = 20) -> list[FigurePrice]:
        """フィギュア検索（サブクラスで実装）"""
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════════════
# MyFigureList Client (Primary - JSON-LD structured data)
# ═══════════════════════════════════════════════════════════════════════

class MyFigureListClient(BaseFigureClient):
    """MyFigureList.com クライアント
    - JSON-LD (Product + AggregateOffer) から構造化価格データを抽出
    - サイトマップから全フィギュアURLを発見可能
    - robots.txt で /api/offer/ 以外はクロール許可
    """

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://myfigurelist.com",
            source=PriceSource.MYFIGURELIST,
            rate_limit_rpm=30,  # 礼儀正しく
            **kwargs
        )
        self._sitemap_cache: list[str] | None = None
        self._sitemap_fetched_at: float = 0

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

    def _parse_product_json_ld(self, data: dict[str, Any], url: str) -> FigurePrice | None:
        """Product JSON-LD から FigurePrice を構築"""
        if data.get("@type") != "Product":
            return None

        # 基本情報
        name = data.get("name", "").strip()
        if not name:
            return None

        figure_id = self._extract_figure_id(url)
        image_url = data.get("image")
        if isinstance(image_url, list):
            image_url = image_url[0] if image_url else None

        # JAN/GTIN コード
        jan_code = data.get("gtin13") or data.get("gtin") or data.get("sku")

        # オファー解析
        offers_data = data.get("offers", {})
        offers = []
        msrp_jpy = None

        if isinstance(offers_data, dict):
            if offers_data.get("@type") == "AggregateOffer":
                # 複数ショップの集約オファー
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
                # 単一オファー（メーカー希望小売価格の可能性）
                seller = offers_data.get("seller")
                if not seller:  # sellerなし = MSRP
                    price = offers_data.get("price")
                    if price is not None:
                        msrp_jpy = int(price)
                else:
                    # 通常のショップオファー
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

        # シリーズ・キャラクター・カテゴリ抽出（breadcrumbやcategoryから）
        series = None
        character = None
        category = None
        manufacturer = data.get("brand", {}).get("name") if isinstance(data.get("brand"), dict) else data.get("brand")

        # カテゴリ推定（URLやnameから）
        category = self._guess_category(name, url)

        return FigurePrice(
            figure_id=figure_id,
            source=PriceSource.MYFIGURELIST,
            source_url=url,
            name=name,
            series=series,
            character=character,
            manufacturer=manufacturer,
            category=category,
            release_date=None,  # JSON-LDにはreleaseDateが稀
            offers=offers,
            msrp_jpy=msrp_jpy,
            image_url=image_url,
            jan_code=jan_code,
            raw_data=data,
        )

    def _parse_availability(self, availability_url: str) -> AvailabilityStatus:
        """schema.org availability URL を列挙値に変換"""
        if "InStock" in availability_url:
            return AvailabilityStatus.IN_STOCK
        elif "OutOfStock" in availability_url:
            return AvailabilityStatus.OUT_OF_STOCK
        elif "PreOrder" in availability_url:
            return AvailabilityStatus.PRE_ORDER
        return AvailabilityStatus.UNKNOWN

    def _extract_figure_id(self, url: str) -> str:
        """URLからフィギュアID抽出: /figure/12345/name -> 12345"""
        match = re.search(r"/figure/(\d+)", url)
        return match.group(1) if match else url

    def _guess_category(self, name: str, url: str) -> str | None:
        """名前/URLからカテゴリ推定"""
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
        }
        for cat, keywords in categories.items():
            if any(kw in name_lower or kw in url_lower for kw in keywords):
                return cat
        return None

    async def fetch_figure(self, identifier: str) -> FigurePrice | None:
        """フィギュア詳細ページから価格取得"""
        # identifier がURLの場合とIDの場合両対応
        if identifier.startswith("http"):
            url = identifier
        else:
            url = f"{self.base_url}/figure/{identifier}"

        # キャッシュチェック
        cached = self._get_cached(url)
        if cached:
            logger.debug(f"MyFigureList cache hit: {url}")
            return cached

        try:
            soup = await self._fetch_html(url)
            json_ld_list = self._extract_json_ld(soup)

            for data in json_ld_list:
                result = self._parse_product_json_ld(data, url)
                if result:
                    self._set_cache(url, result)
                    logger.info(f"MyFigureList: fetched {result.name} (¥{result.lowest_price_jpy}~)")
                    return result

            logger.warning(f"MyFigureList: no Product JSON-LD found at {url}")
            return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"MyFigureList: figure not found: {url}")
            else:
                logger.error(f"MyFigureList HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"MyFigureList fetch error for {url}: {e}")
            return None

    async def search_figures(self, query: str, limit: int = 20) -> list[FigurePrice]:
        """検索クエリでフィギュアを検索（sitemapから発見→詳細取得）"""
        # sitemap.xmlからフィギュアURLを発見
        figure_urls = await self._discover_urls_from_sitemap(limit * 3)

        # 並列で詳細取得（最大5並列）
        semaphore = asyncio.Semaphore(5)

        async def fetch_one(url: str) -> FigurePrice | None:
            async with semaphore:
                return await self.fetch_figure(url)

        tasks = [fetch_one(url) for url in figure_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for r in results:
            if isinstance(r, FigurePrice):
                # query一致フィルタ
                if query.lower() in r.name.lower():
                    valid_results.append(r)
            if len(valid_results) >= limit:
                break

        return valid_results

    async def _discover_urls_from_sitemap(self, max_urls: int = 60) -> list[str]:
        """sitemap.xmlからフィギュア詳細URLを発見"""
        if self._sitemap_cache is None or (time.time() - self._sitemap_fetched_at) > 3600:
            try:
                resp = await self._fetch(f"{self.base_url}/sitemap.xml")
                if resp:
                    text = resp.text
                    pattern = re.compile(
                        rf"{re.escape(self.base_url)}/figure/\d+/[^<\s\"']+",
                        re.IGNORECASE,
                    )
                    self._sitemap_cache = list(dict.fromkeys(pattern.findall(text)))
                    self._sitemap_fetched_at = time.time()
                else:
                    self._sitemap_cache = []
            except Exception as e:
                logger.warning("MFL sitemap fetch failed: %s", e)
                self._sitemap_cache = []

        return self._sitemap_cache[:max_urls]

    async def fetch_sitemap_figure_urls(self) -> list[str]:
        """サイトマップから全フィギュアURLを取得（大量収集用）"""
        now = time.time()
        if self._sitemap_cache and (now - self._sitemap_fetched_at) < 86400:  # 24hキャッシュ
            return self._sitemap_cache

        try:
            resp = await self._fetch(f"{self.base_url}/sitemap.xml")
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "xml")

            urls = []
            for loc in soup.find_all("loc"):
                url = loc.text.strip()
                if "/figure/" in url and re.search(r"/figure/\d+", url):
                    urls.append(url)

            self._sitemap_cache = urls
            self._sitemap_fetched_at = now
            logger.info(f"MyFigureList sitemap: {len(urls)} figure URLs")
            return urls

        except Exception as e:
            logger.error(f"MyFigureList sitemap fetch error: {e}")
            return self._sitemap_cache or []


# ═══════════════════════════════════════════════════════════════════════
# Hpoi.net Client (Secondary - Public API)
# ═══════════════════════════════════════════════════════════════════════

class HpoiClient(BaseFigureClient):
    """Hpoi.net API クライアント
    - parse.bot マーケットプレイスで公開API仕様が確認済み
    - エンドポイント: /api/v1/items/search, /api/v1/items/{id}
    - レスポンスに価格・在庫・ショップ情報含む
    """

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://api.hpoi.jp",
            source=PriceSource.HPOI,
            rate_limit_rpm=20,  # API利用なので控えめに
            **kwargs
        )

    async def fetch_figure(self, identifier: str) -> FigurePrice | None:
        """商品詳細APIから価格取得"""
        if identifier.startswith("http"):
            # URLからID抽出
            match = re.search(r"/item/(\d+)", identifier)
            if not match:
                return None
            item_id = match.group(1)
        else:
            item_id = identifier

        api_url = f"{self.base_url}/api/v1/items/{item_id}"
        source_url = f"https://hpoi.net/item/{item_id}"

        cached = self._get_cached(api_url)
        if cached:
            return cached

        try:
            data = await self._fetch_json(api_url)
            result = self._parse_item_response(data, source_url)
            if result:
                self._set_cache(api_url, result)
            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Hpoi: item not found: {item_id}")
            else:
                logger.error(f"Hpoi HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"Hpoi fetch error for {item_id}: {e}")
            return None

    def _parse_item_response(self, data: dict[str, Any], url: str) -> FigurePrice | None:
        """APIレスポンスから FigurePrice 構築"""
        # Hpoi API レスポンス構造想定（parse.bot仕様ベース）
        # 実際のレスポンス構造に合わせて調整が必要
        item = data.get("item") or data.get("data") or data
        if not item:
            return None

        figure_id = str(item.get("id", ""))
        name = item.get("name", "").strip()
        if not name:
            return None

        # 価格・ショップ情報
        offers = []
        shops = item.get("shops") or item.get("offers") or []

        for shop in shops:
            if not isinstance(shop, dict):
                continue
            shop_name = shop.get("shop_name") or shop.get("name") or "Unknown"
            price = shop.get("price") or shop.get("price_jpy")
            stock = shop.get("stock_status") or shop.get("availability") or "unknown"
            shop_url = shop.get("url") or shop.get("link") or ""

            if price is None:
                continue

            availability = self._parse_hpoi_stock(stock)
            offers.append(ShopOffer(
                shop_name=shop_name,
                price_jpy=int(price),
                availability=availability,
                url=shop_url,
            ))

        # MSRP
        msrp = item.get("msrp") or item.get("list_price") or item.get("original_price")

        return FigurePrice(
            figure_id=figure_id,
            source=PriceSource.HPOI,
            source_url=url,
            name=name,
            series=item.get("series") or item.get("series_name"),
            character=item.get("character") or item.get("character_name"),
            manufacturer=item.get("manufacturer") or item.get("maker"),
            category=item.get("category") or item.get("type"),
            release_date=item.get("release_date") or item.get("release"),
            offers=offers,
            msrp_jpy=int(msrp) if msrp else None,
            image_url=item.get("image") or item.get("image_url") or item.get("thumbnail"),
            jan_code=item.get("jan") or item.get("ean") or item.get("gtin"),
            raw_data=data,
        )

    def _parse_hpoi_stock(self, stock_str: str) -> AvailabilityStatus:
        stock_lower = stock_str.lower()
        if any(kw in stock_lower for kw in ["在庫あり", "in stock", "available", "○", "◯"]):
            return AvailabilityStatus.IN_STOCK
        elif any(kw in stock_lower for kw in ["予約", "preorder", "pre-order", "coming soon"]):
            return AvailabilityStatus.PRE_ORDER
        elif any(kw in stock_lower for kw in ["在庫なし", "out of stock", "sold out", "×", "✕"]):
            return AvailabilityStatus.OUT_OF_STOCK
        return AvailabilityStatus.UNKNOWN

    async def search_figures(self, query: str, limit: int = 20) -> list[FigurePrice]:
        """検索APIでフィギュア検索"""
        url = f"{self.base_url}/api/v1/items/search"
        params = {"q": query, "limit": limit}

        try:
            data = await self._fetch_json(url, params=params)
            items = data.get("items") or data.get("data") or data.get("results") or []

            results = []
            for item in items[:limit]:
                parsed = self._parse_item_response(item, f"https://hpoi.net/item/{item.get('id')}")
                if parsed:
                    results.append(parsed)

            return results

        except Exception as e:
            logger.error(f"Hpoi search error: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════
# FigureMemo.jp Client (Fallback - HTML Scraping)
# ═══════════════════════════════════════════════════════════════════════

class FigureMemoClient(BaseFigureClient):
    """FigureMemo.com クライアント
    - 構造化データなし → HTMLパース必須
    - 商品ページから価格表をスクレイピング
    - レート制限を厳しめに設定
    """

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://figurememo.com",
            source=PriceSource.FIGUREMEMO,
            rate_limit_rpm=10,  # HTMLスクレイピングなので控えめ
            **kwargs
        )

    async def fetch_figure(self, identifier: str) -> FigurePrice | None:
        """商品ページHTMLから価格抽出"""
        if identifier.startswith("http"):
            url = identifier
        else:
            url = f"{self.base_url}/item/{identifier}"

        cached = self._get_cached(url)
        if cached:
            return cached

        try:
            soup = await self._fetch_html(url)
            result = self._parse_item_page(soup, url)
            if result:
                self._set_cache(url, result)
            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"FigureMemo: item not found: {url}")
            else:
                logger.error(f"FigureMemo HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"FigureMemo fetch error for {url}: {e}")
            return None

    def _parse_item_page(self, soup: BeautifulSoup, url: str) -> FigurePrice | None:
        """商品ページHTMLパース（サイト構造に依存・要調整）"""
        # FigureMemo の典型的な構造想定
        # 実際のHTML構造に合わせてセレクタ調整が必要

        # 商品名
        name_elem = soup.select_one("h1.item-title, h1.product-title, .item-name, .product-name")
        name = name_elem.get_text(strip=True) if name_elem else ""
        if not name:
            # fallback: titleタグ
            title = soup.find("title")
            name = title.get_text(strip=True).replace(" - FigureMemo", "") if title else ""
        if not name:
            return None

        # ID抽出
        figure_id = self._extract_id(url)

        # 価格テーブル解析
        offers = []
        # 典型的な価格テーブル構造
        price_rows = soup.select("table.price-table tr, .price-list .shop-row, .shop-price-row")
        for row in price_rows:
            shop_elem = row.select_one(".shop-name, .store-name, td:nth-child(1)")
            price_elem = row.select_one(".price, .shop-price, td:nth-child(2)")
            stock_elem = row.select_one(".stock, .availability, td:nth-child(3)")
            link_elem = row.select_one("a[href]")

            if not shop_elem or not price_elem:
                continue

            shop_name = shop_elem.get_text(strip=True)
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r"[\d,]+", price_text.replace(",", ""))
            if not price_match:
                continue
            price = int(price_match.group())

            stock_text = stock_elem.get_text(strip=True) if stock_elem else ""
            availability = self._parse_figurememo_stock(stock_text)

            shop_url = urljoin(self.base_url, link_elem["href"]) if link_elem and link_elem.get("href") else ""

            offers.append(ShopOffer(
                shop_name=shop_name,
                price_jpy=price,
                availability=availability,
                url=shop_url,
            ))

        # メタ情報抽出（概要エリア等から）
        series = self._extract_meta(soup, ["シリーズ", "series", "作品"])
        character = self._extract_meta(soup, ["キャラクター", "character", "キャラ"])
        manufacturer = self._extract_meta(soup, ["メーカー", "manufacturer", "メーカ"])
        category = self._extract_meta(soup, ["カテゴリ", "category", "種類"])
        release_date = self._extract_meta(soup, ["発売日", "release", "release_date"])
        jan_code = self._extract_meta(soup, ["JAN", "jan", "EAN", "ean", "コード"])
        image_elem = soup.select_one(".item-image img, .product-image img, .main-image img")
        image_url = urljoin(self.base_url, image_elem["src"]) if image_elem and image_elem.get("src") else None

        return FigurePrice(
            figure_id=figure_id,
            source=PriceSource.FIGUREMEMO,
            source_url=url,
            name=name,
            series=series,
            character=character,
            manufacturer=manufacturer,
            category=category,
            release_date=release_date,
            offers=offers,
            image_url=image_url,
            jan_code=jan_code,
            raw_data={"html_length": len(str(soup))},
        )

    def _extract_id(self, url: str) -> str:
        match = re.search(r"/item/(\d+)", url)
        return match.group(1) if match else url

    def _parse_figurememo_stock(self, text: str) -> AvailabilityStatus:
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["在庫あり", "あり", "購入可能", "カート", "in stock"]):
            return AvailabilityStatus.IN_STOCK
        elif any(kw in text_lower for kw in ["予約", "preorder", "予約受付"]):
            return AvailabilityStatus.PRE_ORDER
        elif any(kw in text_lower for kw in ["在庫なし", "なし", "売り切れ", "完売", "out of stock"]):
            return AvailabilityStatus.OUT_OF_STOCK
        return AvailabilityStatus.UNKNOWN

    def _extract_meta(self, soup: BeautifulSoup, keywords: list[str]) -> str | None:
        """メタ情報テーブルから値抽出"""
        for th in soup.find_all(["th", "dt"]):
            th_text = th.get_text(strip=True)
            if any(kw in th_text for kw in keywords):
                td = th.find_next_sibling(["td", "dd"])
                if td:
                    return td.get_text(strip=True)
        return None

    async def search_figures(self, query: str, limit: int = 20) -> list[FigurePrice]:
        """検索ページからフィギュア検索"""
        search_url = f"{self.base_url}/search"
        params = {"q": query}

        try:
            soup = await self._fetch_html(search_url, params=params)

            # 検索結果リンク抽出
            figure_urls = []
            for link in soup.select("a[href^='/item/']"):
                href = link.get("href", "")
                if re.match(r"^/item/\d+", href):
                    full_url = urljoin(self.base_url, href)
                    if full_url not in figure_urls:
                        figure_urls.append(full_url)
                        if len(figure_urls) >= limit:
                            break

            semaphore = asyncio.Semaphore(3)  # より控えめに

            async def fetch_one(url: str) -> FigurePrice | None:
                async with semaphore:
                    return await self.fetch_figure(url)

            tasks = [fetch_one(url) for url in figure_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            valid_results = []
            for r in results:
                if isinstance(r, FigurePrice):
                    valid_results.append(r)
                elif isinstance(r, Exception):
                    logger.error(f"FigureMemo search fetch error: {r}")

            return valid_results

        except Exception as e:
            logger.error(f"FigureMemo search error: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════
# Unified Price Aggregator
# ═══════════════════════════════════════════════════════════════════════

class FigurePriceAggregator:
    """複数ソースから価格を取得し、最安値・在庫情報を統合"""

    def __init__(
        self,
        enable_myfigurelist: bool = True,
        enable_hpoi: bool = True,
        enable_figurememo: bool = True,
        cache_ttl: int = 3600,
    ):
        self.clients: list[BaseFigureClient] = []

        if enable_myfigurelist:
            self.clients.append(MyFigureListClient(cache_ttl=cache_ttl))
        if enable_hpoi:
            self.clients.append(HpoiClient(cache_ttl=cache_ttl))
        if enable_figurememo:
            self.clients.append(FigureMemoClient(cache_ttl=cache_ttl))

        self._source_priority = [
            PriceSource.MYFIGURELIST,
            PriceSource.HPOI,
            PriceSource.FIGUREMEMO,
        ]

    async def __aenter__(self) -> "FigurePriceAggregator":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        for client in self.clients:
            await client.close()

    def _get_client(self, source: PriceSource) -> BaseFigureClient | None:
        for client in self.clients:
            if client.source == source:
                return client
        return None

    async def fetch_best_price(self, identifier: str, source_hint: PriceSource | None = None) -> FigurePrice | None:
        """複数ソースから取得し、最安値（在庫あり）の結果を返す"""
        # ソース優先順位で試行
        sources_to_try = self._source_priority
        if source_hint and source_hint in sources_to_try:
            sources_to_try = [source_hint] + [s for s in sources_to_try if s != source_hint]

        results: list[FigurePrice] = []

        for source in sources_to_try:
            client = self._get_client(source)
            if not client:
                continue

            try:
                result = await client.fetch_figure(identifier)
                if result and result.offers:
                    results.append(result)
                    logger.info(f"Got price from {source.value}: {result.name} - lowest ¥{result.lowest_price_jpy}")
            except Exception as e:
                logger.error(f"Error fetching from {source.value}: {e}")

        if not results:
            return None

        # 最安値（在庫あり）のソースを選択
        best = min(
            (r for r in results if r.lowest_price_jpy is not None),
            key=lambda x: x.lowest_price_jpy or float("inf"),
            default=None
        )

        if best:
            # 他ソースの情報もマージ（オファー統合）
            merged_offers = list(best.offers)
            for other in results:
                if other is best:
                    continue
                # 同一ショップ・同価格は重複除去
                for offer in other.offers:
                    if not any(o.shop_name == offer.shop_name and o.price_jpy == offer.price_jpy for o in merged_offers):
                        merged_offers.append(offer)

            # 新しいFigurePriceを構築（マージ済みオファーで）
            return FigurePrice(
                figure_id=best.figure_id,
                source=best.source,
                source_url=best.source_url,
                name=best.name,
                series=best.series,
                character=best.character,
                manufacturer=best.manufacturer,
                category=best.category,
                release_date=best.release_date,
                offers=merged_offers,
                msrp_jpy=best.msrp_jpy,
                image_url=best.image_url,
                jan_code=best.jan_code,
                raw_data={"sources": [r.source.value for r in results], **best.raw_data},
            )

        return results[0] if results else None

    async def search_all_sources(self, query: str, limit: int = 10) -> dict[PriceSource, list[FigurePrice]]:
        """全ソースで検索実行"""
        results = {}
        for client in self.clients:
            try:
                source_results = await client.search_figures(query, limit)
                results[client.source] = source_results
                logger.info(f"{client.source.value}: found {len(source_results)} results for '{query}'")
            except Exception as e:
                logger.error(f"Search error on {client.source.value}: {e}")
                results[client.source] = []
        return results

    async def compare_prices(self, identifier: str) -> dict[str, Any]:
        """複数ソースの価格比較レポート生成"""
        source_results = {}
        for client in self.clients:
            try:
                result = await client.fetch_figure(identifier)
                if result:
                    source_results[client.source.value] = result.to_dict()
            except Exception as e:
                logger.error(f"Compare error on {client.source.value}: {e}")
                source_results[client.source.value] = {"error": str(e)}

        # 比較サマリー構築
        summary = {
            "identifier": identifier,
            "sources_checked": list(source_results.keys()),
            "source_results": source_results,
            "best_price": None,
            "best_source": None,
        }

        valid_results = {k: v for k, v in source_results.items() if "error" not in v and v.get("lowest_price_jpy")}
        if valid_results:
            best_source = min(valid_results.keys(), key=lambda k: valid_results[k]["lowest_price_jpy"])
            summary["best_price"] = valid_results[best_source]["lowest_price_jpy"]
            summary["best_source"] = best_source

        return summary


# ═══════════════════════════════════════════════════════════════════════
# Convenience Functions
# ═══════════════════════════════════════════════════════════════════════

async def get_figure_price(identifier: str, source: PriceSource | None = None) -> FigurePrice | None:
    """単一フィギュアの価格取得（簡易関数）"""
    async with FigurePriceAggregator() as agg:
        return await agg.fetch_best_price(identifier, source)


async def search_figures(query: str, limit: int = 10) -> dict[PriceSource, list[FigurePrice]]:
    """フィギュア検索（簡易関数）"""
    async with FigurePriceAggregator() as agg:
        return await agg.search_all_sources(query, limit)


async def compare_figure_prices(identifier: str) -> dict[str, Any]:
    """価格比較レポート（簡易関数）"""
    async with FigurePriceAggregator() as agg:
        return await agg.compare_prices(identifier)


# ═══════════════════════════════════════════════════════════════════════
# CLI / Testing
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    async def main():
        if len(sys.argv) < 2:
            print("Usage: python -m kensho.scraping.sources.anime_figure_api <command> [args]")
            print("Commands:")
            print("  price <identifier>     - Get best price for a figure")
            print("  search <query>         - Search figures")
            print("  compare <identifier>   - Compare prices across sources")
            return

        cmd = sys.argv[1]

        if cmd == "price" and len(sys.argv) >= 3:
            identifier = sys.argv[2]
            result = await get_figure_price(identifier)
            if result:
                print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            else:
                print("Not found")

        elif cmd == "search" and len(sys.argv) >= 3:
            query = sys.argv[2]
            limit = int(sys.argv[3]) if len(sys.argv) >= 4 else 10
            results = await search_figures(query, limit)
            for source, items in results.items():
                print(f"\n=== {source.value} ({len(items)} results) ===")
                for item in items[:5]:
                    print(f"  {item.name} - ¥{item.lowest_price_jpy} ({item.in_stock_count}/{item.total_offers_count} in stock)")

        elif cmd == "compare" and len(sys.argv) >= 3:
            identifier = sys.argv[2]
            result = await compare_figure_prices(identifier)
            print(json.dumps(result, ensure_ascii=False, indent=2))

        else:
            print("Invalid command")

    asyncio.run(main())