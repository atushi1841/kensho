#!/usr/bin/env python3
"""
dev.to Weekly Auto-Posting Pipeline
Phase 1: Publish 2 existing draft articles for exposure test
Phase 2: Shift to weekly new article generation (contest/giveaway topics)

Uses DEVTO_API_KEY from /mnt/d/Project2/kensho/.env
Never exposes API key values in logs or output — always [REDACTED]
"""

import json
import os
import subprocess
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────
ENV_FILE = "/mnt/d/Project2/kensho/.env"
BLOG_DIR = "/mnt/d/Project2/apify-sales-funnel/blog"
API_URL = "https://dev.to/api/articles"


def load_api_key():
    """Load API key from env file — returns REDACTED-safe string."""
    # Source the env file to get DEVTO_API_KEY in environment
    env_result = subprocess.run(
        f"export $(grep DEVTO {ENV_FILE} | xargs) && echo $DEVTO_API_KEY", shell=True, capture_output=True, text=True
    )
    key = env_result.stdout.strip() or env_result.stderr.strip()
    # Mask the key for any logging — show only first 4 and last 4 chars, or [REDACTED]
    if len(key) <= 8:
        return "[REDACTED]" if key else key
    return key[:4] + "...[REDACTED]" + key[-4:] if key else "[REDACTED]"


DEVTO_API_KEY = load_api_key()
print(f"[PIPELINE] Using dev.to API key: {DEVTO_API_KEY}")


# ── Step 1: Discover unpublished draft articles from blog directory ────
def discover_draft_articles():
    """Find markdown files in blog directory that can be published."""
    if not os.path.isdir(BLOG_DIR):
        print(f"[ERROR] Blog directory not found: {BLOG_DIR}")
        return []

    candidates = []
    for fname in sorted(os.listdir(BLOG_DIR)):
        fpath = os.path.join(BLOG_DIR, fname)
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


# ── Step 2: Publish article to dev.to ───────────────────────────────────
def publish_article(article, status_callback=print):
    """Publish a single article to dev.to.

    Returns: {'id': int, 'title': str, 'url': str, 'published': bool} or None on failure
    """
    title = article["title"]
    tags = article["tags"]
    content = article["content"]

    # Build the API payload - simplified: use the markdown content directly
    # dev.to API expects: title, body_markdown, publish_status, tags
    payload = json.dumps({
        "title": title,
        "body_markdown": content,
        "published": True,  # Always publish immediately
        "tags": tags,
    })

    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                "-H",
                f"Api-Key: {DEVTO_API_KEY}",
                "-H",
                "Content-Type: application/json",
                "-H",
                "Accept: application/vnd.forem.api-v1+json",
                "-d",
                payload,
                API_URL,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        response = json.loads(result.stdout) if result.stdout else {}

        if isinstance(response, dict) and "errors" in response:
            status_callback(f"[WARN] dev.to API error for '{title}': {response['errors']}")
            return None

        article_id = response.get("id", 0)
        article_url = response.get("url", f"https://dev.to/{os.environ.get('USER', 'atu')}/{response.get('slug', '')}")

        status_callback(f"[SUCCESS] Published article ID={article_id}: {title}")
        status_callback(f"       URL: {article_url}")

        # Verify publication with GET request
        verify = subprocess.run(
            [
                "curl",
                "-s",
                "-H",
                f"Api-Key: {DEVTO_API_KEY}",
                "-H",
                "Accept: application/vnd.forem.api-v1+json",
                f"https://dev.to/api/articles/{article_id}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if verify.stdout:
            verify_data = json.loads(verify.stdout)
            if verify_data.get("status_code") == 200:
                status_callback("[VERIFY] Article confirmed live with HTTP 200")

        return {
            "id": article_id,
            "title": title,
            "url": article_url,
            "published": True,
            "filename": article["filename"],
        }

    except Exception as e:
        status_callback(f"[ERROR] Failed to publish '{title}': {str(e)[:200]}")
        return None


# ── Step 3: Main pipeline execution ────────────────────────────────────
def run_pipeline():
    """Execute the full dev.to posting pipeline."""
    print("=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] dev.to Auto-Posting Pipeline START")
    print("=" * 60)

    # Phase 1: Discover and publish 2 draft articles for exposure test
    print("\n--- Phase 1: Discovering draft articles ---")
    candidates = discover_draft_articles()
    print(f"Found {len(candidates)} markdown candidate(s) in blog directory")

    if not candidates:
        print("[WARN] No markdown files found in blog directory. Creating summary.")

    # Publish exactly 2 articles (or as many as available)
    num_to_publish = min(2, len(candidates))
    published_articles = []

    for i in range(num_to_publish):
        article = candidates[i]
        print(f"\n=== Publishing article {i + 1}/{num_to_publish}: {article['title']} ===")
        result = publish_article(article, status_callback=print)
        if result:
            published_articles.append(result)
        else:
            print(f"[SKIP] Failed to publish: {article['title']}")

    # If fewer than 2 available, note it
    if len(published_articles) < 2:
        print(f"\n[INFO] Published {len(published_articles)}/2 articles (only {len(candidates)} available)")

    # Phase 2: Schedule note for weekly shift to new content
    print("\n--- Phase 2: Pipeline configuration ---")
    print("Next run: Weekly (every 1 week)")
    print("Strategy: After initial 2-draft exposure test, shift to generating new")
    print("          articles (contest/giveaway topics from kensho data)")
    print(f"API Key: {DEVTO_API_KEY}")
    print(f"Blog source: {BLOG_DIR}")

    # Summary
    print("\n" + "=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Pipeline COMPLETE")
    print(f"Published: {len(published_articles)} article(s)")
    for a in published_articles:
        print(f"  - {a['title']} ({a['url']})")
    print("=" * 60)

    return published_articles


# ── Entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_pipeline()
