"""Kensho Collector — knshow.com + ken-kaku.com からX懸賞URLを収集"""

from __future__ import annotations

import httpx, re, json, time, sys
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import load as load_config
from utils.backup import safe_save_json, verify_collected_integrity, try_recover_collected

BASE_URL: str = 'https://www.knshow.com'
KENKAKU_BASE: str = 'https://www.ken-kaku.com/cgi-bin/present/'

# ── User-Agent ローテーション（BOT検出回避）──
_USER_AGENTS: list[str] = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
]
import random as _random
_UA_INDEX: int = _random.randint(0, len(_USER_AGENTS) - 1)

HEADERS: dict[str, str] = {
    'User-Agent': _USER_AGENTS[_UA_INDEX],
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
}


# ── 指数バックオフリトライ ──
def _fetch_with_retry(url: str, referer: str | None = None, max_retries: int = 3, timeout: int = 15) -> tuple[int, str, str]:
    """
    HTTP GET with exponential backoff.
    HTTP 5xx / タイムアウト / ネットワークエラー時にリトライ。
    """
    last_err: str | None = None
    for attempt in range(max_retries):
        try:
            code, html, final_url = fetch(url, referer=referer, timeout=timeout)
            if code < 500:
                return code, html, final_url
            last_err = f"HTTP {code}"
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_err = str(e)
        except Exception as e:
            last_err = str(e)
            break
        if attempt < max_retries - 1:
            delay: float = (2 ** attempt) + _random.uniform(0, 1)
            time.sleep(delay)
    code, html, final_url = 0, '', ''
    try:
        code, html, final_url = fetch(url, referer=referer, timeout=timeout)
    except Exception:
        pass
    return code, html, final_url


def load_json(path: Path, default: Any = None) -> Any:
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return default if default is not None else {}


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch(url: str, referer: str | None = None, timeout: int = 15) -> tuple[int, str, str]:
    h: dict[str, str] = dict(HEADERS)
    if referer:
        h['Referer'] = referer
    with httpx.Client(follow_redirects=False, timeout=timeout) as c:
        r = c.get(url, headers=h)
        return r.status_code, r.text, str(r.url)


def extract_detail_links(html: str) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for m in re.finditer(r'href="(/detail/[^"]+\.html)"', html):
        url: str = m.group(1)
        if url not in seen:
            seen.add(url)
            links.append(url)
    return links


def extract_rd_link(html: str) -> str | None:
    m = re.search(r'href="(/rd/[^"]+)"', html)
    return m.group(1) if m else None


def resolve_redirect(rd_path: str) -> str:
    h: dict[str, str] = dict(HEADERS)
    h['Referer'] = f'{BASE_URL}/twitter'
    with httpx.Client(follow_redirects=True, timeout=15) as c:
        r = c.get(f'{BASE_URL}{rd_path}', headers=h)
        url: str = str(r.url)
        # knshow が tracking hash (#508 など) を付与するので除去
        if '#' in url:
            url = url.split('#')[0]
        return url


def is_x_url(url: str) -> bool:
    """XのツイートURLか判定（アカウントページは除外）"""
    url_lower: str = url.lower()
    if 'x.com' not in url_lower and 'twitter.com' not in url_lower:
        return False
    # /status/ がないものはツイートではなくアカウントページ
    if '/status/' not in url_lower:
        return False
    return True


def extract_deadline_and_winners(html: str) -> tuple[str, int]:
    """詳細ページHTMLから締切日と当選人数を抽出（v3.3: title優先 + サイドバー除外）"""
    deadline: str = ''
    winner_count: int = 0

    # 1) <title> タグから抽出（最も信頼性が高い）
    # 例: "【毎日・その場で当たる】クーリッシュバニラ1個 ... 【〆切07月01日】ロッテ"
    m_title = re.search(r'[【\[]\s*[締〆]切\s*(\d{1,2})月(\d{1,2})日', html.split('</title>')[0])
    if m_title:
        deadline = f'2026-{int(m_title.group(1)):02d}-{int(m_title.group(2)):02d}'
    else:
        # 2) 「応募締切日」の専用spanタグ
        m = re.search(r'応募締切日[：:]?\s*<strong>\s*<span\s+class="expiredatetime-display"\s+data-expiredatetime=\'(\d{4}-\d{1,2}-\d{1,2})\'', html)
        if m:
            deadline = m.group(1)
        else:
            # 3) 「締切:」テキスト（サイドバーの関連案件を避けるため最初の出現のみ）
            m = re.search(r'[締〆]切[：:]\s*(\d{1,2})月(\d{1,2})日\s*(?:\d{1,2}:\d{2})?', html[:3000])
            if m:
                deadline = f'2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}'

    # 当選人数: <strong class="tousenST"> 10,000</strong>名様
    m_w = re.search(r'<strong\s+class="tousenST">\s*([\d,]+)\s*</strong>\s*名様', html)
    if m_w:
        try:
            winner_count = int(m_w.group(1).replace(',', ''))
        except ValueError:
            winner_count = 0
    else:
        # フォールバック: titleタグから（例: "10000名様にプレゼント"）
        m_w2 = re.search(r'(\d[\d,]*)\s*名様', html.split('</title>')[0])
        if m_w2:
            try:
                winner_count = int(m_w2.group(1).replace(',', ''))
            except ValueError:
                winner_count = 0

    return deadline, winner_count


# ── 期限切れアイテムの自動パージ ──
_EXPIRY_DAYS: int = 30


def _is_expired(deadline_str: str, now: datetime | None = None) -> bool:
    """締切日が _EXPIRY_DAYS 以上経過していれば True"""
    if not deadline_str:
        return False
    if now is None:
        now = datetime.now()
    try:
        dl: datetime = datetime.strptime(deadline_str, '%Y-%m-%d')
        return (now - dl).days > _EXPIRY_DAYS
    except (ValueError, TypeError):
        return False


# ── 第2収集源: ken-kaku.com（懸賞館）──
_KENKAKU_PAGE_IDS: list[str] = [
    '104510000', '1045100010', '1045100020', '1045100030',
    '1045100040', '1045100050', '1045100060',
]


def scrape_kenkaku(out: Any, processed_set: set[str],
                   account_keys: list[str]) -> list[dict[str, Any]]:
    """ken-kaku.com のX/Twitter懸賞セクションからX URLを直接取得。
    戻り値: collected.json 互換のアイテムリスト。
    """
    headers_jp: dict[str, str] = dict(HEADERS)
    headers_jp['Accept-Language'] = 'ja,en-US;q=0.9,en;q=0.8'
    items: list[dict[str, Any]] = []
    seen_x_urls: set[str] = set()

    for pid in _KENKAKU_PAGE_IDS:
        url: str = f'{KENKAKU_BASE}present.cgi?id={pid}'
        try:
            with httpx.Client(follow_redirects=True, timeout=15) as c:
                r = c.get(url, headers=headers_jp)
            if r.status_code != 200:
                out(f'  [KENKAKU] ページ{pid}: HTTP {r.status_code} - スキップ')
                continue

            html: str = r.text
            # X URL を直接抽出
            for m in re.finditer(
                r'href=\"(https?://x\.com/[a-zA-Z0-9_]+/status/[0-9]+)\"', html
            ):
                x_url: str = m.group(1)
                if x_url in seen_x_urls:
                    continue
                seen_x_urls.add(x_url)
                if x_url in processed_set:
                    continue

                # 仮のdetail_url（present.cgiのURLを使用）
                detail_url: str = f'/kenkaku/present.cgi?id={pid}/{len(items)}'

                # 締切日をtimeタグから取得
                deadline: str = ''
                context_start: int = max(0, m.start() - 600)
                context: str = html[context_start:m.end()]
                dm = re.search(
                    r'time\s+datetime=\"(\d{4}-\d{1,2}-\d{1,2})\"', context
                )
                if dm:
                    deadline = dm.group(1)

                applied: dict[str, None] = {k: None for k in account_keys}
                items.append({
                    'detail_url': detail_url,
                    'x_url': x_url,
                    'source': 'ken-kaku',
                    'time': 0.0,
                    'deadline': deadline,
                    'winner_count': 0,
                    'days_remaining': '',
                    'applied': applied,
                })
                out(f'    ✅ {x_url[:65]}...')
            time.sleep(0.3)  # 優しめの間隔
        except Exception as e:
            out(f'  [KENKAKU] ページ{pid}: ERROR {type(e).__name__}: {e}')

    out(f'  [KENKAKU] 計{len(items)}件取得')
    return items


def collect(cfg: dict[str, Any] | None = None, log: Any = None,
            max_pages: int = 99) -> tuple[int, int, int]:
    """
    収集を実行。
    cfg: config.yaml の内容（Noneなら自動読込）
    log: LogWriter インスタンス（あれば記録）
    max_pages: 取得する最大ページ数（デフォルト99=全ページ）
    戻り値: (success_count, error_count, total_collected_count)
    """
    if cfg is None:
        cfg = load_config()

    account_keys: list[str] = [a['key'] for a in cfg.get('accounts', [])]

    col_cfg: dict[str, Any] = cfg.get('collection', {})
    max_items: int = col_cfg.get('max_items', 200)

    DATA_DIR: Path = Path(cfg['general']['project_dir']) / 'data'
    PROCESSED_FILE: Path = DATA_DIR / 'processed.json'
    COLLECTED_FILE: Path = DATA_DIR / 'collected.json'

    def out(msg: str) -> None:
        if log:
            log.write(msg)
        else:
            print(msg, flush=True)

    out(f"[Kensho Collection] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out(f"  最大件数: {max_items}, アカウント: {account_keys}")

    t0: float = time.time()

    processed: dict[str, Any] = load_json(PROCESSED_FILE, {})
    processed_set: set[str] = set(processed.get('ids', []))
    out(f"  既処理: {len(processed_set)}件")

    integrity: dict[str, Any] = verify_collected_integrity(COLLECTED_FILE, PROCESSED_FILE)
    if not integrity['ok']:
        out(f'  [WARN] {integrity["message"]}')
        recovered: bool = try_recover_collected(PROCESSED_FILE, COLLECTED_FILE, account_keys)
        if recovered and COLLECTED_FILE.exists() and COLLECTED_FILE.stat().st_size > 500:
            existing_collected: list[dict[str, Any]] = load_json(COLLECTED_FILE, {}).get('collected', [])
            out(f'  [RECOVERY] 復旧データ: {len(existing_collected)}件')
    else:
        out(f'  [CHECK] {integrity["message"]}')

    out("\n[Step 1] 一覧ページ取得...")
    all_detail_links: list[str] = []
    page: int = 1
    while page <= max_pages:
        url: str = f'{BASE_URL}/twitter'
        if page > 1:
            url = f'{BASE_URL}/twitter/page:{page}'
        code, html, _ = fetch(url)
        if code != 200:
            out(f"  ページ{page}: HTTP {code} - 終了")
            break
        links: list[str] = extract_detail_links(html)
        if not links:
            out(f"  ページ{page}: リンクなし - 終了")
            break
        all_detail_links.extend(links)
        out(f"  ページ{page}: {len(links)}件（累計{len(all_detail_links)}件）")
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

    new_links: list[str] = [l for l in unique_links if l not in processed_set]
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
                code, html, _ = _fetch_with_retry(f'{BASE_URL}{detail_url}', referer=f'{BASE_URL}/twitter')
                if code != 200:
                    raise Exception(f"HTTP {code}")
                rd: str | None = extract_rd_link(html)
                if not rd:
                    raise Exception("RDリンクなし")
                x_url: str = resolve_redirect(rd)
                if not is_x_url(x_url):
                    raise Exception(f"X URLではない: {x_url[:60]}")

                applied: dict[str, None] = {k: None for k in account_keys}
                deadline, winner_count = extract_deadline_and_winners(html)
                days_remaining: str = ''
                if deadline:
                    try:
                        dl: datetime = datetime.strptime(deadline, '%Y-%m-%d')
                        remaining: int = (dl - datetime.now()).days
                        days_remaining = f'あと{remaining}日' if remaining >= 0 else '期限切れ'
                    except Exception:
                        pass

                elapsed: float = time.time() - t1
                collected.append({
                    'detail_url': detail_url,
                    'rd_url': rd,
                    'x_url': x_url,
                    'time': round(elapsed, 2),
                    'deadline': deadline,
                    'winner_count': winner_count,
                    'days_remaining': days_remaining,
                    'applied': applied,
                })
                success += 1

                if (i + 1) % 10 == 0 or i == 0:
                    out(f"  {i+1}/{len(new_links)}: ✅ {elapsed:.1f}s → {x_url[:70]}...")

            except Exception as e:
                elapsed = time.time() - t1
                errors.append({
                    'detail_url': detail_url,
                    'error': str(e),
                    'time': round(elapsed, 2),
                })
                if (i + 1) % 10 == 0:
                    out(f"  {i+1}/{len(new_links)}: ❌ {str(e)[:40]}")

            time.sleep(0.3)
    else:
        out("\n✅ knshow.com: 新規なし")

    # ── Step 2b: ken-kaku.com 収集 ──
    out("\n[Step 2b ken-kaku] X懸賞を収集...")
    kenkaku_items: list[dict[str, Any]] = scrape_kenkaku(out, processed_set, account_keys)
    out(f"  ken-kaku: {len(kenkaku_items)}件")
    collected.extend(kenkaku_items)

    if not collected and not errors:
        out("\n✅ 全ソースで新規なし。終了。")
        existing: dict[str, Any] = load_json(COLLECTED_FILE, {})
        existing['timestamp'] = datetime.now().isoformat()
        existing['total_on_page'] = len(unique_links)
        existing['new_items_processed'] = 0
        safe_save_json(COLLECTED_FILE, existing, 'collected.json')
        return (0, 0, len(existing.get('collected', [])))

    out(f"\n[Step 3] 結果保存... (knshow {success}件, ken-kaku {len(kenkaku_items)}件, 計{len(collected)}件)")

    existing_collected = load_json(COLLECTED_FILE, {}).get('collected', [])
    existing_map: dict[str, dict[str, Any]] = {item['detail_url']: item for item in existing_collected}

    for item in collected:
        processed_set.add(item['detail_url'])
        if item['detail_url'] in existing_map:
            item['applied'] = existing_map[item['detail_url']].get('applied', item['applied'])
    for item in errors:
        processed_set.add(item['detail_url'])

    processed['ids'] = list(processed_set)
    processed['last_updated'] = datetime.now().isoformat()
    safe_save_json(PROCESSED_FILE, processed, 'processed.json')

    merged: list[dict[str, Any]] = list(existing_collected)
    existing_detail_urls: set[str] = set(existing_map.keys())
    for item in collected:
        if item['detail_url'] not in existing_detail_urls:
            merged.append(item)

    _now: datetime = datetime.now()
    before: int = len(merged)
    merged = [item for item in merged if not _is_expired(item.get('deadline', ''), _now)]
    purged: int = before - len(merged)
    if purged > 0:
        out(f"  期限切れ除去: {purged}件")

    result: dict[str, Any] = {
        'timestamp': datetime.now().isoformat(),
        'total_on_page': len(unique_links),
        'new_items_processed': len(new_links),
        'success': success,
        'errors': len(errors),
        'collected': merged,
        'error_details': errors,
        'elapsed_seconds': round(time.time() - t0, 1),
    }
    safe_save_json(COLLECTED_FILE, result, 'collected.json')

    elapsed_total: float = time.time() - t0
    out(f"\n{'='*50}")
    out(f"完了: {elapsed_total:.1f}秒")
    out(f"  成功: {success}件")
    out(f"  エラー: {len(errors)}件")
    out(f"  処理済み累計: {len(processed_set)}件")

    x_urls: list[str] = [item['x_url'] for item in collected]
    out("\n収集したX URL:")
    for url in x_urls[:10]:
        out(f"  {url}")
    if len(x_urls) > 10:
        out(f"  ...他{len(x_urls)-10}件")

    return (success, len(errors), len(collected))
