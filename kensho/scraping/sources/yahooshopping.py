"""yahoo-shopping (Yahoo! Shopping) — Japan market specialized scraper for product, price, and review extraction"""

from __future__ import annotations

import re
import time
from typing import Any

from .common import HEADERS, _fetch_with_retry, has_skip_keyword
from ..run_budget import RunBudget, check_budget

# ── 第4収集源: yahoo-shopping (Yahoo! Shopping) ──
_YAHOO_SHOPPING_BASE: str = "https://shopping.yahoo.co.jp"
_YAHOO_SHOPPING_SEARCH: str = "https://shopping.yahoo.co.jp/search?p="
_YAHOO_SHOPPING_MAX_PAGES: int = 10
_YAHOO_SHOPPING_MAX_ITEMS: int = 500


def scrape_yahooshopping(
    out: Any,
    processed_set: set[str],
    account_keys: list[str],
    *,
    budget: RunBudget | None = None,
    search_keyword: str | None = None,
) -> list[dict[str, Any]]:
    """Yahoo! Shoppingの日本市場向けプロダクト、価格、レビューデータを抽出。

    一覧ページ → 商品詳細ページ → 価格・レビュー抽出 の3段階。
    戻り値: scraped.json 互換のアイテムリスト。

    budget (t_b64c35ea): run予算。渡された場合、ページ/商品詳細の区切りで
    打ち切り。価格・レビュー抽出まで残らない（これまでの収集は保持）。
    30ページ×各30商品と最重量のため、collector側の phase 単位打ち切りだけでは
    1ソース内で上限を超過しうるための内側ガード。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
    items: list[dict[str, Any]] = []
    seen_product_urls: set[str] = set()

    # 検索クエリ生成
    if search_keyword:
        query = search_keyword
    else:
        # デフォルトで人気商品を取得
        query = "人気の商品"

    for page in range(1, _YAHOO_SHOPPING_MAX_PAGES + 1):
        if budget is not None and check_budget(budget, "yahoo-shopping内ページ", out):
            break

        # 検索URL
        search_url: str = f"{_YAHOO_SHOPPING_SEARCH}{query}&pstart={page}"

        try:
            # リストページ取得（指数バックオフ付き）
            code, html, _ = _fetch_with_retry(search_url, timeout=30, source="yahoo-shopping")
            if code != 200:
                out(f"  [YSHOP] ページ{page}: HTTP {code} - 終了")
                break

            # 商品リンク抽出（価格・レビュー付き）
            # Yahoo! Shoppingの商品カードパターンを検出
            product_links: list[tuple[str, str, str]] = []  # (url, price, title)

            # 商品タイトルを含むカード要素を抽出
            for m in re.finditer(r'data-product-id="(\d+)".*?<a[^>]*href="(https?://item[^\"]*)"[^>]*>(?:.*?<span[^>]*>(.*?)</span>)?.*?<span class="[^\"]*price[^\"]*">\s*([¥\d,.]+)\s*</span>', html, re.DOTALL):
                product_id, url, title, price = m.groups()
                if url not in seen_product_urls and url not in processed_set:
                    product_links.append((url, price, title))
                    seen_product_urls.add(url)

            if not product_links:
                # 代替パターンを試す
                for m in re.finditer(r'<a[^>]*href="(https?://item[^\"]*)"[^>]*>\s*<img[^>]*alt="([^"]*)"[^>]*/>\s*<div[^>]*class="[^\"]*product-info[^\"]*"[^>]*>\s*<h3[^>]*>([^<]*)</h3>\s*<div[^>]*class="[^\"]*price[^\"]*"[^>]*>\s*([¥\d,.]+)\s*</div>', html, re.DOTALL):
                    url, title, price = m.groups()
                    if url not in seen_product_urls and url not in processed_set:
                        product_links.append((url, price, title))
                        seen_product_urls.add(url)

            if not product_links:
                out(f"  [YSHOP] ページ{page}: リンクなし - 終了")
                break

            out(f"  [YSHOP] ページ{page}: 商品走査{len(product_links)}件（収集件数ではない）")

            # 商品URLから価格・レビュー抽出
            for product_url, price, title in product_links:
                if budget is not None and check_budget(budget, "yahoo-shopping内商品", out):
                    break

                try:
                    code2, html2, _ = _fetch_with_retry(
                        product_url, referer=search_url, timeout=45, source="yahoo-shopping"
                    )
                    if code2 != 200:
                        continue

                    # タイトルの再抽出（複数の可能なセレクタがある）
                    extracted_title: str = title
                    title_patterns = [
                        r'<h1[^>]*class="[^\"]*product-name[^\"]*"[^>]*>([^<]+)</h1>',
                        r'<h1[^>]*>([^<]+)</h1>',
                        r'<title>([^|]+)',
                    ]

                    for pattern in title_patterns:
                        m_title = re.search(pattern, html2, re.DOTALL)
                        if m_title:
                            extracted_title = m_title.group(1).strip()
                            break

                    # 価格の抽出改善
                    extracted_price: str = price.strip()
                    if extracted_price and extracted_price.startswith("¥"):
                        extracted_price = extracted_price[1:].replace(",", "")

                    # 条件の抽出
                    condition: str = ""
                    condition_patterns = [
                        r'class="[^\"]*condition[^\"]*"[^>]*>([^<]+)</[^>]*>\s*',
                        r'新品[^\s]*', r'中古[^\s]*', r'リファurb[^\s]*',
                    ]

                    for pattern in condition_patterns:
                        m_condition = re.search(pattern, html2, re.DOTALL)
                        if m_condition:
                            condition = m_condition.group(1).strip() if pattern != "新品[^\s]*" else "new"
                            if pattern != "新品[^\s]*":
                                condition = m_condition.group(0).strip()
                            break

                    # レビュースコア抽出
                    review_score: float = 0.0
                    review_count: int = 0

                    review_score_match = re.search(r'class="[^\"]*score[^\"]*"[^>]*>(\d+(?:\.\d+)?)</[^>]*>\s*\(評価\s*(\d+)件\)', html2, re.DOTALL)
                    if review_score_match:
                        review_score = float(review_score_match.group(1))
                        review_count = int(review_score_match.group(2))

                    # 価格の正規化抽出（複数のパターンに対応）
                    price_alt_patterns = [
                        r'(?:販売価格|価格|￥)[\s]*[¥]*(\d+(?:,\d+)*)',
                        r'(?:定価|通常価格)[\s]*[¥]*(\d+(?:,\d+)*)',
                        r'(?:ポイント)[\s]*(\d+)%',
                    ]

                    extracted_price: str = ""
                    for pattern in price_alt_patterns:
                        m_price = re.search(pattern, html2, re.DOTALL)
                        if m_price:
                            extracted_price = m_price.group(1).replace(",", "")
                            break

                    # カテゴリの抽出
                    category: list[str] = []
                    category_match = re.search(r'<nav[^>]*class="[^\"]*breadcrumb[^\"]*"[^>]*>(.*?)</nav>', html2, re.DOTALL)
                    if category_match:
                        crumbs = re.findall(r'<a[^>]*>([^<]+)</a>', category_match.group(1))
                        category = [c.strip() for c in crumbs if c.strip()]

                    # 画像の抽出
                    images: list[str] = []
                    image_matches = re.findall(r'<img[^>]*src="(https?://[^\"\']+shopping-item-image[^\"\']*)"[^>]*alt="[^"]*"', html2, re.DOTALL)
                    images.extend(image_matches)

                    # 店舗情報の抽出
                    seller: str = ""
                    seller_match = re.search(r'<span[^>]*class="[^\"]*shop-name[^\"]*"[^>]*>([^<]+)</span>', html2, re.DOTALL)
                    if seller_match:
                        seller = seller_match.group(1).strip()

                    # レビューコンテンツの抽出
                    reviews: list[dict[str, Any]] = []
                    review_blocks = re.findall(r'<div[^>]*class="[^\"]*review-item[^\"]*"[^>]*>(.*?)</div>', html2, re.DOTALL)

                    for review_block in review_blocks:
                        reviewer = ""
                        reviewer_match = re.search(r'<span[^>]*class="[^\"]*reviewer-name[^\"]*"[^>]*>([^<]+)</span>', review_block)
                        if reviewer_match:
                            reviewer = reviewer_match.group(1).strip()

                        rating = ""
                        rating_match = re.search(r'<span[^>]*class="[^\"]*review-rating[^\"]*"[^>]*>(\d+(?:\.\d+)?)</span>', review_block)
                        if rating_match:
                            rating = rating_match.group(1)

                        content = ""
                        content_match = re.search(r'<p[^>]*class="[^\"]*review-text[^\"]*"[^>]*>([^<]+)</p>', review_block, re.DOTALL)
                        if content_match:
                            content = content_match.group(1).strip()

                        date = ""
                        date_match = re.search(r'<time[^>]*datetime="([^"]+)"[^>]*>([^<]+)</time>', review_block)
                        if date_match:
                            date = date_match.group(1)

                        reviews.append({
                            "reviewer": reviewer,
                            "rating": rating,
                            "content": content,
                            "date": date,
                        })

                    applied: dict[str, None] = {k: None for k in account_keys}

                    items.append({
                        "detail_url": product_url,
                        "title": extracted_title,
                        "price": extracted_price,
                        "condition": condition,
                        "review_score": review_score,
                        "review_count": review_count,
                        "seller": seller,
                        "category": category,
                        "images": images,
                        "reviews": reviews,
                        "source": "yahoo-shopping",
                        "time": 0.0,
                        "applied": applied,
                        "keyword_flag": has_skip_keyword(extracted_title),
                    })

                    out(f"    ✅ {extracted_title[:65]}... - ¥{extracted_price}")

                except Exception as e:
                    out(f"    [WARN] yahoo-shopping商品処理失敗: {e}")

            if len(product_links) < 10:  # 最終ページ
                break

            time.sleep(0.5)  # 優しめの間隔

        except Exception as e:
            out(f"  [YSHOP] ページ{page}: ERROR {type(e).__name__}: {e}")
            break

    out(f"  [YSHOP] 計{len(items)}件取得")
    return items