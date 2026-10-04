#!/usr/bin/env python3
"""dev.to Weekly Auto-Posting Pipeline

Phase 1: 既存ドラフト記事を公開して露出テスト（最大2件/回）
Phase 2: 週1で新規記事生成（懸賞/データネタ）へ移行

2026-09-25 (t_d5e647a1) 修正 — 「偽の成功」で外部導線が無言死していた真因:
  1. 認証: 従来はマスク済み文字列（key[:4] + "...[REDACTED]" + key[-4:]）を Api-Key ヘッダに
     送っていたため常に 401。生キーは認証のみ、表示は mask_key() のみ。
  2. 検証: HTTP ステータスを見ず response.get("id", 0) を [SUCCESS] と表示していた
     （401 の本文でも「Published article ID=0」）。curl -w '%{http_code}' で検査し、
     非2xx / id 不在 / 非JSON は [FAIL]。
  3. 公開後の確認: 旧実装は存在しない status_code キーを期待しており機能していなかった。
     HTTP 200 かつ id 一致のときだけ [VERIFY]。
  4. 重複防止: blog/.published.json に公開済みファイルを記録し、記録済みはスキップ
     （キー復旧時に同一記事を二重投稿しない）。
  5. 終了コード: 0=1件以上公開成功 / 1=候補ありで公開失敗 / 2=キー未設定・プレースホルダ /
     3=未公開候補0件。偽の成功は全面禁止。

Uses DEVTO_API_KEY from /mnt/d/Project2/kensho/.env
Never exposes API key values in logs or output — always [REDACTED]
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────
DEFAULT_ENV_FILE = "/mnt/d/Project2/kensho/.env"
DEFAULT_BLOG_DIR = "/mnt/d/Project2/apify-sales-funnel/blog"
# dev.to タグ上限は4
MAX_TAGS = 4
# 下書き生成先（kensho_data_journalism.py が outdir=reports/journalism/drafts に書く）
# このディレクトリの devto-*.md を blog dir へ同期してから公開する（2026-09-27 t_fa77fd1e: 
# 下書きが blog dir にいなければ EXIT_NO_CANDIDATES で外部導線が無言死していた）
DEFAULT_DRAFTS_DIR = "/mnt/d/Project2/kensho/reports/journalism/drafts"
API_URL = "https://dev.to/api/articles"
KEY_NAME = "DEVTO_API_KEY"
STATE_FILENAME = ".published.json"

# 終了コード契約（cron の last_status で異常が見えるようにする）
EXIT_OK = 0                 # 1件以上公開成功
EXIT_PUBLISH_FAILED = 1     # 候補はあったが公開できなかった
EXIT_KEY_INVALID = 2        # キー未設定/プレースホルダ（要ユーザー対応）
EXIT_NO_CANDIDATES = 3      # 未公開候補が0件（新規記事待ち）

# dev.to の API キーは 24 文字前後の英数字。プレースホルダ（*** 等）を弾く。
MIN_KEY_LEN = 12
KEY_CHARSET = re.compile(r"[A-Za-z0-9_-]+")


def env_file():
    return os.environ.get("DEVTO_ENV_FILE", DEFAULT_ENV_FILE)


def blog_dir():
    return os.environ.get("DEVTO_BLOG_DIR", DEFAULT_BLOG_DIR)


def _snippet(text, limit=200):
    return " ".join(str(text).split())[:limit]


# ── API key handling ───────────────────────────────────────────────────
def load_api_key(path=None):
    """.env（無ければ環境変数）から生キーを返す。

    戻り値をそのままログへ出さないこと。表示は mask_key() を通す。
    """
    # .env 内に KEY_NAME が複数行ある場合（*** プレースホルダ + 実キーなど）、
    # 最初の一致で break しない。プレースホルダ/無効キーを飛ばして最初の有効キーを返す。
    # 2026-09-28 (t_2f8a0c1d): 従来は最初の行（***）を返して EXIT_KEY_INVALID になることが多かった。
    valid_key = ""
    last_key = ""
    target = path or env_file()
    try:
        with open(target, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                if name.strip() == KEY_NAME:
                    value = value.strip().strip('"').strip("'")
                    last_key = value
                    if is_valid_key(value):
                        valid_key = value
                        break
    except (FileNotFoundError, PermissionError, OSError):
        pass
    key = valid_key or last_key
    if not key:
        key = os.environ.get(KEY_NAME, "").strip()
    return key


def mask_key(key):
    """表示専用のマスク（値をそのまま出さない）。"""
    if not key or len(key) <= 8:
        return "[REDACTED]"
    return key[:4] + "...[REDACTED]" + key[-4:]


def is_valid_key(key):
    """実キーらしい形式か（空・プレースホルダを弾く）。"""
    if not key or len(key) < MIN_KEY_LEN:
        return False
    return bool(KEY_CHARSET.fullmatch(key))


# ── curl wrapper ───────────────────────────────────────────────────────
def _curl_json(args, timeout):
    """curl を実行し (http_code, body) を返す（本文だけを見て成功判定しない）。"""
    cmd = ["curl", "-s", "-w", "\n%{http_code}"] + list(args)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 0, ""
    out = proc.stdout or ""
    body, sep, code = out.rpartition("\n")
    if not sep:
        body, code = out, ""
    try:
        http_code = int(code.strip())
    except ValueError:
        http_code = 0
    return http_code, body


def _parse_json(body):
    if not (body or "").strip():
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


# ── Step 1: Discover unpublished draft articles from blog directory ────
def sync_drafts(drafts_dir=None, bdir=None):
    """reports/journalism/drafts の devto-*.md を blog dir へ同期する。

    2026-09-27 t_fa77fd1e: kensho_data_journalism.py は reports/journalism/drafts/
    に下書きを書くが、devto_weekly_pipeline.py は blog dir を探索していたため
    下書きが blog dir に存在せず EXIT_NO_CANDIDATES（無言死）になっていた。
    ここでは既公開済み（published state に記録済み）のファイルのみスキップする。
    """
    src = drafts_dir or DEFAULT_DRAFTS_DIR
    dst = bdir or DEFAULT_BLOG_DIR
    if not os.path.isdir(src):
        print(f"[SYNC] drafts dir not found: {src} — スキップ")
        return []
    os.makedirs(dst, exist_ok=True)
    state = load_published_state(state_path(dst))
    synced = []
    for fname in sorted(os.listdir(src)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(src, fname)
        if not os.path.isfile(fpath):
            continue
        if fname in state:
            print(f"[SYNC] SKIP 已公開: {fname} (id={state[fname].get('id')})")
            continue
        dest = os.path.join(dst, fname)
        try:
            shutil.copy2(fpath, dest)
            synced.append(fname)
            print(f"[SYNC] 同期: {fname} → {dst}")
        except OSError as exc:
            print(f"[SYNC] FAIL {fname}: {exc}")
    return synced


def discover_draft_articles(bdir=None):
    """Find markdown files in blog directory that can be published."""
    target = bdir or blog_dir()
    if not os.path.isdir(target):
        print(f"[ERROR] Blog directory not found: {target}")
        return []

    candidates = []
    for fname in sorted(os.listdir(target)):
        fpath = os.path.join(target, fname)
        if not os.path.isfile(fpath):
            continue

        # Only process .md files (html files are landing pages, not articles)
        if not fname.endswith(".md"):
            continue

        with open(fpath, encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Extract title from frontmatter
        title = "Untitled"
        tags = []
        for line in content.split("\n")[:15]:
            line = line.strip()
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("tags:"):
                tags_str = line.split(":", 1)[1].strip()
                tags = [t.strip() for t in tags_str.split(",")]

        candidates.append({
            "filename": fname,
            "filepath": fpath,
            "title": title,
            "tags": tags if tags else ["development", "automation"],
            "content": content,
        })

    return candidates


# ── Published state (重複投稿防止) ──────────────────────────────────────
def state_path(bdir=None):
    return os.path.join(bdir or blog_dir(), STATE_FILENAME)


def load_published_state(path=None):
    """公開済み記録 {filename: {id, url, published_at}} を読む。"""
    target = path or state_path()
    try:
        with open(target, encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_published_state(state, path=None):
    """tmp + os.replace の原子的書換（部分書きを残さない）。"""
    target = path or state_path()
    directory = os.path.dirname(target) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".published-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ── Step 2: Publish article to dev.to ──────────────────────────────────
def publish_article(article, status_callback=print, api_key=None, published_state=None):
    """Publish a single article to dev.to.

    Returns: {'id': int, 'title': str, 'url': str, 'published': bool, 'verified': bool}
             失敗時 None（偽の成功を返さない）
    """
    title = article["title"]
    tags = article["tags"]
    if not isinstance(tags, list):
        tags = []
    tags = tags[:MAX_TAGS] if tags else ["development","automation"]
    content = article["content"]
    key = api_key if api_key is not None else load_api_key()

    if not is_valid_key(key):
        status_callback(
            f"[FAIL] {KEY_NAME} が未設定またはプレースホルダです（dev.to ダッシュボードで再発行し .env へ）"
        )
        return None

    # dev.to API のリクエスト本文は {"article": {...}} で包む（docs: POST /api/articles）
    payload = json.dumps({
        "article": {
            "title": title,
            "body_markdown": content,
            "published": True,
            "tags": tags,
        }
    })

    import time
    retry_delays = [30, 60, 120]
    last_code = 0
    last_body = ""
    for attempt in range(1, 4):
        http_code, body = _curl_json(
            [
                "-X", "POST",
                "-H", f"Api-Key: {key}",
                            "-H", "Content-Type: application/json",
                "-H", "Accept: application/vnd.forem.api-v1+json",
                "-d", payload,
                API_URL,
            ],
            timeout=120,
        )
        last_code, last_body = http_code, body
        if http_code == 429:
            if attempt < 3:
                status_callback(f"[WARN] HTTP 429 rate limit, retry {attempt}/3 after {retry_delays[attempt-1]}s")
                time.sleep(retry_delays[attempt-1])
                continue
        break
    http_code, body = last_code, last_body

    if http_code in (401, 403):
        status_callback(
            f"[FAIL] dev.to API 認証エラー HTTP {http_code}（{KEY_NAME} が無効/失効）: {title}"
        )
        return None
    if not (200 <= http_code < 300):
        status_callback(
            f"[FAIL] dev.to API HTTP {http_code} のため公開できません: {title} / {_snippet(body)}"
        )
        return None

    response = _parse_json(body)
    if response is None:
        status_callback(
            f"[FAIL] dev.to API 応答が JSON として解釈できません（HTTP {http_code}）: {_snippet(body)}"
        )
        return None
    if isinstance(response, dict) and ("error" in response or "errors" in response):
        status_callback(
            f"[FAIL] dev.to API error for '{title}': "
            f"{_snippet(response.get('errors') or response.get('error'))}"
        )
        return None

    article_id = response.get("id") if isinstance(response, dict) else None
    if not isinstance(article_id, int) or article_id <= 0:
        status_callback(
            f"[FAIL] dev.to API 応答に有効な id がありません（HTTP {http_code}）: {_snippet(body)}"
        )
        return None

    # 作成できた時点で URL は API 応答のみを使う（捏造しない）
    article_url = ""
    if isinstance(response, dict):
        article_url = response.get("url") or response.get("canonical_url") or ""

    status_callback(f"[SUCCESS] Published article ID={article_id}: {title}")

    # 公開確認（HTTP 200 かつ id 一致のときだけ VERIFY）
    verify_code, verify_body = _curl_json(
        [
            "-H", f"Api-Key: {key}",
            "-H", "Accept: application/vnd.forem.api-v1+json",
            f"{API_URL}/{article_id}",
        ],
        timeout=30,
    )
    verified = False
    if verify_code == 200:
        verify_data = _parse_json(verify_body)
        if isinstance(verify_data, dict) and verify_data.get("id") == article_id:
            verified = True
            article_url = (
                verify_data.get("url") or verify_data.get("canonical_url") or article_url
            )
    if verified:
        status_callback(f"[VERIFY] Article confirmed live (HTTP 200, id={article_id})")
    else:
        status_callback(
            f"[WARN] 公開確認GETが HTTP {verify_code} / id不一致。id={article_id} は作成済みだが要確認"
        )

    if not article_url:
        article_url = "(URL未取得)"
    status_callback(f"       URL: {article_url}")

    result = {
        "id": article_id,
        "title": title,
        "url": article_url,
        "published": True,
        "verified": verified,
        "filename": article["filename"],
    }
    if published_state is not None:
        published_state[article["filename"]] = {
            "id": article_id,
            "url": article_url,
            "published_at": datetime.now().isoformat(timespec="seconds"),
        }
    return result


# ── Step 3: Main pipeline execution ────────────────────────────────────
def run_pipeline(bdir=None, state_file=None):
    """Execute the full dev.to posting pipeline. 戻り値は終了コード（上記契約）。"""
    target_dir = bdir or blog_dir()
    state_file = state_file or state_path(target_dir)
    key = load_api_key()
    state = load_published_state(state_file)

    print("=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] dev.to Auto-Posting Pipeline START")
    print("=" * 60)
    print(f"[PIPELINE] {KEY_NAME}: {mask_key(key)} (valid_format={is_valid_key(key)})")
    print(f"[PIPELINE] Blog: {target_dir}")
    print(f"[PIPELINE] Published state: {state_file} ({len(state)} record(s))")

    # Phase 0: 下書き同期（reports/journalism/drafts → blog dir）
    print("\n--- Phase 0: Sync draft articles from journalism/drafts ---")
    synced = sync_drafts(os.environ.get("DEVTO_DRAFTS_DIR"), target_dir)
    print(f"[SYNC] {len(synced)} file(s) synced")

    # Phase 1: 未公開候補の抽出
    print("\n--- Phase 1: Discovering draft articles ---")
    candidates = discover_draft_articles(target_dir)
    pending = []
    for article in candidates:
        if article["filename"] in state:
            print(
                f"[SKIP] already published: {article['filename']} "
                f"(id={state[article['filename']].get('id')})"
            )
        else:
            pending.append(article)
    print(f"Found {len(candidates)} markdown candidate(s) / 未公開 {len(pending)}")

    if not pending:
        print("[INFO] 未公開候補はありません（新規記事の追加待ち）")
        return EXIT_NO_CANDIDATES

    if not is_valid_key(key):
        print(f"[FAIL] {KEY_NAME} が未設定またはプレースホルダのため公開を中止（要ユーザー対応）")
        return EXIT_KEY_INVALID

    published_articles = []
    num_to_publish = min(2, len(pending))
    for i in range(num_to_publish):
        article = pending[i]
        print(f"\n=== Publishing article {i + 1}/{num_to_publish}: {article['title']} ===")
        result = publish_article(
            article, status_callback=print, api_key=key, published_state=state
        )
        if result:
            published_articles.append(result)
        else:
            print(f"[SKIP] Failed to publish: {article['title']}")

    if published_articles:
        try:
            save_published_state(state, state_file)
            print(f"[STATE] 公開済み記録を更新: {state_file}")
        except OSError as exc:
            print(f"[WARN] 公開済み記録の保存に失敗: {exc}")

    # Phase 2: 週次運用の案内
    print("\n--- Phase 2: Pipeline configuration ---")
    print("Next run: Weekly (every 1 week)")
    print("Strategy: 2ドラフトの露出テスト後は新規記事生成（懸賞/データネタ）へ移行")
    print(f"Blog source: {target_dir}")

    print("\n" + "=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Pipeline COMPLETE")
    print(f"Published: {len(published_articles)} article(s)")
    for a in published_articles:
        print(f"  - {a['title']} ({a['url']})")
    print("=" * 60)

    return EXIT_OK if published_articles else EXIT_PUBLISH_FAILED


# ── Entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.exit(run_pipeline())
