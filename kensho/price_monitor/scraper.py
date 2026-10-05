"""Scraper and parser engine for Japanese EC platforms."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .models import ECPlatform, PriceItem

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


def detect_platform(url: str) -> ECPlatform:
    """Detect EC Platform from product URL."""
    domain = urlparse(url).netloc.lower()
    if "yahoo.co.jp" in domain:
        return ECPlatform.YAHOO_SHOPPING
    elif "rakuten.co.jp" in domain:
        return ECPlatform.RAKUTEN
    elif "mercari.com" in domain:
        return ECPlatform.MERCARI
    elif "suruga-ya.jp" in domain:
        return ECPlatform.SURUGAYA
    return ECPlatform.GENERIC


def clean_price(price_str: str | int | float | None) -> int | None:
    """Extract integer price in JPY from messy text."""
    if price_str is None:
        return None
    if isinstance(price_str, (int, float)):
        return int(price_str)
    cleaned = re.sub(r"[¥,円\s\\]", "", str(price_str))
    match = re.search(r"\d+", cleaned)
    if match:
        try:
            return int(match.group())
        except ValueError:
            return None
    return None


class ECPriceScraper:
    """Fetches and parses Japanese EC product prices."""

    def __init__(self, timeout_sec: int = 15):
        self.timeout_sec = timeout_sec

    def fetch_product_info(self, url: str) -> PriceItem:
        """Fetch URL and parse product title, price, and availability."""
        platform = detect_platform(url)
        headers = dict(DEFAULT_HEADERS)

        try:
            with httpx.Client(headers=headers, timeout=self.timeout_sec, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code >= 400:
                    raise ValueError(f"HTTP error {resp.status_code} fetching {url}")
                html_text = resp.text
        except Exception as e:
            logger.warning(f"Failed to fetch {url} via HTTP: {e}")
            raise

        return self.parse_html(url, html_text, platform)

    def parse_html(self, url: str, html_text: str, platform: ECPlatform | None = None) -> PriceItem:
        """Parse HTML string according to platform rules."""
        if platform is None:
            platform = detect_platform(url)

        soup = BeautifulSoup(html_text, "html.parser")
        title: str = "Unknown Product"
        price_jpy: int | None = None
        in_stock: bool = True
        seller: str | None = None
        image_url: str | None = None

        # 1. Try JSON-LD Product schema
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    data = data[0] if data else {}
                if data.get("@type") == "Product":
                    title = data.get("name") or title
                    offers = data.get("offers", {})
                    if isinstance(offers, list) and offers:
                        offers = offers[0]
                    if isinstance(offers, dict):
                        p = offers.get("price") or offers.get("lowPrice")
                        price_jpy = clean_price(p)
                        avail = offers.get("availability", "")
                        if "OutOfStock" in avail:
                            in_stock = False
                    if "image" in data:
                        img = data["image"]
                        image_url = img[0] if isinstance(img, list) else img
            except Exception:
                pass

        # 2. Platform specific regex & CSS selectors if JSON-LD missing
        if platform == ECPlatform.YAHOO_SHOPPING:
            if not price_jpy:
                p_tag = soup.find(class_=re.compile(r"price|ItemPrice", re.I))
                if p_tag:
                    price_jpy = clean_price(p_tag.get_text())
            if title == "Unknown Product":
                t_tag = soup.find("h1") or soup.find(class_=re.compile(r"title|ItemTitle", re.I))
                if t_tag:
                    title = t_tag.get_text().strip()

        elif platform == ECPlatform.RAKUTEN:
            if not price_jpy:
                p_tag = soup.find(class_=re.compile(r"price2|item-price|price", re.I))
                if p_tag:
                    price_jpy = clean_price(p_tag.get_text())
            if title == "Unknown Product":
                t_tag = soup.find(class_=re.compile(r"item-name|product-name", re.I)) or soup.find("h1")
                if t_tag:
                    title = t_tag.get_text().strip()

        elif platform == ECPlatform.MERCARI:
            if not price_jpy:
                p_tag = soup.find("div", {"data-testid": "price"}) or soup.find(class_=re.compile(r"price", re.I))
                if p_tag:
                    price_jpy = clean_price(p_tag.get_text())
            if title == "Unknown Product":
                t_tag = soup.find("h1") or soup.find("div", {"data-testid": "name"})
                if t_tag:
                    title = t_tag.get_text().strip()
            # Out of stock check (sold out button/badge)
            if soup.find(string=re.compile(r"売り切れ|SOLD", re.I)):
                in_stock = False

        # 3. Fallback generic meta tags
        if not price_jpy:
            meta_price = (
                soup.find("meta", property="product:price:amount")
                or soup.find("meta", property="og:price:amount")
            )
            if meta_price and meta_price.get("content"):
                price_jpy = clean_price(meta_price["content"])

        if title == "Unknown Product":
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
            elif soup.title:
                title = soup.title.get_text().strip()

        if not price_jpy:
            # Last resort regex over HTML
            m = re.search(r'[¥\\]\s*([0-9,]+)', html_text)
            if m:
                price_jpy = clean_price(m.group(1))

        if price_jpy is None:
            raise ValueError(f"Could not extract price from {url}")

        return PriceItem(
            url=url,
            title=title[:200],
            price_jpy=price_jpy,
            platform=platform,
            in_stock=in_stock,
            scraped_at=datetime.utcnow(),
            seller=seller,
            image_url=image_url,
        )
