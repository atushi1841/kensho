"""Kensho Collector — knshow.com + ken-kaku.com + kenshou.club + cp.meikan.org からX懸賞URLを収集"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from kensho.core.config import load as load_config
from kensho.scraping.common import (
    is_stale_empty_deadline,
    snowflake_ts_ms,
)
from kensho.scraping.dead_source_sentinel import check_dead_sources
from kensho.scraping.source_health import PRIMARY_SOURCES, SourceHealth, set_active
from kensho.scraping.sources import (
    BASE_URL,
    _fetch_with_retry,
    _is_expired,
    extract_deadline_and_winners,
    extract_detail_links,
    extract_rd_link,
    fetch,
    has_skip_keyword,
    is_x_url,
    load_json,
    resolve_redirect,
    scrape_chancecom,
    scrape_cpmeikan,
    scrape_kema,
    scrape_kenkaku,
    scrape_kensho_everyday,
    scrape_kenshouclub,
    scrape_twscrape,
    scrapling_fetch,
    scrapling_fetch_with_retry,
)
from kensho.utils.backup import safe_save_json, try_recover_collected, verify_collected_integrity
from kensho.utils.url_guard import (
    BLOCK_THRESHOLD,
    GUARD_FILENAME,
    is_blocked,
    load_guard,
    record_failure,
    record_success,
)

# ── deadline 空アイテムの snowflake 年齢パージ（critic v67）──
#   cp.meikan は一覧ページから期限を抽出できないため deadline が空のまま collected.json に
#   滞留する。_is_expired(deadline="") は False を返すため期限切れ除去をすり抜け、収集のたびに
#   再生成されて backfill の成果を毎朝リセットしていた。tweet_id(snowflake)から生成時刻を
#   復元し、_STALE_TWEET_DAYS 超のものを期限切れとして除去する。
#   ★ critic v70: ロジックは kensho/scraping/common.py へ共通化（collector パージと
#     applier 保存層パージ state.save_collected_safe で同一判定を共有）。
#   _snowflake_ts_ms / _is_stale_empty_deadline は後方互換のため再エクスポート。
_TWITTER_EPOCH_MS: int = 1288834974657

# mypy strict 用: 後方互換の再エクスポート（テスト tests/test_collector.py が private 名で import）
_snowflake_ts_ms = snowflake_ts_ms
_is_stale_empty_deadline = is_stale_empty_deadline


def research_allowed(hour: int, cfg: dict[str, Any] | None) -> bool:
    """twscrape(X直接検索=research)の実行可否を現在時刻で判定 (t_9cc18ba0)。

    背景: twscrape はX APIを叩く唯一の収集ソースで、auth_token(auth_session)をXアカウントの
    cookie から使う（collects未指定時は home_internet の atushi16 にフォールバック）。
    apply応募も atushi16 等の同一セッション/同一IPで8:00〜23:00に走るため、収集cronが
    同時刻（例：12:00収集と11:47〜12:56のapply）にtwscrapeのX検索を実行すると、X側から
    「同一セッションが検索と応募を近接実行」と相関されBOT検出フラグが付きやすくなる。

    対策: collection.research_hours（HH形式の整数リスト）でresearch実行を apply 非稼働時刻
    （orchestrator.no_action_window 既定 00:00〜07:00）に限定。デフォルトは ["03"] で、
    深夜の収集cron（03:00）でのみtwscrapeを実行する（それ以外の時刻は skip）。

    cfg 未指定 or research_hours 未設定 → True（従来挙動・後方互換）。
    """
    if not cfg:
        return True
    col = cfg.get("collection") or {}
    research_hours: list[int] | None = col.get("research_hours")
    if not research_hours:
        return True  # 未設定 = 従来挙動（毎時の収集で実行）
    return hour in research_hours


def _normalize_x_url(xu: str) -> str:
    """x_url を正規化して同一ツイートの表記揺れを吸収する。

    - /status/<id> のツイートIDをキーとして抽出（/i/web/status/ やユーザー名表記揺れを吸収）
    - 末尾の #フラグメント / ?クエリ を除去
    - twitter.com を x.com に統一

    dedup のキーに使う。同一ツイートが複数ソースで別表記されても
    重複エントリとして再応募されるのを防ぐ（2026-08-25 修正）。
    """
    u = xu.split("#")[0].split("?")[0].rstrip("/")
    u = u.replace("twitter.com/", "x.com/")
    # ツイートIDで同一視（ユーザー名の有無 / /i/web/status/ 表記を吸収）
    m = re.search(r"/status/(\d+)", u)
    if m:
        return f"x.com/status/{m.group(1)}"
    return u


def _dedup_x_url_merge(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """x_url 単位で一意化（URL表記揺れも正規化して同一視）。

    - 応募済み状態(applied) は union 保持（None以外の値を優先）
    - 長い方の tweet_text を保持
    - 空でない deadline を優先
    - 正規形(/status/ 表記)の x_url を優先保持
    - x_url 無しエントリは detail_url で退避維持
    """
    x_url_index: dict[str, dict[str, Any]] = {}
    for item in items:
        xu: str = item.get("x_url", "")
        if not xu:
            x_url_index.setdefault(f"__no_xurl__{item.get('detail_url', '')}", item)
            continue
        xu_key: str = _normalize_x_url(xu)
        if xu_key not in x_url_index:
            x_url_index[xu_key] = item
        else:
            base = x_url_index[xu_key]
            # 応募済み状態の union（None以外を優先）
            base_applied = base.get("applied") or {}
            new_applied = item.get("applied") or {}
            merged_applied: dict[str, Any] = {}
            for _src in (new_applied, base_applied):
                for _k, _v in _src.items():
                    if _v not in (None, ""):
                        merged_applied[_k] = _v
                    elif _k not in merged_applied:
                        merged_applied[_k] = _v
            base["applied"] = merged_applied
            # 長いほうのtweet_textを保持
            btxt = base.get("tweet_text", "") or ""
            itxt = item.get("tweet_text", "") or ""
            if len(itxt) > len(btxt):
                base["tweet_text"] = itxt
            # deadlineが空なら埋める
            if not base.get("deadline") and item.get("deadline"):
                base["deadline"] = item["deadline"]
            # 正規形(/status/)の x_url を優先保持（applier が確実にパースできる表記）
            if "/i/web/status/" in (base.get("x_url", "")) and "/i/web/status/" not in (item.get("x_url", "")):
                base["x_url"] = item["x_url"]
    # ★ 2026-08-26: 全アイテムにtweet_idをバックフィル（監査の追跡性回復: n/a解消）
    for it in x_url_index.values():
        if not it.get("tweet_id"):
            _m = re.search(r"/status/(\d+)", it.get("x_url", ""))
            if _m:
                it["tweet_id"] = _m.group(1)
    return list(x_url_index.values())


def _merge_applied_from_disk(result_items: list[dict[str, Any]], disk_items: list[dict[str, Any]]) -> int:
    """保存直前マージ: ディスク上のapplied応募日付を収集結果に反映（2026-09-03 v7修正）。

    collectorは全ソース収集に数分かかり、その間にapplierがcollected.jsonのappliedを
    更新（日付書き込み）している可能性がある。この変更を上書きして消さないよう、
    各アイテムのappliedをディスク値とmerged（None以外を優先）する。

    knshow の detail_url は収集ごとに変わるハッシュ形式（/detail/<hash>.html）のため、
    detail_url 単独照合では保存前マージが機能せず applied が消滅する（観測1・4回目再発）。
    → detail_url 照合に失敗した場合は正規化済み x_url で再照合する複合照合に変更。

    戻り値: applied をディスク値で補完・更新したアイテム数
    """
    if not disk_items or not result_items:
        return 0
    _disk_map_detail: dict[str, dict[str, Any]] = {item["detail_url"]: item for item in disk_items}
    # x_url（正規化後）→ ディスクアイテム。同一ツイートが過去の収集でdetail_url違いで
    # 重複している場合は applied（None以外を優先）をunionして最も情報の多い状態を保持。
    _disk_map_xurl: dict[str, dict[str, Any]] = {}
    for _dit in disk_items:
        _dxu: str = _normalize_x_url(_dit.get("x_url", ""))
        if not _dxu:
            continue
        if _dxu not in _disk_map_xurl:
            _disk_map_xurl[_dxu] = _dit
            continue
        _prev = _disk_map_xurl[_dxu]
        _pa: dict[str, Any] = _prev.get("applied") or {}
        _da: dict[str, Any] = _dit.get("applied") or {}
        _ua: dict[str, Any] = dict(_pa)
        for _k, _v in _da.items():
            if _v not in (None, ""):
                _ua[_k] = _v
            elif _k not in _ua:
                _ua[_k] = _v
        _prev["applied"] = _ua
    _matched: int = 0
    for item in result_items:
        _du: str = item.get("detail_url", "")
        _disk_item: dict[str, Any] | None = _disk_map_detail.get(_du)
        if _disk_item is None:
            # detail_url が変わった（knshow ハッシュ形式）→ x_url で再照合
            _xu_key: str = _normalize_x_url(item.get("x_url", ""))
            if _xu_key:
                _disk_item = _disk_map_xurl.get(_xu_key)
        if _disk_item is None:
            continue
        _disk_applied: dict[str, Any] = _disk_item.get("applied") or {}
        _item_applied: dict[str, Any] = item.get("applied") or {}
        _merged: dict[str, Any] = dict(_disk_applied)
        for _k, _v in _item_applied.items():
            if _v is None:
                _merged.setdefault(_k, None)
            else:
                _merged[_k] = _v
        item["applied"] = _merged
        _matched += 1
    return _matched


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

    # ★ t_442337b4 提案2/3: 収集源ヘルスモニタ — ネットワーク層timeout率を日次trackし、
    #   閾値超過ソースを自動skip（キャッシュ=既収集分を維持）。全主要源timeout時は前日キャッシュ提供。
    _hcfg: dict[str, Any] = cfg.get("collection", {})
    health: SourceHealth = SourceHealth(
        DATA_DIR,
        max_consecutive_failures=int(_hcfg.get("health_max_consecutive_failures", 4)),
        daily_failure_rate=float(_hcfg.get("health_daily_failure_rate", 0.5)),
        min_attempts=int(_hcfg.get("health_min_attempts", 6)),
    )
    health.begin_run()
    set_active(health)

    def guarded_source(name: str, fn: Callable[..., list[dict[str, Any]]], *args: Any) -> list[dict[str, Any]]:
        """異常ソースはネットワーク呼び出しを回避して自動スキップ（既収集分=キャッシュを維持）。"""
        if health.is_unhealthy(name):
            out(f"  [HEALTH] {name}: 異常 {health.status_line(name)} → 自動skip・キャッシュ（既収集分）維持")
            health.record_skip(name)
            return []
        return fn(*args)

    out(f"[Kensho Collection] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out(f"  最大件数: {max_items}, アカウント: {account_keys}")

    # ★ t_d2242716: research(twscrape)ゲートの基準を「収集開始時刻(cron hour)」に固定。
    #   収集が遅れて Step 2f 到達が 03:00 を跨いでも、cron開始時刻に基づきresearchを実行する
    #   （壁時計 datetime.now().hour だと実行機会を取り逃すため）。
    _collect_start_hour: int = datetime.now().hour

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
    consecutive_zero: int = 0  # 連続で「全リンク処理済み」のページ数（knshow早期終了用）
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
        page_new: int = sum(1 for link in links if link not in processed_set)
        all_detail_links.extend(links)
        out(f"  ページ{page}: 走査{len(links)}件 (累計{len(all_detail_links)}件, 新規{page_new}件 - 収集件数ではない)")
        # ★ knshowは最新順ソート。連続2ページで新規ゼロ＝以降も処理済みの古い案件のみ → 打ち切り
        #   収集を毎回全30ページスキャンして無駄な時間を使うのを防ぐ（2026-08-20最適化）
        if page_new == 0:
            consecutive_zero += 1
            if consecutive_zero >= 2:
                out(f"  ページ{page}: 連続{consecutive_zero}ページ新規ゼロ → 早期終了")
                break
        else:
            consecutive_zero = 0
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
                        _m = re.search(
                            r'<meta\s+property="og:description"\s+content="([^"]*)"',
                            _fx_html,
                        )
                        if _m:
                            tweet_text = _m.group(1)
                except Exception:
                    pass

                applied: dict[str, None] = {k: None for k in account_keys}
                deadline, winner_count = extract_deadline_and_winners(html)
                # ★ 賞品価値推定（当選人数・締切を重みに反映）
                prize_score: dict = {}
                if tweet_text:
                    try:
                        from kensho.scraping.scorer import score_prize

                        prize_score = score_prize(
                            tweet_text,
                            winner_count=winner_count or 0,
                            deadline=deadline or "",
                        )
                    except Exception:
                        pass
                days_remaining: str = ""
                if deadline:
                    try:
                        dl: datetime = datetime.strptime(deadline, "%Y-%m-%d")
                        remaining: int = (dl - datetime.now()).days
                        days_remaining = f"あと{remaining}日" if remaining >= 0 else "期限切れ"
                    except Exception:
                        pass

                elapsed: float = time.time() - t1
                _tid_m = re.search(r"/status/(\d+)", x_url)
                collected.append({
                    "detail_url": detail_url,
                    "rd_url": rd,
                    "x_url": x_url,
                    # ★ 2026-08-26: 監査追跡用にtweet_idを保存
                    "tweet_id": _tid_m.group(1) if _tid_m else "",
                    "source": "knshow",
                    "time": round(elapsed, 2),
                    "deadline": deadline,
                    "winner_count": winner_count,
                    "days_remaining": days_remaining,
                    "prize_score": prize_score,
                    "applied": applied,
                    "tweet_text": tweet_text,
                    # ★ 2026-08-26: 引用RT・コメント応募のフラグ（applierでスキップする）
                    "keyword_flag": has_skip_keyword(tweet_text),
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
    kenkaku_items: list[dict[str, Any]] = guarded_source("ken-kaku", scrape_kenkaku, out, processed_set, account_keys)
    out(f"  ken-kaku: {len(kenkaku_items)}件")
    collected.extend(kenkaku_items)

    # ── Step 2c: kenshou.club 収集 ──
    out("\n[Step 2c kenshou.club] X懸賞を収集...")
    kclub_items: list[dict[str, Any]] = guarded_source(
        "kenshou.club", scrape_kenshouclub, out, processed_set, account_keys
    )
    out(f"  kenshou.club: {len(kclub_items)}件")
    collected.extend(kclub_items)

    # ── Step 2d: cp.meikan.org 収集 ──
    out("\n[Step 2d cp.meikan.org] Xキャンペーンを収集...")
    cpmeikan_items: list[dict[str, Any]] = guarded_source(
        "cp.meikan", scrape_cpmeikan, out, processed_set, account_keys
    )
    out(f"  cp.meikan.org: {len(cpmeikan_items)}件")
    collected.extend(cpmeikan_items)

    # ── Step 2e: ke-ma.net 収集 ──
    out("\n[Step 2e ke-ma.net] X懸賞を収集...")
    kema_items: list[dict[str, Any]] = guarded_source("ke-ma", scrape_kema, out, processed_set, account_keys)
    out(f"  ke-ma.net: {len(kema_items)}件")
    collected.extend(kema_items)

    # ── Step 2f: twscrape 収集 ──
    out("\n[Step 2f twscrape] X直接検索で懸賞を収集...")
    # ★ t_9cc18ba0: research(セッション使用のX検索)をapply時刻と分離 — 同一セッションで
    #   検索と応募を近接実行するとXのBOT相関検出が付きやすいため、apply非稼働時刻に限定。
    #   t_d2242716: 判定基準を壁時計(datetime.now().hour)ではなく収集開始時刻 _collect_start_hour
    #   （cron発火時刻）に変更。収集遅延で Step 2f 到達が数時間を跨いでも実行機会を逃さない。
    _research_ok: bool = research_allowed(_collect_start_hour, cfg)
    twscrape_items: list[dict[str, Any]] = []
    if not _research_ok:
        _rh = (cfg or {}).get("collection", {}).get("research_hours")
        out(
            f"  [RESEARCH分離] 収集開始時刻 {_collect_start_hour:02d}:00 は research_hours={_rh} "
            "実行対象外 → X検索(twscrape)をスキップ（apply同時刻のセッション相関防止）"
        )
        twscrape_items = []
    else:
        session_path: str | None = None
        for a in cfg.get("accounts", []):
            if a.get("schedule", {}).get("collects", False):
                session_path = str(Path(cfg["general"]["project_dir"]) / a["session"])
                break
        if not session_path:
            # collects指定が無い場合でもX検索を回せるよう、自宅/最安全垢のセッションを使う（2026-08-20修正）
            # X直接検索は読み取りのみ・低リスク。BANへの影響は応募より遥かに小さい。
            for a in cfg.get("accounts", []):
                if a["key"] == "atushi16":  # home_internet正規垢(凍結リスク最低)を優先
                    session_path = str(Path(cfg["general"]["project_dir"]) / a["session"])
                    break
        twscrape_items = scrape_twscrape(out, processed_set, account_keys, session_path)
    out(f"  twscrape: {len(twscrape_items)}件")
    collected.extend(twscrape_items)

    # ── Step 2g: chance.com 収集 ──
    out("\n[Step 2g chance.com] X懸賞を収集...")
    chancecom_items: list[dict[str, Any]] = scrape_chancecom(out, processed_set, account_keys)
    out(f"  chance.com: {len(chancecom_items)}件")
    collected.extend(chancecom_items)

    # ── Step 2h: kensho-everyday.com 収集（X懸賞カテゴリRSS）──
    out("\n[Step 2h kensho-everyday.com] X懸賞RSSを収集...")
    kevery_items: list[dict[str, Any]] = scrape_kensho_everyday(out, processed_set, account_keys)
    out(f"  kensho-everyday.com: {len(kevery_items)}件")
    collected.extend(kevery_items)

    # ★ t_442337b4 提案3: 全主要ソース（KENKAKU/KCLUB/CPMK/KEMA）がこのrunで1つも応答成功
    #   → 前日データをキャッシュ(collected.json累積)から提供継続 + アラート。fail-open。
    if health.all_primary_idle():
        _unh: list[str] = health.unhealthy_sources()
        out("\n[FALLBACK] 全主要ソースがこの収集runで応答失敗（全timeout/全異常skip）→ 前日データをキャッシュから提供")
        out(f"          主要源状態: { {s: health.status_line(s) for s in PRIMARY_SOURCES} }")
        try:
            from kensho.core.notifier import notify_warning

            notify_warning(
                "収集フォールバック（全主要源timeout）",
                "KENKAKU/KCLUB/KEMA/CPMK 全主要源が応答失敗。前日キャッシュ(collected.json)から提供継続。"
                f"unhealthy={_unh}",
                log_path="",
                cfg=cfg,
            )
        except Exception as _fe:  # noqa: BLE001 — fail-open
            out(f"  [WARN] フォールバック通知失敗（fail-open）: {_fe}")
    elif health.any_primary_failed():
        _failed: list[str] = [s for s in PRIMARY_SOURCES if health.run_failures.get(s, 0) > 0]
        out(f"  [HEALTH] 部分劣化（主要源timeout）: {_failed}")

    if not collected and not errors:
        out("\n✅ 全ソースで新規なし。終了。")
        existing: dict[str, Any] = load_json(COLLECTED_FILE, {})
        existing["timestamp"] = datetime.now().isoformat()
        existing["total_on_page"] = len(unique_links)
        existing["new_items_processed"] = 0
        existing["new_items_by_source"] = {}
        safe_save_json(COLLECTED_FILE, existing, "collected.json")
        health.save()
        set_active(None)
        return (0, 0, len(existing.get("collected", [])))

    out(
        f"\n[Step 3] 結果保存... (knshow {success}件, ken-kaku {len(kenkaku_items)}件, "
        f"kenshou.club {len(kclub_items)}件, cp.meikan {len(cpmeikan_items)}件, "
        f"ke-ma {len(kema_items)}件, twscrape {len(twscrape_items)}件, "
        f"chance.com {len(chancecom_items)}件, kensho-everyday {len(kevery_items)}件, "
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

    # ── マージ: 既存 + 新規を x_url 単位で一意化 ──
    # ★ 同一Xツイートが収集ソース(knshow/kenshouclub等)ごとに別エントリとして重複登録され、
    #   applierがdetail_url単位でしか応募済みを記録しないため、重複エントリが何度も再応募される
    #   バグを防ぐため、マージ時に x_url で統合する（応募済み状態(applied)は union 保持）。
    #   2026-08-20対応: 既存collectedの重複エントリも同時に解消。
    #   2026-08-25対応: URL表記揺れ(/i/web/status/ 等)も正規化して同一視（_dedup_x_url_merge）。
    merged: list[dict[str, Any]] = _dedup_x_url_merge(list(existing_collected) + collected)

    _now: datetime = datetime.now()
    before: int = len(merged)
    # _is_expired: deadline 日付ベースの除去。_is_stale_empty_deadline: deadline 空を
    # snowflake(tweet_id) 年齢で除去（critic v67、cp.meikan 対策）。
    merged = [
        item
        for item in merged
        if not (_is_expired(item.get("deadline", ""), _now) or _is_stale_empty_deadline(item, _now))
    ]
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
    text_candidates: list[dict[str, Any]] = [
        item for item in merged if not item.get("tweet_text", "").strip() and "/status/" in item.get("x_url", "")
    ]
    if text_candidates:
        out(f"\n[Step 4 Tweet Text Fetch] 未取得 {len(text_candidates)}件をCDN→fixupxで取得...")
        # ★ critic v71 提案②: fixupx 失敗ガード（同一ツイートID失敗3回でブラックリスト、
        #   ブロック入りURLは以後の収集でスキップ、成功でカウントリセット）
        _guard_path: Path = DATA_DIR / GUARD_FILENAME
        _guard = load_guard(_guard_path)
        _guard_hits = 0
        for idx, item in enumerate(text_candidates):
            x_url: str = item["x_url"]
            if is_blocked(_guard, x_url):
                _guard_hits += 1
                continue
            # ★ CDN優先（認証不要・全文取得・軽量） — REST v1.1死の代替
            _tweet_id = re.search(r"/status/(\d+)", x_url)
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
                record_success(_guard, x_url, _guard_path)  # ★ v71: 成功で失敗カウント消去
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
                        _m = re.search(
                            r'<meta\s+property="og:description"\s+content="([^"]*)"',
                            _fx_resp.text,
                            re.IGNORECASE,
                        )
                        if _m:
                            item["tweet_text"] = _m.group(1)
                            text_fetched += 1
                            record_success(_guard, x_url, _guard_path)  # ★ v71
                        else:
                            text_skipped += 1  # no og:description meta
                            # 200だがog:descriptionなし（delete済みページはこの形）も失敗扱い
                            _fc = record_failure(_guard, x_url, "no_og_description", _guard_path)
                            if _fc == BLOCK_THRESHOLD:
                                out(f"    🚫 fixupx失敗{_fc}回 → ガードブロック入り: {x_url[:70]}")
                    else:
                        out(f"    [ERROR] fixupx: {x_url} (HTTP {_fx_resp.status_code})")
                        text_errors += 1
                        _fc = record_failure(_guard, x_url, f"HTTP {_fx_resp.status_code}", _guard_path)
                        if _fc == BLOCK_THRESHOLD:
                            out(f"    🚫 fixupx失敗{_fc}回 → ガードブロック入り: {x_url[:70]}")
                except Exception:
                    out(f"    [ERROR] fixupx例外: {x_url}")
                    text_errors += 1
                    _fc = record_failure(_guard, x_url, "exception", _guard_path)
                    if _fc == BLOCK_THRESHOLD:
                        out(f"    🚫 fixupx失敗{_fc}回 → ガードブロック入り: {x_url[:70]}")

            if (idx + 1) % 10 == 0:
                out(
                    f"  {idx + 1}/{len(text_candidates)}: 取得{text_fetched} / スキップ{text_skipped} / エラー{text_errors}"  # noqa: E501
                )

            # ★ 人間の閲覧ペース: CDN成功時は0.5s、フォールバック後は1.5〜2秒
            time.sleep(0.5 if _cdn_text else 1.5)

        out(
            f"  Tweet Text一括取得完了: 成功{text_fetched} / スキップ{text_skipped} / エラー{text_errors}"
            + (f" / ガードスキップ{_guard_hits}件" if _guard_hits else "")
        )
    else:
        out("\n[Step 4 Tweet Text Fetch] 未取得アイテムなし（スキップ）")

    # ★ 提案39: Step 4終了後、tweet_textベースでkeyword_flagを再評価（cpmeikan/kenkakuのHTMLコンテキスト過検出是正）
    rechecked: int = 0
    cleared: int = 0
    for item in merged:
        if item.get("keyword_flag") and item.get("tweet_text"):
            rechecked += 1
            if not has_skip_keyword(item["tweet_text"]):
                item["keyword_flag"] = False
                cleared += 1
    if rechecked > 0:
        out(
            f"  [keyword_flag再評価] {rechecked}件中{cleared}件の過検出を解除"
            f"（残り{rechecked - cleared}件が正当な引用/コメント）"
        )

    # ★ 2026-08-28: LLMによる「フォロー+RTだけで応募完了か」判定（simple_rt_ok）
    #   従来のキーワード・ブラックリストは過検出/見逃しのいたちごっこ（例: 「結果をチェック」削除→
    #   外部X連携案件の見逃し）。LLM（DeepSeek v4-flash）で追加操作（外部サイト/動画認証/入力/
    #   診断/写真投稿/シェア等）が必要な案件を捕捉する。実測7/7正解。
    #   fail-open: LLM失敗・APIキーなし・未設定は従来挙動（応募継続）のまま。
    _llm_classify: bool = (cfg or {}).get("collection", {}).get("llm_classify", False)
    if _llm_classify:
        try:
            from kensho.scraping.simple_rt_classifier import classify_collected_items

            _llm_model: str = (cfg or {}).get("collection", {}).get("llm_model", "deepseek-v4-flash")
            _llm_batch: int = int((cfg or {}).get("collection", {}).get("llm_batch_size", 8))
            _c_n, _f_n, _u_n = classify_collected_items(merged, model=_llm_model, batch_size=_llm_batch, log=log)
            if _c_n:
                out(f"  [simple_rt LLM判定] {_c_n}件（FLAG={_f_n} / OK={_c_n - _f_n - _u_n} / UNKNOWN={_u_n}）")
        except Exception as e:  # noqa: BLE001 — fail-open
            out(f"  [simple_rt LLM判定] 失敗（fail-open・応募継続）: {e}")

    # ★ 2026-08-27 スループット改善②: 必須ワードなしツイートを収集から除外
    #    applier側（①）でも収集時tweet_textで早期スキップするが、収集データ自体を
    #    絞ることで保存・可視化・処理対象を軽くする。tweet_textが空の項目は判定不能のため保持。
    _drop_missing = (cfg or {}).get("collection_filter", {}).get("drop_without_must_word", False)
    if _drop_missing:
        _req_any = (cfg or {}).get("required_words", {}).get("require_any", [])
        _req_all = (cfg or {}).get("required_words", {}).get("require_all", [])
        _before_n = len(merged)
        _kept: list[dict[str, Any]] = []
        _dropped_n = 0
        for item in merged:
            _txt = item.get("tweet_text", "") or ""
            if not _txt:
                _kept.append(item)  # 判定不能 → 保持（後で本文取得）
                continue
            if _req_any and not any(w in _txt for w in _req_any):
                _dropped_n += 1
                continue
            if _req_all and not all(w in _txt for w in _req_all):
                _dropped_n += 1
                continue
            _kept.append(item)
        merged = _kept
        if _dropped_n:
            out(f"  [収集フィルタ②] 必須ワードなしを除外: {_dropped_n}件（{_before_n}→{len(merged)}件）")

    result: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "total_on_page": len(unique_links),
        "new_items_processed": len(collected),  # 全ソース合計の新規取得数（knshowのみ→全ソースに修正）
        "success": success,
        "errors": len(errors),
        "collected": merged,
        "error_details": errors,
        "elapsed_seconds": round(time.time() - t0, 1),
        "new_items_by_source": {  # 診断用: ソース別新規取得数
            "knshow": success,
            "ken-kaku": len(kenkaku_items),
            "kenshou.club": len(kclub_items),
            "cp.meikan": len(cpmeikan_items),
            "ke-ma": len(kema_items),
            "twscrape": len(twscrape_items),
            "chance.com": len(chancecom_items),
            "kensho-everyday": len(kevery_items),
        },
    }
    # ★ 2026-09-02 修正: 保存直前にディスクから再読込し、applierが書き込んだ応募日付をマージ。
    #    collectorは全ソース収集に数分かかり、その間にapplierがcollected.jsonのappliedを更新
    #    (日付書き込み)している可能性がある。この変更を上書きして消さないよう、
    #    各アイテムのappliedをディスク値とmerged（None以外を優先）する。
    # ★ 2026-09-03 v7修正: detail_url 単独照合→x_url複合照合に変更（_merge_applied_from_disk参照）。
    try:
        _disk_data: dict[str, Any] = load_json(COLLECTED_FILE, {})
        _disk_items: list[dict[str, Any]] = _disk_data.get("collected", [])
        _matched: int = _merge_applied_from_disk(result["collected"], _disk_items)
        if _matched:
            out(f"  [保存前マージ] {_matched}件のappliedをディスク値で補完")
    except Exception as _me:
        out(f"  [WARN] 保存前マージ失敗: {_me}")
    safe_save_json(COLLECTED_FILE, result, "collected.json")

    # ★ critic v71 提案①: デッドソースセンチネル — ソース別連続0件/fixupx連続エラーを
    #   検知してログに[DEAD-SOURCE]明示 + kanbanタスク自動投入（twscrape 50hサイレント死再発防止）。
    #   fail-open: 検知機構の失敗で収集本体を絶対に止めない。
    try:
        check_dead_sources(
            by_source=result["new_items_by_source"],
            fixupx_errors=text_errors,
            fixupx_fetched=text_fetched,
            data_dir=DATA_DIR,
            out=out,
        )
    except Exception as _dse:  # noqa: BLE001
        out(f"  [WARN] dead-source sentinel 失敗（fail-open）: {_dse}")

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

    # ★ t_442337b4 提案2: ヘルスモニタ永続化 + アクティブ解除。fail-open。
    _unh_list: list[str] = health.unhealthy_sources()
    if _unh_list:
        out(f"  [HEALTH] 異常ソース: {_unh_list}（次回収集で自動skip・キャッシュ維持）")
    health.save()
    set_active(None)

    return (success, len(errors), len(collected))
