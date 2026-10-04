"""_apify_auth — Apify API のトークンをURLに出さないための共通ヘルパー

背景(2026-10-04): Apifyを `?token=...` で呼ぶと requests/urllib の例外文に
トークンが混入し、それがJSONやログに保存されて公開リポジトリへ漏洩した
（GitHub Secret Scanning 検知）。以降は Authorization ヘッダを使う。
"""
from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"[?&]token=([^&\s]+)")
_REDACT = (
    (re.compile(r"(token=)[A-Za-z0-9_\-\.]+"), r"\1***REDACTED***"),
    (re.compile(r"apify_api_[A-Za-z0-9]+"), "apify_api_***REDACTED***"),
)


def redact_secrets(text: Any) -> str:
    s = str(text)
    for pat, rep in _REDACT:
        s = pat.sub(rep, s)
    return s


def split_token(url: str) -> tuple[str, str]:
    """URLから token= を抜き、(トークンなしURL, トークン) を返す。"""
    m = _TOKEN_RE.search(url or "")
    if not m:
        return url, ""
    tok = m.group(1)
    return _TOKEN_RE.sub(lambda mm: "?" if mm.group(0)[0] == "?" else "", url).rstrip("?&"), tok


def apify_get(url: str, **kwargs: Any):
    """requests.get 互換。URL内の token= を Authorization ヘッダへ移す。"""
    import requests

    clean, tok = split_token(url)
    if tok:
        h = dict(kwargs.pop("headers", None) or {})
        h.setdefault("Authorization", "Bearer " + tok)
        kwargs["headers"] = h
    return requests.get(clean, **kwargs)


def apify_urlopen(req_or_url, headers: dict | None = None, timeout: int = 30, **kwargs: Any):
    """urllib.request.urlopen 互換。URL/Request内の token= を Authorization へ移す。"""
    import urllib.request

    base: dict[str, str] = {}
    data = None
    method = None
    if isinstance(req_or_url, urllib.request.Request):
        base = dict(req_or_url.header_items())
        url = req_or_url.full_url
        data = req_or_url.data
        method = req_or_url.get_method()
    else:
        url = str(req_or_url)
    clean, tok = split_token(url)
    if headers:
        base.update(headers)
    if tok:
        base.setdefault("Authorization", "Bearer " + tok)
    req = urllib.request.Request(clean, data=data, headers=base, method=method)
    return urllib.request.urlopen(req, timeout=timeout, **kwargs)
