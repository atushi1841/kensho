#!/usr/bin/env python3
"""tests/test_devto_weekly_pipeline.py — dev.to 週次パイプラインの偽成功根絶テスト (t_d5e647a1)

検証対象:
  - 認証: 生キーが Api-Key ヘッダに載る（マスク値ではない）
  - 失敗の可視化: 401 / id 欠落 / 非JSON は [FAIL] で SUCCESS を出さない（終了コードで通知）
  - 重複防止: .published.json に記録済みのファイルはスキップ（終了コード 3）
  - キー未設定: 公開を試みず終了コード 2
  - ペイロード形状: dev.to ドキュメントどおり {"article": {...}} で包む

curl は PATH 先頭に置いたスタブで差し替える（実ネットワークに触れない）。
"""

import json
import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import devto_weekly_pipeline as pipeline  # noqa: E402

RAW_KEY = "abcdef0123456789abcdef01"  # 24文字・実キー形式（テスト用ダミー。実キーではない）
CANDIDATE_MD = textwrap.dedent(
    """\
    ---
    title: "Test Article Title"
    tags: python, testing
    ---

    本文サンプル。
    """
)

STUB_CURL = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    LOG="${STUB_CURL_LOG:-/dev/null}"
    printf 'ARGS %s\\n' "$*" >> "$LOG"
    prev=""
    for a in "$@"; do
      if [ "$prev" = "-d" ]; then printf 'DATA %s\\n' "$a" >> "$LOG"; fi
      prev="$a"
    done
    case "$*" in
      *"-X POST"*)
        printf '%s\\n%s' "$(cat "$STUB_POST_BODY_FILE")" "$(cat "$STUB_POST_CODE_FILE")"
        ;;
      *)
        printf '%s\\n%s' "$(cat "$STUB_GET_BODY_FILE")" "$(cat "$STUB_GET_CODE_FILE")"
        ;;
    esac
    """
)


class Harness:
    """tmp の blog/env/スタブcurl でパイプラインを1回走らせる環境。"""

    def __init__(self, tmp_path: Path, key: str = RAW_KEY):
        self.blog = tmp_path / "blog"
        self.blog.mkdir()
        # t_1f4779d4: 同期元draftsをtmpに固定し、実リポの reports/journalism/drafts
        # （例: devto-2026W40.md）がテストのblog/stateに混入するのを遮断する。
        self.drafts = tmp_path / "drafts"
        self.drafts.mkdir()
        self.envfile = tmp_path / ".env"
        self.envfile.write_text(f"OTHER=1\nDEVTO_API_KEY={key}\n", encoding="utf-8")
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        stub = self.bin / "curl"
        stub.write_text(STUB_CURL, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        self.log = tmp_path / "curl.log"
        self.post_body = tmp_path / "post.body"
        self.post_code = tmp_path / "post.code"
        self.get_body = tmp_path / "get.body"
        self.get_code = tmp_path / "get.code"
        self.set_post("{}", 401)
        self.set_get("{}", 200)

    def add_candidate(self, name: str = "article.md", body: str = CANDIDATE_MD):
        (self.blog / name).write_text(body, encoding="utf-8")
        return name

    def set_post(self, body: str, code: int):
        self.post_body.write_text(body, encoding="utf-8")
        self.post_code.write_text(str(code), encoding="utf-8")

    def set_get(self, body: str, code: int):
        self.get_body.write_text(body, encoding="utf-8")
        self.get_code.write_text(str(code), encoding="utf-8")

    def run(self):
        env = os.environ.copy()
        env.pop("DEVTO_API_KEY", None)
        env.update({
            "PATH": f"{self.bin}:{env.get('PATH', '')}",
            "DEVTO_ENV_FILE": str(self.envfile),
            "DEVTO_BLOG_DIR": str(self.blog),
            "DEVTO_DRAFTS_DIR": str(self.drafts),
            "STUB_CURL_LOG": str(self.log),
            "STUB_POST_BODY_FILE": str(self.post_body),
            "STUB_POST_CODE_FILE": str(self.post_code),
            "STUB_GET_BODY_FILE": str(self.get_body),
            "STUB_GET_CODE_FILE": str(self.get_code),
        })
        proc = subprocess.run(
            [sys.executable, str(REPO / "devto_weekly_pipeline.py")],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO),
        )
        proc.curl_log = self.log.read_text(encoding="utf-8") if self.log.exists() else ""
        return proc

    def state(self):
        path = self.blog / ".published.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


# ── 旧バグの再発防止（真因） ────────────────────────────────────────────
def test_raw_key_is_sent_and_masked_value_is_not(tmp_path):
    """旧実装はマスク済み文字列を Api-Key に送っていた（常時401の真因）。"""
    h = Harness(tmp_path)
    h.add_candidate()
    h.set_post(json.dumps({"id": 999001, "url": "https://dev.to/example/999001"}), 200)
    h.set_get(json.dumps({"id": 999001, "url": "https://dev.to/example/999001"}), 200)

    proc = h.run()

    assert proc.returncode == pipeline.EXIT_OK, proc.stdout + proc.stderr
    assert f"Api-Key: {RAW_KEY}" in proc.curl_log  # 生キーがヘッダに載る
    assert "...[REDACTED]" not in proc.curl_log     # マスク値は送らない
    assert RAW_KEY not in proc.stdout               # 生キーを表示しない
    assert "[SUCCESS] Published article ID=999001" in proc.stdout
    assert "[VERIFY] Article confirmed live (HTTP 200, id=999001)" in proc.stdout


def test_payload_is_wrapped_in_article_object(tmp_path):
    """dev.to docs: POST /api/articles の本文は {"article": {...}}。"""
    h = Harness(tmp_path)
    h.add_candidate()
    h.set_post(json.dumps({"id": 999002, "url": "https://dev.to/example/999002"}), 200)
    h.set_get(json.dumps({"id": 999002, "url": "https://dev.to/example/999002"}), 200)

    proc = h.run()

    assert proc.returncode == pipeline.EXIT_OK
    data_lines = [l for l in proc.curl_log.splitlines() if l.startswith("DATA ")]
    assert data_lines, proc.curl_log
    payload = json.loads(data_lines[0][len("DATA "):])
    assert set(payload) == {"article"}
    assert payload["article"]["published"] is True
    assert payload["article"]["title"] == "Test Article Title"


# ── 偽成功の根絶 ────────────────────────────────────────────────────────
def test_401_is_failure_not_success(tmp_path):
    h = Harness(tmp_path)
    h.add_candidate()
    h.set_post(json.dumps({"error": "unauthorized"}), 401)

    proc = h.run()

    assert proc.returncode == pipeline.EXIT_PUBLISH_FAILED, proc.stdout
    assert "[FAIL] dev.to API 認証エラー HTTP 401" in proc.stdout
    assert "[SUCCESS]" not in proc.stdout        # 旧実装はここで偽の SUCCESS を出していた
    assert h.state() is None                     # 失敗を公開済みとして記録しない


def test_http_200_without_id_is_failure(tmp_path):
    h = Harness(tmp_path)
    h.add_candidate()
    h.set_post(json.dumps({"status": "ok"}), 200)  # id なし

    proc = h.run()

    assert proc.returncode == pipeline.EXIT_PUBLISH_FAILED, proc.stdout
    assert "有効な id がありません" in proc.stdout
    assert "[SUCCESS]" not in proc.stdout


def test_non_json_body_is_failure(tmp_path):
    h = Harness(tmp_path)
    h.add_candidate()
    h.set_post("<html>502 Bad Gateway</html>", 502)

    proc = h.run()

    assert proc.returncode == pipeline.EXIT_PUBLISH_FAILED, proc.stdout
    assert "[FAIL] dev.to API HTTP 502" in proc.stdout
    assert "[SUCCESS]" not in proc.stdout


# ── キー未設定（要ユーザー対応）と重複防止 ───────────────────────────────
def test_placeholder_key_exits_2_without_request(tmp_path):
    h = Harness(tmp_path, key="***")
    h.add_candidate()

    proc = h.run()

    assert proc.returncode == pipeline.EXIT_KEY_INVALID, proc.stdout
    assert "[FAIL]" in proc.stdout and "プレースホルダ" in proc.stdout
    assert proc.curl_log == ""                   # 無駄な 401 リクエストすら出さない


def test_already_published_candidate_is_skipped(tmp_path):
    h = Harness(tmp_path)
    name = h.add_candidate()
    (h.blog / ".published.json").write_text(
        json.dumps({name: {"id": 4606013, "url": "https://dev.to/x", "published_at": "2026-09-08T11:17:20"}}),
        encoding="utf-8",
    )

    proc = h.run()

    assert proc.returncode == pipeline.EXIT_NO_CANDIDATES, proc.stdout
    assert f"[SKIP] already published: {name}" in proc.stdout
    assert proc.curl_log == ""                   # 二重投稿しない


def test_published_state_written_after_success(tmp_path):
    h = Harness(tmp_path)
    name = h.add_candidate()
    h.set_post(json.dumps({"id": 999003, "url": "https://dev.to/example/999003"}), 200)
    h.set_get(json.dumps({"id": 999003, "url": "https://dev.to/example/999003"}), 200)

    proc = h.run()

    assert proc.returncode == pipeline.EXIT_OK
    state = h.state()
    assert state and state[name]["id"] == 999003
    assert state[name]["url"] == "https://dev.to/example/999003"


# ── 単体（キー・frontmatter） ───────────────────────────────────────────
def test_mask_key_hides_the_value():
    assert pipeline.mask_key(RAW_KEY) == "abcd...[REDACTED]ef01"
    assert pipeline.mask_key("***") == "[REDACTED]"
    assert pipeline.mask_key("") == "[REDACTED]"


@pytest.mark.parametrize("key,expected", [
    (RAW_KEY, True),
    ("***", False),
    ("", False),
    ("short", False),
    ("abcdef0123456789abcdef0!", False),
])
def test_is_valid_key(key, expected):
    assert pipeline.is_valid_key(key) is expected


def test_discover_parses_frontmatter_and_state_roundtrip(tmp_path):
    h = Harness(tmp_path)
    name = h.add_candidate()
    found = pipeline.discover_draft_articles(str(h.blog))
    assert [c["filename"] for c in found] == [name]
    assert found[0]["title"] == "Test Article Title"
    assert found[0]["tags"] == ["python", "testing"]

    path = h.blog / ".published.json"
    pipeline.save_published_state({name: {"id": 1, "url": "u", "published_at": "t"}}, str(path))
    assert pipeline.load_published_state(str(path))[name]["id"] == 1


# ── 本番実行実体との一致性（cron は profile scripts 側を実行する） ────────
def test_live_profile_copy_matches_repo_copy():
    """cron d538be4f5549 が実行する profile scripts 側が repo 正本と同一であること。"""
    live = Path.home() / ".hermes/profiles/kensho-sweeps/scripts/devto_weekly_pipeline.py"
    if not live.exists():
        pytest.skip("live profile copy not present in this environment")
    assert live.read_bytes() == (REPO / "devto_weekly_pipeline.py").read_bytes(), (
        "profile scripts 側が repo 正本と乖離している（cron は profile 側を実行するため要同期）"
    )
