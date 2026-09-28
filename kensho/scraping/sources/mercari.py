"""mercari (Mercari) — Japan market specialized scraper for product, price, and review extraction"""

from __future__ import annotations

import re
import time
from typing import Any

from .common import HEADERS, _fetch_with_retry, has_skip_keyword
from ..run_budget import RunBudget, check_budget

# ── 第6収集源: mercari (Mercari) ──
_MERCARI_BASE: str = "https://www.mercari.com"
_MERCARI_SEARCH: str = "https://jp.mercari.com/search"
_MERCARI_MAX_PAGES: int = 10
_MERCARI_MAX_ITEMS: int = 500


def scrape_mercari(
    out: Any,
    processed_set: set[str],
    account_keys: list[str],
    *,
    budget: RunBudget | None = None,
    search_keyword: str | None = None,
) -> list[dict[str, Any]]:
    """Mercariの日本市場向けプロダクト、価格、レビューデータを抽出。

    一覧ページ → 商品詳細ページ → 価格・レビュー抽出 の3段階。
    戻り値: scraped.json 互換のアイテムリスト。

    budget (t_b64c35ea): run予算。渡された場合、ページ/商品詳細の区切りで
    打ち切り。価格・レビュー抽出まで残らない（これまでの収集は保持）。
    30ページ×各30商品と最重量のため、collector側の phase 単位打ち切りだけでは
    1ソース内で上限を超過しうるための内側ガード。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp["Accept-Language"] = "ja,en-US;q=0.9,en;q=0.8"
    headers_jp["X-Requested-With"] = "XMLHttpRequest"
    items: list[dict[str, Any]] = []
    seen_product_ids: set[str] = set()

    # 検索クエリ生成
    if search_keyword:
        query = search_keyword
    else:
        # デフォルトで人気商品を取得
        query = "人気商品"

    for page in range(1, _MERCARI_MAX_PAGES + 1):
        if budget is not None and check_budget(budget, "mercari内ページ", out):
            break

        # 検索URL（Mercariの商用検索）
        search_url: str = f"{_MERCARI_SEARCH}?keyword={query}&page={page}"

        try:
            # リストページ取得（指数バックオフ付き）
            code, html, _ = _fetch_with_retry(search_url, timeout=30, source="mercari")
            if code != 200:
                out(f"  [MERC] ページ{page}: HTTP {code} - 終了")
                break

            # 商品リンク抽出（価格・レビュー付き）
            # Mercariの商品カードパターンを検出
            product_items: list[tuple[str, str, str, str, str]] = []  # (id, url, price, title, seller)

            # 商品カードを含むリスト要素を抽出
            for m in re.finditer(r'<a[^>]*href="https?://jp\\.mercari\\.com/item/(\d+)"[^>]*>\s*<div[^>]*class="[^\"]*item-name[^\"]*"[^>]*>\s*<h2[^>]*>([^<]+)</h2>\s*</div>\s*<div[^>]*class="[^\"]*price[^\"]*"[^>]*>\s*<span[^>]*class="[^\"]*price-value[^\"]*"[^>]*>\s*([¥\d,.]+)\s*</span>\s*<span[^>]*class="[^\"]*currency[^\"]*"[^>]*>[^<]*</span>\s*</div>\s*<div[^>]*class="[^\"]*shop-name[^\"]*"[^>]*>\s*<span[^>]*>([^<]+)</span>\s*</div>\s*<div[^>]*class="[^\"]*condition[^\"]*"[^>]*>\s*<span[^>]*>([^<]+)</span>\s*</div>\s*</a>', html, re.DOTALL):
                item_id, title, price, seller, condition = m.groups()
                if item_id not in seen_product_ids and item_id not in processed_set:
                    url = f"https://jp.mercari.com/item/{item_id}"
                    product_items.append((item_id, url, price, title, seller, condition))
                    seen_product_ids.add(item_id)

            if not product_items:
                # 代替パターンを試す
                for m in re.finditer(r'<div[^>]*class="[^\"]*item-card[^\"]*"[^>]*>\s*<a[^>]*href="https?://jp\\.mercari\\.com/item/(\d+)"[^>]*>\s*<img[^>]*alt="([^"]*)"[^>]*/>\s*<div[^>]*class="[^\"]*item-info[^\"]*"[^>]*>\s*<h3[^>]*>([^<]+)</h3>\s*<div[^>]*class="[^\"]*item-price[^\"]*"[^>]*>\s*<span[^>]*class="[^\"]*price[^\"]*"[^>]*>\s*([¥\d,.]+)\s*</span>\s*<span[^>]*class="[^\"]*seller[^\"]*"[^>]*>\s*([^<]+)\s*</span>\s*</div>\s*<div[^>]*class="[^\"]*item-condition[^\"]*"[^>]*>\s*<span[^>]*>([^<]+)</span>\s*</div>\s*</a>', html, re.DOTALL):
                    item_id, title, price, seller, condition = m.groups()
                    if item_id not in seen_product_ids and item_id not in processed_set:
                        url = f"https://jp.mercari.com/item/{item_id}"
                        product_items.append((item_id, url, price, title, seller, condition))
                        seen_product_ids.add(item_id)

            if not product_items:
                out(f"  [MERC] ページ{page}: リンクなし - 終了")
                break

            out(f"  [MERC] ページ{page}: 商品走査{len(product_items)}件（収集件数ではない）")

            # 商品URLから価格・レビュー抽出
            for item_id, product_url, price, title, seller, condition in product_items:
                if budget is not None and check_budget(budget, "mercari内商品", out):
                    break

                try:
                    # Mercariの商品詳細ページにアクセス
                    detail_url: str = f"https://jp.mercari.com/item/{item_id}"

                    code2, html2, _ = _fetch_with_retry(
                        detail_url, referer=search_url, timeout=45, source="mercari"
                    )
                    if code2 != 200:
                        continue

                    # タイトルの抽出改善
                    extracted_title: str = title
                    title_patterns = [
                        r'<h1[^>]*class="[^\"]*item-name[^\"]*"[^>]*>([^<]+)</h1>',
                        r'<h1[^>]*>([^<]+)</h1>',
                        r'<title>([^|]+)',
                        r'<meta property="og:title" content="([^"]*)">',
                    ]

                    for pattern in title_patterns:
                        m_title = re.search(pattern, html2, re.DOTALL)
                        if m_title:
                            extracted_title = m_title.group(1).strip()
                            break

                    # 価格の抽出改善
                    extracted_price: str = price.strip()
                    if extracted_price and extracted_price.startswith("￥"):
                        extracted_price = extracted_price[1:].replace(",", "")

                    # 価格の正規化抽出（複数のパターンに対応）
                    price_alt_patterns = [
                        r'(?:販売価格|価格|￥)[\s]*[¥]*(\d+(?:,\d+)*)',
                        r'(?:定価|通常価格)[\s]*[¥]*(\d+(?:,\d+)*)',
                        r'(?:ポイント)[\s]*(\d+)%',
                        r'class="[^\"]*price-value[^\"]*"[^>]*>\s*([¥\d,.]+)\s*<',
                    ]

                    extracted_price: str = ""
                    for pattern in price_alt_patterns:
                        m_price = re.search(pattern, html2, re.DOTALL)
                        if m_price:
                            extracted_price = m_price.group(1).replace(",", "")
                            break

                    # 条件の抽出
                    extracted_condition: str = condition
                    condition_patterns = [
                        r'class="[^\"]*condition[^\"]*"[^>]*>([^<]+)</[^>]*>\s*',
                        r'class="[^\"]*item-status[^\"]*"[^>]*>([^<]+)<',
                        r'新品[^\s]*', r'中古[^\s]*', r'リファurb[^\s]*',
                    ]

                    for pattern in condition_patterns:
                        m_condition = re.search(pattern, html2, re.DOTALL)
                        if m_condition:
                            extracted_condition = m_condition.group(1).strip() if pattern != "新品[^\s]*" else "new"
                            if pattern != "新品[^\s]*":
                                extracted_condition = m_condition.group(0).strip()
                            break

                    # レビースコア抽出
                    review_score: float = 0.0
                    review_count: int = 0

                    # レビース表示の抽出
                    review_patterns = [
                        r'(\d+(?:\.\d+)?)\s*点\s*\(評価\s*(\d+)件\)',
                        r'(\d+(?:\.\d+)?)/5\s*点\s*\(評価\s*(\d+)件\)',
                        r'(\d+(?:\.\d+)?)\s*<[^>]*class="[^\"]*rating[^\"]*"[^>]*>.*?\(評価\s*(\d+)件\)',
                    ]

                    for pattern in review_patterns:
                        m_review = re.search(pattern, html2, re.DOTALL)
                        if m_review:
                            review_score = float(m_review.group(1))
                            review_count = int(m_review.group(2))
                            break

                    # カテゴリの抽出
                    category: list[str] = []
                    category_patterns = [
                        r'<nav[^>]*class="[^\"]*breadcrumb[^\"]*"[^>]*>(.*?)</nav>',
                        r'<div[^>]*class="[^\"]*category-path[^\"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>',
                    ]

                    for pattern in category_patterns:
                        m_category = re.search(pattern, html2, re.DOTALL)
                        if m_category:
                            if pattern == r'<nav[^>]*class="[^\"]*breadcrumb[^\"]*"[^>]*>(.*?)</nav>':
                                crumbs = re.findall(r'<a[^>]*>([^<]+)</a>', m_category.group(1))
                                category = [c.strip() for c in crumbs if c.strip()]
                            else:
                                category.append(m_category.group(1).strip())
                            break

                    # 画像の抽出
                    images: list[str] = []
                    image_patterns = [
                        r'<meta property="og:image" content="([^"]*)">',
                        r'<div[^>]*class="[^\"]*item-image[^\"]*"[^>]*>\s*<img[^>]*src="([^"]*)"[^>]*alt="[^"]*"',r
                    ]

                    for pattern in image_patterns:
                        if pattern == r'<meta property="og:image" content="([^"]*)">':
                            m_images = re.search(pattern, html2)
                            if m_images:
                                images.append(m_images.group(1))
                        else:
                            m_images = re.findall(pattern, html2, re.DOTALL)
                            images.extend(m_images)

                    # 店舗情報の抽出改善
                    seller_alt: str = seller
                    seller_patterns = [
                        r'<span[^>]*class="[^\"]*shop-name[^\"]*"[^>]*>([^<]+)</span>',
                        r'<div[^>]*class="[^\"]*seller-info[^\"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>',
                        r'<strong[^>]*class="[^\"]*shop-name[^\"]*"[^>]*>([^<]+)</strong>',
                    ]

                    for pattern in seller_patterns:
                        m_seller = re.search(pattern, html2, re.DOTALL)
                        if m_seller:
                            seller_alt = m_seller.group(1).strip()
                            break

                    # レビューコンテンツの抽出
                    reviews: list[dict[str, Any]] = []
                    review_patterns = [
                        r'<div[^>]*class="[^\"]*review-item[^\"]*"[^>]*>\s*<div[^>]*class="[^\"]*review-header[^\"]*"[^>]*>\s*<span[^>]*class="[^\"]*reviewer-name[^\"]*"[^>]*>([^<]+)</span>\s*<span[^>]*class="[^\"]*review-date[^\"]*"[^>]*>([^<]+)</span>\s*</div>\s*<div[^>]*class="[^\"]*review-content[^\"]*"[^>]*>\s*(.*?)</div>\s*</div>',
                        r'<div[^>]*class="[^\"]*comment-item[^\"]*"[^>]*>\s*<div[^>]*class="[^\"]*comment-body[^\"]*"[^>]*>\s*<span[^>]*class="[^\"]*comment-user[^\"]*"[^>]*>([^<]+)</span>\s*<span[^>]*class="[^\"]*comment-date[^\"]*"[^>]*>([^<]+)</span>\s*<p[^>]*class="[^\"]*comment-text[^\"]*"[^>]*>([^<]+)</p>\s*</div>\s*</div>',
                    ]

                    for pattern in review_patterns:
                        matches = re.findall(pattern, html2, re.DOTALL)
                        for match in matches:
                            if len(match) == 3:  # reviewer, date, content
                                reviewer, date, content = match
                                reviews.append({
                                    "reviewer": reviewer.strip(),
                                    "date": date.strip(),
                                    "content": content.strip(),
                                    "rating": "",
                                })
                            elif len(match) == 4:  # reviewer, date, content, rating
                                reviewer, date, content, rating = match
                                reviews.append({
                                    "reviewer": reviewer.strip(),
                                    "date": date.strip(),
                                    "content": content.strip(),
                                    "rating": rating.strip(),
                                })

                    applied: dict[str, None] = {k: None for k in account_keys}

                    items.append({
                        "detail_url": detail_url,
                        "title": extracted_title,
                        "price": extracted_price,
                        "condition": extracted_condition,
                        "review_score": review_score,
                        "review_count": review_count,
                        "seller": seller_alt,
                        "category": category,
                        "images": images,
                        "reviews": reviews,
                        "source": "mercari",
                        "time": 0.0,
                        "applied": applied,
                        "keyword_flag": has_skip_keyword(extracted_title),
                    })

                    out(f"    ✅ {extracted_title[:65]}... - ¥{extracted_price}")

                except Exception as e:
                    out(f"    [WARN] mercari商品処理失敗: {e}")

            if len(product_items) < 10:  # 最終ページ
                break

            time.sleep(0.5)  # 優しめの間隔

        except Exception as e:
            out(f"  [MERC] ページ{page}: ERROR {type(e).__name__}: {e}")
            break

    out(f"  [MERC] 計{len(items)}件取得")
    return items