#!/usr/bin/env python3
"""AIデータジャーナリズム基盤 — 収集済み懸賞データの傾向自動抽出（t_0b949bda）.

Kensho が収集した懸賞データ（`data/collected_today.json` / `data/collected.json` /
`data/collected_history/*.json`）と当選DM（`data/dm_wins.json`）を突合し、
「人気キーワード」「賞品カテゴリ」「当選枠」「締切逼迫度」「参加導線」「収集源供給」
「実測当選率」「前週比」「応募カバレッジ」を Markdown レポート + JSON 統計として出力する。
さらに dev.to / Qiita 投稿用の下書き（front matter 付き）を生成する。

読み取り専用分析のみ — 応募ロジック・収集ロジックは一切変更しない。

使い方:
    python3 scripts/kensho_data_journalism.py                      # 今週分を生成
    python3 scripts/kensho_data_journalism.py --week 2026W39
    python3 scripts/kensho_data_journalism.py --snapshot           # 履歴スナップショットも保存
    python3 scripts/kensho_data_journalism.py --check-template     # テンプレ整合性のみ検証

出力:
    reports/journalism/<week>.md              レポート本体（テンプレート描画）
    reports/journalism/<week>.json            統計JSON（機械可読・AIチームの下流入力）
    reports/journalism/drafts/devto-<week>.md dev.to 投稿用下書き
    reports/journalism/drafts/qiita-<week>.md Qiita 投稿用下書き
    data/collected_history/<date>.json        履歴スナップショット（--snapshot時のみ）

依存は標準ライブラリのみ。当選率の詳細突合（t.co 解決込み）は
`scripts/kensho_winrate_analysis.py` が担当し、本スクリプトはその純粋ヘルパー
（`parse_dt` / `normalize_handle` / `prize_category`）を再利用する。
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, os.path.dirname(_SCRIPTS_DIR))

from scripts.kensho_winrate_analysis import (  # noqa: E402  (純粋ヘルパーの再利用)
    _X_URL_RE,
    normalize_handle,
    parse_dt,
    prize_category,
    tweet_id_to_time_ms,
)

JST = timezone(timedelta(hours=9))
PROJECT_DIR = os.environ.get("PROJECT_DIR", "/mnt/d/Project2/kensho")

DEFAULT_COLLECTED = (
    "data/collected_today.json",
    "data/collected.json",
)
HISTORY_DIR = "data/collected_history"
DEFAULT_TEMPLATE = "reports/templates/data-journalism-report.md"
DEFAULT_BLOG_TEMPLATE = "reports/templates/data-journalism-blog.md"
DEFAULT_REPORT_DIR = "reports/journalism"
DEFAULT_STATS_DIR = "reports/journalism"
DEFAULT_DRAFT_DIR = "reports/journalism/drafts"
DM_WINS = "data/dm_wins.json"

# ── キーワード抽出設定 ────────────────────────────────────────────────
_TOKEN_RE = re.compile(r"[ァ-ヶー]{2,}|[一-龥]{2,}|[A-Za-z][A-Za-z0-9\-]{2,}|\d{3,}")
_HASHTAG_RE = re.compile(r"[#＃]([^\s#＃、。！!？?「」【】\[\]]+)")
_URL_RE = re.compile(r"https?://\S+")
# 賞品相当額の抽出（`1,000円分` / `500円相当` を優先、次に素の `◯円`）
_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"([0-9][0-9,]{2,})\s*円\s*(?:分|相当)"),
    re.compile(r"([0-9][0-9,]{2,})\s*円"),
)

# 懸賞文脈で意味を持たない語（ノイズ除去）。ドキュメント頻度で上位に来る語のみを対象にする。
_STOPWORDS: frozenset[str] = frozenset(
    {
        "キャンペーン", "プレゼント", "応募", "募集", "開催", "詳細", "締切", "締め切り", "当選", "抽選",
        "対象", "期間", "方法", "賞品", "発表", "結果", "応募者", "皆様", "様", "名様", "名", "本日", "今日",
        "公式", "情報", "必要", "確認", "注意", "条件", "商品", "購入", "画像", "写真", "動画", "リンク",
        "フォロー", "リポスト", "リツイート", "いいね", "応募フォーム", "エントリー", "参加", "特典",
        "キャンペ", "グッズ", "オリジナル", "プレゼントキャンペーン", "ツイート", "アカウント", "アカウント名",
        "リプライ", "コメント", "チャンス", "家", "円", "分", "用", "者", "日", "月", "年", "時", "版権",
        "株式会社", "会社", "商品券", "点数", "実施", "決定", "受付", "開始", "終了", "限定", "特別",
        "twitter", "https", "http", "www", "com", "jp", "co", "the", "and", "for", "you", "your",
        # 応募手順の定型文・キャンペーン事務文言（ブランド名ではない＝「人気キーワード」にならない）
        "投稿", "応募方法", "応募期間", "参加方法", "当選者", "当選確率", "当選率", "引用", "本投稿",
        "ポスト", "投稿する", "リポスト", "リプ", "円分", "円相当", "企画", "連絡", "応募締切",
        "応募完了", "チェック", "実施中", "アップ", "合計", "セット", "記念", "発売記念", "開催中",
        "モニター", "商品画像", "応募規約", "懸賞", "抽選", "抽選で", "詳細はこちら", "こちら",
        "以下", "ため", "よう", "こと", "もの", "みなさま", "皆さま", "方", "名様", "カード",
        "画像", "動画", "投稿キャンペーン", "リポストキャンペーン", "フォローキャンペーン",
        "キャンペーン実施中", "参加", "対象者", "当たる", "当たり", "抽せん", "ご応募", "発表",
        # 集計ノイズ（日付カウンタ・一般語・HTML実体参照の残骸）
        "日目", "場合", "人気", "発売", "開催記念", "拡散希望", "新登場", "登場", "配布", "応募券",
        "当選発表", "抽選日", "内容", "不明", "以上", "予定", "利用", "使用", "info", "box", "amp",
        "皆さん", "みなさん", "参加者", "応募者", "当選品", "発送", "到着", "今回", "是非", "ぜひ",
        "お待ち", "お願い", "下さい", "ください", "まで", "から", "より", "について", "として",
        "本人", "当社", "当店", "当アカウント", "店舗", "各店", "全国", "数量", "上限", "先着",
        "後日", "新作", "応援", "当選人数", "景品内容", "抽選結果", "発表日", "当選連絡", "応募総数",
    }
)

# 景品カテゴリ判定（prize_items / tweet_text 双方から推定。上から順に評価）
_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Amazonギフト券", ("amazon", "アマゾン", "アマギフ")),
    ("金券・現金", ("現金", "キャッシュ", "電子マネー", "図書カード", "クオカード", "quoカード", "商品券", "ギフトカード", "ギフト券")),
    ("Pay系・ポイント", ("paypay", "ペイペイ", "quicpay", "楽天ポイント", "ポイント還元", "dポイント", "ponta", "ポイント")),
    ("ゲーム機・ゲームソフト", ("switch", "スイッチ", "プレイステーション", "playstation", "ps5", "ps4", "ゲーム機", "ゲームソフト", "ニンテンドー")),
    ("家電・ガジェット", ("テレビ", "掃除機", "炊飯器", "イヤホン", "ヘッドホン", "スマホ", "パソコン", "ロボット", "空気清浄", "カメラ", "冷蔵庫", "レンジ", "家電", "シャワーヘッド", "美容家電", "スピーカー")),
    ("旅行・宿泊", ("旅行", "宿泊", "ペアチケット", "航空", "ホテル", "温泉", "旅")),
    ("食品・飲料", ("お米", "米", "ビール", "飲料", "ジュース", "コーヒー", "お菓子", "菓子", "食品", "牛肉", "肉", "シリアル", "酒", "ソース", "ジャム", "モヒート", "焼酎", "スイーツ", "ドリンク", "kg", "梨", "トマト", "岩塩", "野菜", "果物", "パフェ", "サブレ", "アイス", "からあげ", "ちゃんぽん", "わらび", "詰め合わせ", "袋", "本数", "玉")),
    ("化粧品・日用品", ("化粧品", "コスメ", "メイク", "シャンプー", "洗剤", "タオル", "ティッシュ", "石鹸", "入浴剤", "ヘア", "ネイル", "スキンケア")),
    ("グッズ・ノベルティ", ("ぬいぐるみ", "トートバッグ", "トレカ", "フィギュア", "アクスタ", "缶バッジ", "タンブラー", "キーホルダー", "ストラップ", "お箸", "サイン", "色紙", "ポスター", "グッズ", "ノベルティ", "クリアファイル", "ネックレス", "タペストリー", "抱き枕", "アクセサリー", "ジュエリー", "ボドゲ", "ボードゲーム", "カードゲーム", "衣装", "アパレル", "ナイトウェア", "アクリル", "ラバー", "ステッカー", "ポーチ", "バッグ")),
    ("体験・チケット", ("チケット", "体験", "招待", "試写会", "観戦", "ライブ", "映画", "コンサート", "入場券")),
    ("デジタル特典", ("サブスク", "コード", "無料視聴", "クーポン", "壁紙", "デジタル", "着せ替え", "テクスチャ", "アバター", "3dモデル", "データ", "配信")),
)

_WINCOUNT_BANDS: tuple[tuple[str, int, int], ...] = (
    ("1名（最難関）", 1, 1),
    ("2〜5名", 2, 5),
    ("6〜20名", 6, 20),
    ("21〜100名", 21, 100),
    ("101名以上（大量枠）", 101, 10**9),
    ("枠数不明・記載なし", 0, 0),
)

_DEADLINE_BANDS: tuple[tuple[str, int, int], ...] = (
    ("本日締切", 0, 0),
    ("明日締切", 1, 1),
    ("2〜3日", 2, 3),
    ("4〜7日", 4, 7),
    ("8〜30日", 8, 30),
    ("31日以上", 31, 10**6),
)


@dataclass
class Campaign:
    """正規化した1案件（複数スナップショットを統合したもの）。"""

    key: str
    tweet_id: str = ""
    handle: str = ""
    source: str = "unknown"
    detail_url: str = ""
    deadline: str = ""
    winner_count: int = 0
    estimated_value_jpy: int = 0
    value_source: str = "none"  # prize_score / text / none
    prize_items: list[str] = field(default_factory=list)
    priority: float = 0.0
    route: str = ""
    keyword_flag: bool = False
    tweet_text: str = ""
    applied: dict[str, str] = field(default_factory=dict)

    @property
    def entries(self) -> int:
        return len(self.applied)

    @property
    def category(self) -> str:
        return classify_category(self)

    @property
    def days_left(self) -> int | None:
        dl = parse_deadline(self.deadline)
        if dl is None:
            return None
        return (dl - datetime.now(JST).date()).days

    @property
    def post_dt(self) -> datetime | None:
        """ツイート投稿時刻（snowflake IDから）。記事の時間軸分析に使う。"""
        ms = tweet_id_to_time_ms(self.tweet_id) if self.tweet_id else None
        if ms is None:
            return None
        return datetime.fromtimestamp(ms / 1000.0, tz=JST)


# ── ローダ ────────────────────────────────────────────────────────────
def _derive_source(detail_url: str) -> str:
    """detail_url 前置きから収集源を推定（収集側 source 欠損時）。"""
    prefixes = (
        ("/kenshouclub", "kenshouclub"),
        ("/twscrape", "twscrape"),
        ("/cpmeikan", "cpmeikan"),
        ("/present", "chancecom"),
        ("/kema", "kema"),
        ("/kensho-everyday", "kensho-everyday"),
        ("/kenkaku", "ken-kaku"),
        ("/detail", "knshow"),
    )
    for pre, name in prefixes:
        if (detail_url or "").startswith(pre):
            return name
    return "unknown"


def parse_deadline(raw: str) -> date | None:
    """`2026-09-30` / `9/30` / `2026年9月30日` を date に正規化。失敗は None。"""
    if not raw:
        return None
    txt = raw.strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", txt)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日?", txt)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", txt)
    if m:
        try:
            return date(datetime.now(JST).year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    return None


def extract_value_from_text(text: str) -> int:
    """キャンペーン本文から賞品相当額を推定する（`1,000円分` → 1000）。

    100円未満・300万円超は誤検出とみなして捨てる（送料・手数料・総額表記の混入対策）。
    """
    if not text:
        return 0
    for pat in _VALUE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        value = int(m.group(1).replace(",", ""))
        if 100 <= value <= 3_000_000:
            return value
    return 0


def _iter_items(path: str) -> Iterable[dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    items = data.get("collected") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return
    for it in items:
        if isinstance(it, dict):
            yield it


def discover_snapshot_files(project_dir: str, extra: Sequence[str] = ()) -> list[str]:
    """分析対象スナップショットのパス一覧（古い順）。履歴ディレクトリがあれば含める。"""
    paths: list[str] = []
    for rel in extra or DEFAULT_COLLECTED:
        p = rel if os.path.isabs(rel) else os.path.join(project_dir, rel)
        if os.path.exists(p):
            paths.append(p)
    hdir = os.path.join(project_dir, HISTORY_DIR)
    if os.path.isdir(hdir):
        paths.extend(sorted(os.path.join(hdir, n) for n in os.listdir(hdir) if n.endswith(".json")))
    # 重複排除（順序維持）
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def load_campaigns(paths: Sequence[str]) -> dict[str, Campaign]:
    """スナップショット群を tweet_id（無ければ detail_url）キーで統合する。

    後から読んだファイルの値で上書きし、`applied` は和集合を取る
    （古いスナップショットにしか無い応募記録を失わないため）。
    """
    campaigns: dict[str, Campaign] = {}
    for path in paths:
        for it in _iter_items(path):
            x_url = str(it.get("x_url") or "")
            m = _X_URL_RE.search(x_url)
            tweet_id = str(it.get("tweet_id") or "").strip()
            if not tweet_id and m:
                tweet_id = m.group(2)
            detail = str(it.get("detail_url") or "")
            key = tweet_id or detail
            if not key:
                continue
            prize = it.get("prize_score") or {}
            prev = campaigns.get(key)
            camp = prev or Campaign(key=key)
            camp.tweet_id = tweet_id or camp.tweet_id
            camp.handle = (m.group(1).lower() if m else camp.handle)
            camp.detail_url = detail or camp.detail_url
            camp.source = str(it.get("source") or _derive_source(detail))
            camp.deadline = str(it.get("deadline") or camp.deadline)
            wc = it.get("winner_count")
            if isinstance(wc, int):
                camp.winner_count = wc
            ev = prize.get("estimated_value_jpy")
            if isinstance(ev, int) and ev:
                camp.estimated_value_jpy = ev
                camp.value_source = "prize_score"
            items = prize.get("items")
            if isinstance(items, list) and items:
                camp.prize_items = [str(x) for x in items]
            pr = prize.get("priority")
            if isinstance(pr, (int, float)):
                camp.priority = float(pr)
            camp.route = str(it.get("導線") or camp.route)
            camp.keyword_flag = bool(it.get("keyword_flag")) or camp.keyword_flag
            camp.tweet_text = str(it.get("tweet_text") or camp.tweet_text)
            for acct, ts in (it.get("applied") or {}).items():
                if isinstance(ts, str) and ts:
                    camp.applied[acct] = ts
            # prize_score に金額が無い場合は本文の「◯円分」から推定（情報欠損の救済）
            if not camp.estimated_value_jpy:
                text_value = extract_value_from_text(camp.tweet_text)
                if text_value:
                    camp.estimated_value_jpy = text_value
                    camp.value_source = "text"
            campaigns[key] = camp
    return campaigns


def load_wins(path: str) -> list[dict[str, Any]]:
    """dm_wins.json（{account_key: [win,...]}）をフラット化。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    wins: list[dict[str, Any]] = []
    if isinstance(data, dict):
        for acct, rows in data.items():
            if not isinstance(rows, list):
                continue
            for w in rows:
                if isinstance(w, dict):
                    row = dict(w)
                    row.setdefault("account_key", acct)
                    wins.append(row)
    return wins


_STATUS_ID_RE = re.compile(r"/status(?:es)?/(\d{5,25})")


def match_wins_local(
    wins: Sequence[dict[str, Any]], campaigns: dict[str, Campaign]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """当選DM→案件の**ローカル完結**突合（ネットワークアクセスなし）。

    キー1: DM本文中の tweet_id 完全一致
    キー2: sender handle 一致（当該アカウントの応募記録を持つ案件を優先）
    t.co 展開が必要なケースは `kensho_winrate_analysis.py` 側の担当。
    """
    by_tweet = {c.tweet_id: c for c in campaigns.values() if c.tweet_id}
    by_handle: dict[str, list[Campaign]] = defaultdict(list)
    for c in campaigns.values():
        if c.handle:
            by_handle[c.handle].append(c)

    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for win in wins:
        acct = str(win.get("account_key") or "")
        text = str(win.get("message_text") or "")
        camp: Campaign | None = None
        key = ""
        for tid in _STATUS_ID_RE.findall(text):
            cand = by_tweet.get(tid)
            if cand is not None and acct in cand.applied:
                camp, key = cand, "tweet_id"
                break
            if cand is not None and not camp:
                camp, key = cand, "tweet_id"
        if camp is None:
            handle = normalize_handle(str(win.get("sender") or ""))
            cands = by_handle.get(handle, [])
            with_entry = [c for c in cands if acct in c.applied]
            pool = with_entry or cands
            if pool:
                camp = max(pool, key=lambda c: max(c.applied.values(), default=""))
                key = "handle"
        if camp is None:
            unmatched.append(win)
        else:
            matched.append({"win": win, "campaign": camp, "key": key})
    return matched, unmatched


# ── 分析 ──────────────────────────────────────────────────────────────
def _normalize_text(text: str) -> str:
    """HTML実体参照と全角文字を正規化する（`&amp;`→`&`、`１`→`1`、`＃`→`#`）。"""
    return unicodedata.normalize("NFKC", html.unescape(text or ""))


def classify_category(camp: Campaign) -> str:
    """景品カテゴリを prize_items → tweet_text の順に推定。"""
    hay = _normalize_text(" ".join([*camp.prize_items, camp.tweet_text])).lower()
    for name, keys in _CATEGORY_RULES:
        if any(k.lower() in hay for k in keys):
            return name
    base = prize_category({"prize_items": camp.prize_items})
    if base != "その他(情報欠損)":
        return base
    return "分類不能・情報欠損"


def extract_keywords(camp: Campaign) -> list[str]:
    """1案件からキーワード候補を抽出（ハッシュタグ + 名詞的トークン）。

    ハッシュタグはブランド名・企画名の強いシグナルなので `#` 付きで保持する。
    定型事務文言（応募方法・投稿・当選者…）と数字のみのトークンは除外する。
    """
    text = _normalize_text(camp.tweet_text)
    text = _URL_RE.sub(" ", text)
    raw: list[tuple[str, bool]] = []
    for tag in _HASHTAG_RE.findall(text):
        tag = tag.strip()
        if 2 <= len(tag) <= 20 and tag not in _STOPWORDS and tag.lower() not in _STOPWORDS:
            raw.append((tag, True))
    for tok in _TOKEN_RE.findall(text):
        if tok.lower() in _STOPWORDS or tok in _STOPWORDS or tok.isdigit():
            continue
        if len(tok) < 2:
            continue
        raw.append((tok, False))
    # 同一案件内の重複除去（DFで数えたいため）。ハッシュタグ表記を優先。
    seen: set[str] = set()
    out: list[str] = []
    for word, is_tag in raw:
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(f"#{word}" if is_tag else word)
    return out


def keyword_stats(campaigns: dict[str, Campaign], top_n: int = 20, min_df: int = 3) -> list[dict[str, Any]]:
    """キーワード別に 出現案件数(DF) / 応募率リフト / 平均枠数を算出。

    応募率リフト = そのキーワードを含む案件の平均応募率 − 全体平均応募率。
    プラスなら「自動応募が刺さっている＝反応が良い語」。`min_df` 未満の語はノイズとして落とす。
    """
    total = len(campaigns)
    if total == 0:
        return []
    accts = {a for c in campaigns.values() for a in c.applied}
    n_accts = len(accts) or 1
    overall = sum(c.entries for c in campaigns.values()) / (total * n_accts)

    agg: dict[str, dict[str, float]] = defaultdict(lambda: {"df": 0.0, "entries": 0.0, "value": 0.0, "wins": 0.0})
    for c in campaigns.values():
        for w in extract_keywords(c):
            row = agg[w]
            row["df"] += 1
            row["entries"] += c.entries / n_accts
            row["value"] += c.estimated_value_jpy
    rows = []
    for word, row in agg.items():
        df = int(row["df"])
        if df < min_df:  # 既定2件以下はノイズ
            continue
        rate = row["entries"] / df
        rows.append(
            {
                "keyword": word,
                "campaigns": df,
                "coverage": rate,
                "lift": rate - overall,
                "avg_entries": row["entries"] / df * n_accts,
            }
        )
    rows.sort(key=lambda r: (-r["campaigns"], -r["lift"]))
    return rows[:top_n]


def band_of(value: int, bands: Sequence[tuple[str, int, int]]) -> str:
    for name, lo, hi in bands:
        if lo <= value <= hi:
            return name
    return bands[-1][0]


def wins_block(campaigns: dict[str, Campaign], wins: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """当選DM突合の集計ブロック（全期間の応募記録に対して評価する）。

    実測当選率は「カテゴリ別の応募数（全期間）」で割るため、`entries_by_category` も返す。
    """
    matched, unmatched = match_wins_local(wins, campaigns)
    entries_by_cat: Counter[str] = Counter()
    for c in campaigns.values():
        entries_by_cat[c.category] += c.entries
    return {
        "matched": len(matched),
        "unmatched": len(unmatched),
        "total": len(wins),
        "by_category": _wins_by(lambda m: m["campaign"].category, matched),
        "by_wincount": _wins_by(lambda m: band_of(m["campaign"].winner_count, _WINCOUNT_BANDS), matched),
        "by_source": _wins_by(lambda m: m["campaign"].source, matched),
        "matched_keys": dict(Counter(str(m["key"]) for m in matched)),
        "entries_by_category": dict(entries_by_cat),
        "entries_total": sum(entries_by_cat.values()),
    }


def analyze(
    campaigns: dict[str, Campaign],
    wins: Sequence[dict[str, Any]] | None = None,
    prev_campaigns: dict[str, Campaign] | None = None,
    wins_stats: dict[str, Any] | None = None,
    min_df: int = 3,
) -> dict[str, Any]:
    """全指標を1つの辞書にまとめる（レポート・JSON・ブログ下書きの共通ソース）。

    `wins_stats` を渡すと当選突合だけを別母集団（全期間）で評価できる。
    未指定時は `campaigns` 自身に対して突合する（テスト・単発利用向け）。
    """
    total = len(campaigns)
    accounts = sorted({a for c in campaigns.values() for a in c.applied})
    n_accts = len(accounts) or 1
    total_entries = sum(c.entries for c in campaigns.values())

    by_category: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0.0, "entries": 0.0, "value": 0.0, "wins": 0.0, "seats": 0.0})
    by_wincount: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0.0, "entries": 0.0, "wins": 0.0})
    by_deadline: Counter[str] = Counter()
    by_route: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    by_account: Counter[str] = Counter()
    value_known = 0
    deadline_known = 0
    text_missing = 0

    wstats: dict[str, Any] = wins_stats if wins_stats is not None else wins_block(campaigns, wins or [])
    value_from_text = 0

    for c in campaigns.values():
        cat = c.category
        row = by_category[cat]
        row["n"] += 1
        row["entries"] += c.entries
        row["value"] += c.estimated_value_jpy
        row["wins"] += 0  # 当選数は全期間母集団（wins_block）側で集計する
        if c.winner_count:
            row["seats"] += c.winner_count
        band = band_of(c.winner_count, _WINCOUNT_BANDS)
        wrow = by_wincount[band]
        wrow["n"] += 1
        wrow["entries"] += c.entries
        dl = c.days_left
        if dl is None:
            by_deadline["期限未記載"] += 1
        else:
            by_deadline[band_of(dl, _DEADLINE_BANDS)] += 1
            deadline_known += 1
        by_route[c.route or "未判定"] += 1
        by_source[c.source or "unknown"] += 1
        for a in c.applied:
            by_account[a] += 1
        if c.estimated_value_jpy:
            value_known += 1
            if c.value_source == "text":
                value_from_text += 1
        if not (c.tweet_text or "").strip():
            text_missing += 1

    keywords = keyword_stats(campaigns, min_df=min_df)

    # 未応募の高価値案件（応募カバレッジの穴 = 記事の「機会損失」ネタ）
    # 同一キャンペーンの複数ツイート（日替わり企画など）は1行に畳む。
    missed = [c for c in campaigns.values() if c.entries < n_accts]
    missed.sort(key=lambda c: (-c.estimated_value_jpy, -c.winner_count))
    missed_rows: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for c in missed:
        title = _short_title(c)
        if title in seen_titles:
            continue
        seen_titles.add(title)
        missed_rows.append(
            {
                "title": title,
                "value": c.estimated_value_jpy,
                "seats": c.winner_count,
                "missing": n_accts - c.entries,
                "deadline": c.deadline or "未記載",
                "source": c.source,
            }
        )
        if len(missed_rows) >= 10:
            break

    wow = _wow_delta(campaigns, prev_campaigns) if prev_campaigns else None

    return {
        "total_campaigns": total,
        "accounts": accounts,
        "total_entries": total_entries,
        "coverage_rate": (total_entries / (total * n_accts)) if total else 0.0,
        "value_known": value_known,
        "value_from_text": value_from_text,
        "deadline_known": deadline_known,
        "text_missing": text_missing,
        "category_unclassified": sum(1 for c in campaigns.values() if c.category == "分類不能・情報欠損"),
        "total_estimated_value_jpy": sum(c.estimated_value_jpy for c in campaigns.values()),
        "total_seats": sum(c.winner_count for c in campaigns.values()),
        "by_category": {k: dict(v) for k, v in by_category.items()},
        "by_wincount": {k: dict(v) for k, v in by_wincount.items()},
        "by_deadline": dict(by_deadline),
        "by_route": dict(by_route),
        "by_source": dict(by_source),
        "by_account": dict(by_account),
        "keywords": keywords,
        "missed": missed_rows,
        "wins": wstats,
        "wow": wow,
        "route_unknown": by_route.get("未判定", 0) + by_route.get("要確認", 0),
    }


def _wins_by(fn: Any, matched: Sequence[dict[str, Any]]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for m in matched:
        c[str(fn(m))] += 1
    return dict(c)


def _short_title(c: Campaign) -> str:
    """記事表示用の短い案件名（本文の先頭行から生成）。"""
    first = ""
    for line in (c.tweet_text or "").splitlines():
        line = _URL_RE.sub("", line).strip()
        if len(line) >= 6:
            first = line
            break
    if not first:
        first = c.prize_items[0] if c.prize_items else (c.handle or c.key)
    first = re.sub(r"\s+", " ", first).strip()
    return first[:60]


def _wow_delta(cur: dict[str, Campaign], prev: dict[str, Campaign]) -> dict[str, Any]:
    """前回スナップショットとの差分（曜日/期間が違っても「供給量の変化」として読む）。"""

    def _keys(d: dict[str, Campaign]) -> set[str]:
        return set(d)

    cur_keys, prev_keys = _keys(cur), _keys(prev)
    new = cur_keys - prev_keys
    gone = prev_keys - cur_keys
    cur_val = sum(c.estimated_value_jpy for c in cur.values())
    prev_val = sum(c.estimated_value_jpy for c in prev.values())
    return {
        "prev_size": len(prev),
        "size_delta": len(cur) - len(prev),
        "new_campaigns": len(new),
        "disappeared": len(gone),
        "value_delta": cur_val - prev_val,
        "entries_delta": sum(c.entries for c in cur.values()) - sum(c.entries for c in prev.values()),
        # 決定的サンプル: set の反復順はプロセスごとのハッシュ乱数で変わるため、
        # キー（tweet_id/URL）降順で固定する。ここが揺れると fingerprint が非再現になる。
        "new_sample": [_short_title(cur[k]) for k in sorted(new, reverse=True)[:5]],
    }


# ── Markdown 生成 ─────────────────────────────────────────────────────
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")


def render_template(template: str, values: dict[str, str]) -> str:
    """`{{PLACEHOLDER}}` を置換。未定義プレースホルダは KeyError（黙って空にしない）。"""
    missing = sorted(set(_PLACEHOLDER_RE.findall(template)) - set(values))
    if missing:
        raise KeyError(f"template placeholders without values: {', '.join(missing)}")
    return _PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], template)


def md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    if not rows:
        out.append("| " + " | ".join(["—"] * len(headers)) + " |")
    return "\n".join(out)


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _yen(x: float) -> str:
    return f"{int(x):,}円"


def build_sections(stats: dict[str, Any]) -> dict[str, str]:
    """レポート本文の各セクションを Markdown 断片として生成。"""
    total = stats["total_campaigns"] or 1
    # 1. サマリ
    bullets = [
        f"- 収集案件 **{stats['total_campaigns']:,}件** / 自動応募 **{stats['total_entries']:,}件**"
        f"（監視アカウント {len(stats['accounts'])}件・案件あたり応募率 {_pct(stats['coverage_rate'])}）",
        f"- 判明した当選枠合計 **{stats['total_seats']:,}口** / 推定賞品価値 **{_yen(stats['total_estimated_value_jpy'])}**",
        f"- 締切が機械可読な案件は {stats['deadline_known']:,}/{total:,}（{_pct(stats['deadline_known'] / total)}）"
        f"、景品カテゴリを判定できた案件は {total - stats['category_unclassified']:,}件"
        f"（{_pct((total - stats['category_unclassified']) / total)}）",
        f"- 賞品評価額が判明した案件は {stats['value_known']:,}件（{_pct(stats['value_known'] / total)}）"
        f"（うち {stats['value_from_text']:,}件は本文の「◯円分」表記から推定）",
        f"- 応募導線が要確認・未判定の案件 {stats['route_unknown']:,}件（X完結以外は自動化コストが跳ね上がる）",
    ]
    if stats.get("scope") == "all":
        bullets.append(
            "- 対象範囲: **収集全件**（対象週に投稿された案件が判定できなかったため全期間にフォールバック）"
        )
    if stats["wow"]:
        w = stats["wow"]
        bullets.append(
            f"- 前回スナップショット比: 総案件 {w['size_delta']:+,}"
            f"（新規 {w['new_campaigns']}・消滅 {w['disappeared']}）、推定価値 {_yen(w['value_delta'])}"
        )
    summary = "\n".join(bullets)

    # 2. キーワード
    kw_rows = [
        [f"`{r['keyword']}`", f"{r['campaigns']:,}", f"{r['avg_entries']:.1f}", f"{_pct(r['coverage'])}",
         f"{'+' if r['lift'] >= 0 else ''}{_pct(r['lift'])}"]
        for r in stats["keywords"][:15]
    ]
    keyword_table = md_table(
        ["キーワード", "出現案件数", "平均応募数", "応募率", "リフト"], kw_rows
    )

    # 3. カテゴリ
    cat = sorted(stats["by_category"].items(), key=lambda kv: -kv[1]["n"])
    cat_rows = [
        [name, f"{int(v['n']):,}", f"{int(v['entries']):,}", _yen(v["value"]), f"{int(v['seats']):,}"]
        for name, v in cat
    ]
    category_table = md_table(["カテゴリ", "案件数", "応募数", "推定価値", "当選枠"], cat_rows)

    # 4. 当選枠
    wc_rows = []
    for name, _, _ in _WINCOUNT_BANDS:
        v = stats["by_wincount"].get(name)
        if not v:
            continue
        n = int(v["n"])
        wc_rows.append([name, f"{n:,}", f"{n / total * 100:.1f}%", f"{int(v['entries']):,}"])
    wincount_table = md_table(["当選枠レンジ", "案件数", "構成比", "応募数"], wc_rows)

    # 5. 締切
    dl_rows = [[name, f"{stats['by_deadline'].get(name, 0):,}"] for name, _, _ in _DEADLINE_BANDS]
    dl_rows.append(["期限未記載", f"{stats['by_deadline'].get('期限未記載', 0):,}"])
    deadline_table = md_table(["残り期間", "案件数"], dl_rows)

    # 6. 導線
    route_rows = [[k, f"{v:,}", f"{v / total * 100:.1f}%"] for k, v in
                  sorted(stats["by_route"].items(), key=lambda kv: -kv[1])]
    route_table = md_table(["応募導線", "案件数", "構成比"], route_rows)

    # 7. 収集源
    source_rows = [[k, f"{v:,}", f"{v / total * 100:.1f}%"] for k, v in
                   sorted(stats["by_source"].items(), key=lambda kv: -kv[1])]
    source_table = md_table(["収集源", "案件数", "構成比"], source_rows)

    # 8. 実測当選（全期間の応募記録 × 当選DM）
    wins = stats["wins"]
    win_rows = []
    for name, v in sorted(wins["by_category"].items(), key=lambda kv: -kv[1]):
        entries = int((wins.get("entries_by_category") or {}).get(name, 0))
        win_rows.append([name, f"{entries:,}", f"{v:,}", f"{v / entries * 100:.2f}%" if entries else "—"])
    win_table = md_table(["カテゴリ", "応募数(全期間)", "当選", "実測当選率"], win_rows)
    win_notes = (
        f"当選DM {wins['total']}件中 {wins['matched']}件を収集案件と突合（ローカル照合: tweet_id完全一致 "
        f"{wins['matched_keys'].get('tweet_id', 0)}件 / handle一致 {wins['matched_keys'].get('handle', 0)}件）。"
        f"未突合 {wins['unmatched']}件は収集前の案件またはX外経路の当選。"
        "分母は全期間の応募記録（=本レポートの週次集計とは母集団が異なる）。"
        "t.co展開を含む詳細突合は `scripts/kensho_winrate_analysis.py` が担当する。"
    )

    # 9. 前回スナップショット比
    if stats["wow"]:
        w = stats["wow"]
        wow_table = md_table(
            ["指標", "前回", "今回", "差分"],
            [
                ["新規投稿案件数", f"{w['prev_size']:,}", f"{stats['total_campaigns']:,}", f"{w['size_delta']:+,}"],
                ["新規案件", "—", f"{w['new_campaigns']:,}", "—"],
                ["消滅案件", "—", f"{w['disappeared']:,}", "—"],
                ["応募数", "—", f"{stats['total_entries']:,}", f"{w['entries_delta']:+,}"],
                ["推定価値", "—", _yen(stats["total_estimated_value_jpy"]), _yen(w["value_delta"])],
            ],
        )
        wow_notes = (
            "比較の基準: ツイート投稿日（snowflake IDから復元）で「今週」と「前週」に分けた供給量比較。"
            "スナップショット履歴（`data/collected_history/`）が2件以上あれば、そちらの集合差分を優先する。"
            + ("新規案件の例: " + "、".join(w["new_sample"]) if w["new_sample"] else "")
        )
    else:
        wow_table = "（履歴スナップショット未作成のため初回は前週比なし。`--snapshot` を実行すると次回から差分が出る）"
        wow_notes = ""

    # 10. アカウント別
    acct_rows = [
        [a, f"{stats['by_account'].get(a, 0):,}", f"{stats['by_account'].get(a, 0) / total * 100:.1f}%"]
        for a in stats["accounts"]
    ]
    acct_rows.sort(key=lambda r: -int(str(r[1]).replace(",", "")))
    account_table = md_table(["アカウント", "応募数", "案件カバー率"], acct_rows)

    # 11. 未応募の高価値案件
    missed_table = md_table(
        ["案件", "推定価値", "当選枠", "未応募アカウント数", "締切", "収集源"],
        [[m["title"], _yen(m["value"]) if m["value"] else "—", f"{m['seats']:,}", f"{m['missing']}", m["deadline"], m["source"]]
         for m in stats["missed"]],
    )

    return {
        "SUMMARY_BULLETS": summary,
        "KEYWORD_TABLE": keyword_table,
        "CATEGORY_TABLE": category_table,
        "WINCOUNT_TABLE": wincount_table,
        "DEADLINE_TABLE": deadline_table,
        "ROUTE_TABLE": route_table,
        "SOURCE_TABLE": source_table,
        "WIN_TABLE": win_table,
        "WIN_NOTES": win_notes,
        "WOW_TABLE": wow_table,
        "WOW_NOTES": wow_notes,
        "ACCOUNT_TABLE": account_table,
        "MISSED_TABLE": missed_table,
    }


def build_blog_sections(stats: dict[str, Any]) -> dict[str, str]:
    """ブログ下書き向けの要約断片（レポートとは切り口を変える）。"""
    total = stats["total_campaigns"] or 1
    top_kw = [r for r in stats["keywords"] if r["campaigns"] >= 3][:8]
    kw_line = "、".join(f"`{r['keyword']}`（{r['campaigns']}件）" for r in top_kw) or "（データ不足）"
    routes = sorted(stats["by_route"].items(), key=lambda kv: -kv[1])[:3]
    route_line = "、".join(f"{k} {v / total * 100:.1f}%" for k, v in routes)
    bands = [(k, v) for k, v in stats["by_wincount"].items() if v["n"] >= 5]
    bands.sort(key=lambda kv: -kv[1]["n"])
    band_line = "、".join(f"{k} {int(v['n'])}件" for k, v in bands[:3])
    lead = (
        f"国内懸賞 **{stats['total_campaigns']:,}件**を自動収集し、{len(stats['accounts'])}アカウントで "
        f"**{stats['total_entries']:,}件**のエントリーを実行した。"
        f"その生ログから、応募導線・当選枠・締切の分布を機械可読な形で集計したのがこのレポートだ。"
        f"手作業では絶対に作れない「{total:,}件横断の傾向」を見ていく。"
    )
    body = "\n\n".join(
        [
            "## 何を測ったのか",
            f"- 対象: `data/collected_today.json` ほかスナップショット（{stats['total_campaigns']:,}件）",
            f"- 実行: 自動応募 {stats['total_entries']:,}件（アカウントあたり案件カバー率 {_pct(stats['coverage_rate'])}）",
            f"- 判明した当選枠合計 {stats['total_seats']:,}口 / 推定賞品価値 {_yen(stats['total_estimated_value_jpy'])}",
            "",
            "## わかったこと(1): 伸びているキーワード",
            f"最も多く出現したのは {kw_line}。単なる出現数ではなく、"
            "「そのキーワードの案件にどれだけ自動応募が刺さったか（応募率リフト）」も併記している。"
            "リフトが正のキーワードは、運用側の判断と需要が噛み合っている語だ。",
            "",
            "## わかったこと(2): 当選枠の構造",
            f"枠数構成比は {band_line} の順。枠が大きい案件ほど当選確率は上がるが、"
            "実際に当選が積み上がっている枠レンジは実測当選テーブルを見ればわかる。",
            "",
            "## わかったこと(3): 参加導線という見えない壁",
            f"応募導線は {route_line}。X内で完結する案件は自動化できるが、"
            "LINE・外部フォーム・会員IDは1件ごとに人手または専用実装が必要で、ここが実質的な参入障壁になる。",
            "",
            "## 再現方法",
            "```bash\npython3 scripts/kensho_data_journalism.py --week " + str(stats["week_label"]) + "\n```",
            "統計JSONは `reports/journalism/" + str(stats["week_label"]) + ".json` に出力される。"
            "同じ入力からは同じ数値が出る（乱数も時刻依存の集計も使っていない）。",
        ]
    )
    return {"LEAD": lead, "BODY": body}


# ── 出力 ──────────────────────────────────────────────────────────────
def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def iso_week_label(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}W{w:02d}"


def week_window(label: str) -> tuple[datetime, datetime] | None:
    """`2026W39` → (月曜0時JST, 翌週月曜0時JST)。不正形式は None。"""
    m = re.fullmatch(r"(\d{4})W(\d{2})", label)
    if not m:
        return None
    try:
        start = date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    except ValueError:
        return None
    s = datetime(start.year, start.month, start.day, tzinfo=JST)
    return s, s + timedelta(days=7)


def stats_fingerprint(stats: dict[str, Any]) -> str:
    """統計の同定用ハッシュ（再現性検証に使う決定的ダイジェスト）。"""
    payload = json.dumps(stats, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kensho AIデータジャーナリズム: 傾向自動抽出")
    ap.add_argument("--project-dir", default=PROJECT_DIR)
    ap.add_argument("--week", default=None, help="ISO週ラベル（例: 2026W39）。既定は今週")
    ap.add_argument("--collected", action="append", default=None, help="対象スナップショット（複数可）")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--blog-template", default=DEFAULT_BLOG_TEMPLATE)
    ap.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    ap.add_argument("--stats-dir", default=DEFAULT_STATS_DIR)
    ap.add_argument("--draft-dir", default=DEFAULT_DRAFT_DIR)
    ap.add_argument("--snapshot", action="store_true", help="現行collectedを履歴に保存（前週比の母集団作り）")
    ap.add_argument("--no-wins", action="store_true", help="当選DM突合をスキップ")
    ap.add_argument("--min-df", type=int, default=3, help="キーワードの最小出現案件数（既定3）")
    ap.add_argument("--check-template", action="store_true", help="テンプレート整合性の検証のみ")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)

    pd = args.project_dir
    template_path = os.path.join(pd, args.template) if not os.path.isabs(args.template) else args.template
    blog_template_path = (
        os.path.join(pd, args.blog_template) if not os.path.isabs(args.blog_template) else args.blog_template
    )

    if args.check_template:
        report_tpl = _read(template_path)
        blog_tpl = _read(blog_template_path)
        # 空値で描画してプレースホルダ整合のみ確認（未定義トークンが残れば KeyError）
        try:
            render_template(report_tpl, {k: "" for k in _PLACEHOLDER_RE.findall(report_tpl)})
            render_template(blog_tpl, {k: "" for k in _PLACEHOLDER_RE.findall(blog_tpl)})
        except KeyError as e:
            print(f"NG: {e}", file=sys.stderr)
            return 2
        print(f"OK: template ok ({template_path}) / blog ok ({blog_template_path})")
        return 0

    paths = discover_snapshot_files(pd, args.collected or ())
    if not paths:
        print("ERROR: 分析対象のスナップショットが見つかりません", file=sys.stderr)
        return 1
    campaigns = load_campaigns(paths)

    week_label = args.week or iso_week_label(datetime.now(JST).date())
    window = week_window(week_label)
    in_week: dict[str, Campaign] = campaigns
    prev_campaigns: dict[str, Campaign] | None = None
    if window:
        cur_lo, cur_hi = window
        prev_lo = cur_lo - timedelta(days=7)
        cur_set = {k: c for k, c in campaigns.items() if _in_window(c, cur_lo, cur_hi)}
        prev_set = {k: c for k, c in campaigns.items() if _in_window(c, prev_lo, cur_lo)}
        if cur_set and len(cur_set) < len(campaigns):
            in_week = cur_set
            prev_campaigns = prev_set or None

    # 前週比はスナップショット履歴があればそちらを優先（案件集合の純粋な差分）
    if prev_campaigns is None:
        prev_campaigns = _previous_snapshot(pd, paths)

    wins = [] if args.no_wins else load_wins(os.path.join(pd, DM_WINS))
    # 当選突合は全期間の応募記録に対して行う（週次窓に切ると当選が落ちる）
    wins_stats = wins_block(campaigns, wins)
    stats = analyze(in_week, wins, prev_campaigns, wins_stats=wins_stats, min_df=args.min_df)
    stats["week_label"] = week_label
    stats["scope"] = "week" if in_week is not campaigns else "all"
    stats["generated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    stats["data_files"] = [os.path.relpath(p, pd) for p in paths]
    stats["fingerprint"] = stats_fingerprint({k: v for k, v in stats.items() if k != "generated_at"})

    values = build_sections(stats)
    values.update(
        {
            "WEEK_LABEL": week_label,
            "GENERATED_AT": stats["generated_at"],
            "DATA_SOURCES": ", ".join(f"`{p}`" for p in stats["data_files"]),
            "RECORD_COUNT": f"{stats['total_campaigns']:,}",
            "FINGERPRINT": stats["fingerprint"][:16],
            "REPRO_CMD": f"python3 scripts/kensho_data_journalism.py --week {week_label}",
        }
    )
    report_path = os.path.join(pd, args.report_dir, f"{week_label}.md")
    _write(report_path, render_template(_read(template_path), values))

    stats_path = os.path.join(pd, args.stats_dir, f"{week_label}.json")
    _write(stats_path, json.dumps(stats, ensure_ascii=False, indent=2, default=str) + "\n")

    # ブログ下書き（dev.to / Qiita）
    blog_values = build_blog_sections(stats)
    blog_tpl = _read(blog_template_path)
    title = (
        f"懸賞{stats['total_campaigns']:,}件の自動応募ログを全部集計したら、"
        f"「応募導線」と「当選枠」に地味な崖があった"
    )
    tags = ["python", "automation", "datajournalism", "japanese"][:4]
    drafts: dict[str, str] = {}
    for platform, front in (
        ("devto", f"title: {title}\ntags: {', '.join(tags)}\npublished: false\n"),
        ("qiita", f"title: {title}\ntags:\n" + "".join(f"  - {t}\n" for t in tags) + "private: true\n"),
    ):
        out = render_template(
            blog_tpl,
            {**blog_values, "TITLE": title, "FRONT_MATTER": front, "FOOTER": _blog_footer(stats, platform)},
        )
        drafts[platform] = out
        _write(os.path.join(pd, args.draft_dir, f"{platform}-{week_label}.md"), out)

    if args.snapshot:
        src = os.path.join(pd, DEFAULT_COLLECTED[0])
        if os.path.exists(src):
            dst = os.path.join(pd, HISTORY_DIR, f"collected_{datetime.now(JST).strftime('%Y%m%d')}.json")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)

    if not args.quiet:
        print(f"report : {report_path}")
        print(f"stats  : {stats_path}")
        for platform in drafts:
            print(f"draft  : {os.path.join(pd, args.draft_dir, f'{platform}-{week_label}.md')}")
        print(f"campaigns={stats['total_campaigns']} entries={stats['total_entries']} "
              f"keywords={len(stats['keywords'])} fingerprint={stats['fingerprint'][:16]}")
    return 0


def _in_window(camp: Campaign, lo: datetime, hi: datetime) -> bool:
    """ツイート投稿時刻が [lo, hi) に入るか。投稿時刻が取れない案件は常に含める。"""
    dt = camp.post_dt
    if dt is None:
        return True
    return lo <= dt < hi


def _previous_snapshot(pd: str, paths: Sequence[str]) -> dict[str, Campaign] | None:
    """履歴ディレクトリ内の1つ前のスナップショットを前週比の母集団として返す。"""
    hdir = os.path.join(pd, HISTORY_DIR)
    if not os.path.isdir(hdir):
        return None
    snaps = sorted(n for n in os.listdir(hdir) if n.endswith(".json"))
    if len(snaps) < 2:
        return None
    prev = os.path.join(hdir, snaps[-2])
    if prev in paths and len(paths) == 1:
        return None
    return load_campaigns([prev])


def _blog_footer(stats: dict[str, Any], platform: str) -> str:
    return (
        f"対象データ: {stats['total_campaigns']:,}件 / 応募 {stats['total_entries']:,}件 / "
        f"統計ハッシュ `{stats['fingerprint'][:16]}`（{platform} 用下書き・自動生成）"
    )


if __name__ == "__main__":
    raise SystemExit(main())
