"""Kensho Collector — knshow.com + ken-kaku.com + kenshou.club + cp.meikan.org からX懸賞URLを収集"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from kensho.core.config import load as load_config
from kensho.scraping.sources import (
    BASE_URL,
    _fetch_with_retry,
    _is_expired,
    extract_deadline_and_winners,
    extract_detail_links,
    extract_rd_link,
    fetch,
    is_x_url,
    load_json,
    resolve_redirect,
    scrape_chancecom,
    scrape_cpmeikan,
    scrape_kema,
    scrape_kenkaku,
    scrape_kenshouclub,
    scrape_twscrape,
    scrapling_fetch,
    scrapling_fetch_with_retry,
)
from kensho.utils.backup import safe_save_json, try_recover_collected, verify_collected_integrity


def collect(cfg: dict[str, Any] | None = None, log: Any = None, max_pages: int = 99) -> tuple[int, int, int]:
    """
    収集を実行。
    cfg: config.yaml の内容（Noneなら自動読込）
    log: LogWriter インスタンス（あれば記録）
    max_pages: 取得する最大ページ数（デフォルト99=全ページ）
    戻り値: (success_count, error_count, total_collected_count)
    """
    if cfg is None:
        cfg = load_config()

    account_keys: list[str] = [a["key"] for a in cfg.get("accounts", [])]

    col_cfg: dict[str, Any] = cfg.get("collection", {})
    max_items: int = col_cfg.get("max_items", 200)

    # ── Scrapling モード（Cloudflare突破）──
    use_scrapling: bool = col_cfg.get("use_scrapling", False)
    _do_fetch = scrapling_fetch if use_scrapling else fetch
    _do_fetch_retry = scrapling_fetch_with_retry if use_scrapling else _fetch_with_retry

    DATA_DIR: Path = Path(cfg["general"]["project_dir"]) / "data"
    PROCESSED_FILE: Path = DATA_DIR / "processed.json"
    COLLECTED_FILE: Path = DATA_DIR / "collected.json"

    def out(msg: str) -> None:
        if log:
            log.write(msg)
        else:
            print(msg, flush=True)

    out(f"[Kensho Collection] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out(f"  最大件数: {max_items}, アカウント: {account_keys}")

    t0: float = time.time()

    processed: dict[str, Any] = load_json(PROCESSED_FILE, {})
    processed_set: set[str] = set(processed.get("ids", []))
    out(f"  既処理: {len(processed_set)}件")

    integrity: dict[str, Any] = verify_collected_integrity(COLLECTED_FILE, PROCESSED_FILE)
    if not integrity["ok"]:
        out(f"  [WARN] {integrity['message']}")
        recovered: bool = try_recover_collected(PROCESSED_FILE, COLLECTED_FILE, account_keys)
        if recovered and COLLECTED_FILE.exists() and COLLECTED_FILE.stat().st_size > 500:
            existing_collected: list[dict[str, Any]] = load_json(COLLECTED_FILE, {}).get("collected", [])
            out(f"  [RECOVERY] 復旧データ: {len(existing_collected)}件")
    else:
        out(f"  [CHECK] {integrity['message']}")

    out("\n[Step 1] 一覧ページ取得...")
    all_detail_links: list[str] = []
    page: int = 1
    while page <= max_pages:
        url: str = f"{BASE_URL}/twitter"
        if page > 1:
            url = f"{BASE_URL}/twitter/page:{page}"
        code, html, _ = _do_fetch(url)
        if code != 200:
            out(f"  ページ{page}: HTTP {code} - 終了")
            break
        links: list[str] = extract_detail_links(html)
        if not links:
            out(f"  ページ{page}: リンクなし - 終了")
            break
        all_detail_links.extend(links)
        out(f"  ページ{page}: {len(links)}件（累計{len(all_detail_links)}件）")
        time.sleep(1.5)  # ★ レート制限回避（1.5秒間隔）
        page += 1
        if len(all_detail_links) >= max_items * 2:
            break

    seen: set[str] = set()
    unique_links: list[str] = []
    for link in all_detail_links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)
    out(f"  ユニーク: {len(unique_links)}件")

    new_links: list[str] = [link for link in unique_links if link not in processed_set]
    new_links = new_links[:max_items]
    out(f"  未処理: {len(new_links)}件（最大{max_items}件処理）")

    # ── 変数初期化 ──
    collected: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    success: int = 0

    # ── Step 2a: knshow.com 収集 ──
    if new_links:
        out(f"\n[Step 2a knshow] {len(new_links)}件を処理...")
        for i, detail_url in enumerate(new_links):
            t1: float = time.time()
            try:
                code, html, _ = _do_fetch_retry(f"{BASE_URL}{detail_url}", referer=f"{BASE_URL}/twitter")
                if code != 200:
                    raise Exception(f"HTTP {code}")
                rd: str | None = extract_rd_link(html)
                if not rd:
                    raise Exception("RDリンクなし")
                x_url: str = resolve_redirect(rd)
                if not is_x_url(x_url):
                    raise Exception(f"X URLではない: {x_url[:60]}")

                # ★ fixupx.com経由でツイート本文を事前取得（応募時のAPI/goto回避用）
                tweet_text = ""
                try:
                    _fx_url = x_url.replace("x.com/", "fixupx.com/").replace("twitter.com/", "fixupx.com/")
                    _fx_resp: httpx.Response = httpx.get(
                        _fx_url,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/125.0.0.0 Safari/537.36"
                            )
                        },
                        follow_redirects=True,
                        timeout=15,
                    )
                    _fx_code = _fx_resp.status_code
                    _fx_html = _fx_resp.text
                    if _fx_code == 200 and _fx_html:
                        import re as _re

                        _m = _re.search(
                            r'<meta\s+property="og:description"\s+content="([^"]*)"',
                            _fx_html,
                        )
                        if _m:
                            tweet_text = _m.group(1)
                except Exception:
                    pass

                # ★ 賞品価値推定
                prize_score: dict = {}
                if tweet_text:
                    try:
                        from kensho.scraping.scorer import score_prize

                        prize_score = score_prize(tweet_text)
                    except Exception:
                        pass

                applied: dict[str, None] = {k: None for k in account_keys}
                deadline, winner_count = extract_deadline_and_winners(html)
                days_remaining: str = ""
                if deadline:
                    try:
                        dl: datetime = datetime.strptime(deadline, "%Y-%m-%d")
                        remaining: int = (dl - datetime.now()).days
                        days_remaining = f"あと{remaining}日" if remaining >= 0 else "期限切れ"
                    except Exception:
                        pass

                elapsed: float = time.time() - t1
                collected.append({
                    "detail_url": detail_url,
                    "rd_url": rd,
                    "x_url": x_url,
                    "source": "knshow",
                    "time": round(elapsed, 2),
                    "deadline": deadline,
                    "winner_count": winner_count,
                    "days_remaining": days_remaining,
                    "prize_score": prize_score,
                    "applied": applied,
                    "tweet_text": tweet_text,
                })
                success += 1

                if (i + 1) % 10 == 0 or i == 0:
                    out(f"  {i + 1}/{len(new_links)}: ✅ {elapsed:.1f}s → {x_url[:70]}...")

            except Exception as e:
                elapsed = time.time() - t1
                errors.append({
                    "detail_url": detail_url,
                    "error": str(e),
                    "time": round(elapsed, 2),
                })
                if (i + 1) % 10 == 0:
                    out(f"  {i + 1}/{len(new_links)}: ❌ {str(e)[:40]}")

            time.sleep(0.3)
    else:
        out("\n✅ knshow.com: 新規なし")

    # ── Step 2b: ken-kaku.com 収集 ──
    out("\n[Step 2b ken-kaku] X懸賞を収集...")
    kenkaku_items: list[dict[str, Any]] = scrape_kenkaku(out, processed_set, account_keys)
    out(f"  ken-kaku: {len(kenkaku_items)}件")
    collected.extend(kenkaku_items)

    # ── Step 2c: kenshou.club 収集 ──
    out("\n[Step 2c kenshou.club] X懸賞を収集...")
    kclub_items: list[dict[str, Any]] = scrape_kenshouclub(out, processed_set, account_keys)
    out(f"  kenshou.club: {len(kclub_items)}件")
    collected.extend(kclub_items)

    # ── Step 2d: cp.meikan.org 収集 ──
    out("\n[Step 2d cp.meikan.org] Xキャンペーンを収集...")
    cpmeikan_items: list[dict[str, Any]] = scrape_cpmeikan(out, processed_set, account_keys)
    out(f"  cp.meikan.org: {len(cpmeikan_items)}件")
    collected.extend(cpmeikan_items)

    # ── Step 2e: ke-ma.net 収集 ──
    out("\n[Step 2e ke-ma.net] X懸賞を収集...")
    kema_items: list[dict[str, Any]] = scrape_kema(out, processed_set, account_keys)
    out(f"  ke-ma.net: {len(kema_items)}件")
    collected.extend(kema_items)

    # ── Step 2f: twscrape 収集 ──
    out("\n[Step 2f twscrape] X直接検索で懸賞を収集...")
    session_path: str | None = None
    for a in cfg.get("accounts", []):
        if a.get("schedule", {}).get("collects", False):
            session_path = str(Path(cfg["general"]["project_dir"]) / a["session"])
            break
    twscrape_items: list[dict[str, Any]] = scrape_twscrape(out, processed_set, account_keys, session_path)
    out(f"  twscrape: {len(twscrape_items)}件")
    collected.extend(twscrape_items)

    # ── Step 2g: chance.com 収集 ──
    out("\n[Step 2g chance.com] X懸賞を収集...")
    chancecom_items: list[dict[str, Any]] = scrape_chancecom(out, processed_set, account_keys)
    out(f"  chance.com: {len(chancecom_items)}件")
    collected.extend(chancecom_items)

    if not collected and not errors:
        out("\n✅ 全ソースで新規なし。終了。")
        existing: dict[str, Any] = load_json(COLLECTED_FILE, {})
        existing["timestamp"] = datetime.now().isoformat()
        existing["total_on_page"] = len(unique_links)
        existing["new_items_processed"] = 0
        safe_save_json(COLLECTED_FILE, existing, "collected.json")
        return (0, 0, len(existing.get("collected", [])))

    out(
        f"\n[Step 3] 結果保存... (knshow {success}件, ken-kaku {len(kenkaku_items)}件, "
        f"kenshou.club {len(kclub_items)}件, cp.meikan {len(cpmeikan_items)}件, "
        f"ke-ma {len(kema_items)}件, twscrape {len(twscrape_items)}件, "
        f"chance.com {len(chancecom_items)}件, "
        f"計{len(collected)}件)"
    )

    existing_collected = load_json(COLLECTED_FILE, {}).get("collected", [])
    existing_map: dict[str, dict[str, Any]] = {item["detail_url"]: item for item in existing_collected}

    for item in collected:
        processed_set.add(item["detail_url"])
        if item["detail_url"] in existing_map:
            item["applied"] = existing_map[item["detail_url"]].get("applied", item["applied"])
    for item in errors:
        processed_set.add(item["detail_url"])

    processed["ids"] = list(processed_set)
    processed["last_updated"] = datetime.now().isoformat()
    safe_save_json(PROCESSED_FILE, processed, "processed.json")

    merged: list[dict[str, Any]] = list(existing_collected)
    existing_detail_urls: set[str] = set(existing_map.keys())
    for item in collected:
        if item["detail_url"] not in existing_detail_urls:
            merged.append(item)

    _now: datetime = datetime.now()
    before: int = len(merged)
    merged = [item for item in merged if not _is_expired(item.get("deadline", ""), _now)]
    purged: int = before - len(merged)
    if purged > 0:
        out(f"  期限切れ除去: {purged}件")

    # ── 賞品価格ランクを収集アイテムに追加 ──
    for item in merged:
        xurl: str = item.get("x_url", "")
        if xurl:
            # 簡易的な金額推定（x_urlからは取れないので0固定、後でapplierがツイート本文から取得）
            item["prize_rank"] = 0
    out(f"  賞品価格ランク: 全{len(merged)}件（実際のランクは応募時にツイート本文から計算）")

    # ── Step 4: 未取得ツイート本文の一括テキスト取得（fixupx.com経由） ──
    text_fetched: int = 0
    text_skipped: int = 0
    text_errors: int = 0
    text_unfetchable: int = 0
    text_candidates: list[dict[str, Any]] = [
        item for item in merged if not item.get("tweet_text", "").strip() and "/status/" in item.get("x_url", "")
    ]
    if text_candidates:
        out(f"\n[Step 4 Tweet Text Fetch] 未取得 {len(text_candidates)}件をCDN→fixupxで取得...")
        for idx, item in enumerate(text_candidates):
            x_url: str = item["x_url"]
            # ★ CDN優先（認証不要・全文取得・軽量） — REST v1.1死の代替
            _tweet_id = _re.search(r"/status/(\d+)", x_url)
            _cdn_text: str = ""
            if _tweet_id:
                try:
                    _cdn_resp = httpx.get(
                        f"https://cdn.syndication.twimg.com/tweet-result?id={_tweet_id.group(1)}&lang=ja&token=a",
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=10,
                    )
                    if _cdn_resp.status_code == 200 and _cdn_resp.text:
                        _cdn_data = _cdn_resp.json()
                        _cdn_text = _cdn_data.get("text", "") or ""
                except Exception:
                    _cdn_text = ""
            if _cdn_text:
                item["tweet_text"] = _cdn_text
                text_fetched += 1
            else:
                # ★ fixupxフォールバック（og:description 168文字打ち切り）
                fx_url: str = x_url.replace("x.com/", "fixupx.com/").replace("twitter.com/", "fixupx.com/")
                try:
                    _fx_resp: httpx.Response = httpx.get(
                        fx_url,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/125.0.0.0 Safari/537.36"
                            )
                        },
                        follow_redirects=True,
                        timeout=15,
                    )
                    if _fx_resp.status_code == 200 and _fx_resp.text:
                        _m = _re.search(
                            r'<meta\s+property="og:description"\s+content="([^"]*)"',
                            _fx_resp.text,
                            _re.IGNORECASE,
                        )
                        if _m:
                            item["tweet_text"] = _m.group(1)
                            text_fetched += 1
                        else:
                            text_skipped += 1  # no og:description meta
                    else:
                        text_errors += 1
                except Exception:
                    text_errors += 1

            if (idx + 1) % 10 == 0:
                out(
                    f"  {idx + 1}/{len(text_candidates)}: 取得{text_fetched} / スキップ{text_skipped} / エラー{text_errors}"
                )

            # ★ 人間の閲覧ペース: CDN成功時は0.5s、フォールバック後は1.5〜2秒
            time.sleep(0.5 if _cdn_text else 1.5)

        out(f"  Tweet Text一括取得完了: 成功{text_fetched} / スキップ{text_skipped} / エラー{text_errors}")
    else:
        out("\n[Step 4 Tweet Text Fetch] 未取得アイテムなし（スキップ）")

    result: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "total_on_page": len(unique_links),
        "new_items_processed": len(new_links),
        "success": success,
        "errors": len(errors),
        "collected": merged,
        "error_details": errors,
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    safe_save_json(COLLECTED_FILE, result, "collected.json")

    elapsed_total: float = time.time() - t0
    out(f"\n{'=' * 50}")
    out(f"完了: {elapsed_total:.1f}秒")
    out(f"  成功: {success}件")
    out(f"  エラー: {len(errors)}件")
    out(f"  処理済み累計: {len(processed_set)}件")

    x_urls: list[str] = [item["x_url"] for item in collected]
    out("\n収集したX URL:")
    for url in x_urls[:10]:
        out(f"  {url}")
    if len(x_urls) > 10:
        out(f"  ...他{len(x_urls) - 10}件")

    return (success, len(errors), len(collected))
