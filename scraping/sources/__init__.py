"""scraping.sources — 懸賞収集源モジュール"""
from __future__ import annotations

from .common import (
    fetch,
    _fetch_with_retry,
    _decode_response,
    load_json,
    save_json,
    _is_expired,
    has_skip_keyword,
    HEADERS,
    BASE_URL,
    KENKAKU_BASE,
)
from .knshow import (
    extract_detail_links,
    extract_rd_link,
    resolve_redirect,
    is_x_url,
    extract_deadline_and_winners,
)
from .kenkaku import scrape_kenkaku
from .kenshouclub import scrape_kenshouclub
from .cpmeikan import scrape_cpmeikan
from .kema import scrape_kema
from .kensho_everyday import scrape_kensho_everyday
from .twscrape import scrape_twscrape

__all__ = [
    "fetch",
    "_fetch_with_retry",
    "_decode_response",
    "load_json",
    "save_json",
    "_is_expired",
    "has_skip_keyword",
    "HEADERS",
    "BASE_URL",
    "KENKAKU_BASE",
    "extract_detail_links",
    "extract_rd_link",
    "resolve_redirect",
    "is_x_url",
    "extract_deadline_and_winners",
    "scrape_kenkaku",
    "scrape_kenshouclub",
    "scrape_cpmeikan",
    "scrape_kema",
    "scrape_kensho_everyday",
    "scrape_twscrape",
]
