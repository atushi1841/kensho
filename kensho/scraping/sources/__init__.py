"""scraping.sources — 懸賞収集源モジュール"""

from __future__ import annotations

from .chancecom import scrape_chancecom
from .common import (
    BASE_URL,
    HEADERS,
    KENKAKU_BASE,
    _decode_response,
    _fetch_with_retry,
    _is_expired,
    fetch,
    has_skip_keyword,
    load_json,
    save_json,
)
from .cpmeikan import scrape_cpmeikan
from .kema import scrape_kema
from .kenkaku import scrape_kenkaku
from .kensho_everyday import scrape_kensho_everyday
from .kenshouclub import scrape_kenshouclub
from .knshow import (
    extract_deadline_and_winners,
    extract_detail_links,
    extract_rd_link,
    fetch_listing_with_retry,
    is_x_url,
    resolve_redirect,
)
from .prtimes import scrape_prtimes
from .scrapling_fetch import (
    is_scrapling_available,
    scrapling_fetch,
    scrapling_fetch_with_retry,
)
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
    "fetch_listing_with_retry",
    "resolve_redirect",
    "is_x_url",
    "extract_deadline_and_winners",
    "scrape_kenkaku",
    "scrape_kenshouclub",
    "scrape_cpmeikan",
    "scrape_kema",
    "scrape_kensho_everyday",
    "scrapling_fetch",
    "scrapling_fetch_with_retry",
    "is_scrapling_available",
    "scrape_twscrape",
    "scrape_chancecom",
    "scrape_prtimes",
]
