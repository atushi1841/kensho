"""pathway_classifier — 収集時にX懸賞の「応募導線」を判別し非X案件を分離するモジュール。

背景 (2026-09-20, t_f7b0d3bd):
- 応募導線は X上(フォロー/RT/いいね) だけとは限らず、X連携・LINE・Instagram・
  専用アプリ・レシート・会員ID登録・外部フォーム・DM・メールなどへ多様化している。
  X投稿URLだけでは応募条件を自動判定できない案件が増えた。
- これら非X導線を自動操作すると TOS/個人情報流出リスクが高いため、収集時に導線を
  分類ラベル(導入)として付与し、非X案件は '手動・要確認' レポートへ割り出す。
  自動応募対象には非X案件を混入させない。

設計方針:
- ラベル値:
    X        — X上で完結（フォロー/リポスト/いいねで応募できる）→ 自動応募対象
    LINE     — LINE友だち追加・LINE応募
    Instagram— Instagramでの応募
    アプリ    — 専用アプリでの応募
    レシート  — レシート・購入履歴での応募
    会員ID    — 会員登録・会員IDが必要
    外部フォーム — 外部サイト/url/フォームへの入力
    DM       — DM(メッセージ)で応募
    メール    — メールで応募
    要確認    — 本文はあるが導線が判別できない（【要ユーザー対応】）
    未判定    — tweet_text 無し（取得不能）→ 自動応募対象外・要確認扱い
- 自動応募対象 = ラベルが X のもののみ。それ以外（X連携含む非X全種）は除外。
- 判別順序: ①必須の非X導線 ②X導線 ③不明→要確認。
  非Xキーワードが単なる言及（例「Instagramで当選率UP」「当選者へDMで連絡」）のときは
  X導線がある限り X と見なす（過剰排除を防ぐ）。
- fail-safe追記: 誤ってX案件を非X判定しても流通は減るだけ（安全側）。
  誤って非X案件をX判定すると自動応募に混入（危険側）のため、X判定は
  「フォロー + (リポスト/いいね)」という明示的なX導線がある場合に限定する。
"""

from __future__ import annotations

import math
import re
from typing import Any

from kensho.scraping.scorer import EASY_WIN_SCORE_KEY

# 自動応募対象になるラベル（X導線）
X_LABEL: str = "X"

# ── 当選易度 TOP50 表示（t_c1889d30）──
# easy_win_score（収集時に scorer.compute_easy_win_score で付与）の高得点順 TOP50 を
# デイリーレポートに表示する。計算不能（winner_count 欠落・0）は score=0 で付与した上で
# TOP50 から分離して別セクションに切り出す。表示・可視化のみで応募ロジックには未反映。
EASY_WIN_TOP_N: int = 50

# 自動応募対象外の非Xラベル集合
NON_X_LABELS: frozenset[str] = frozenset(
    {
        "LINE",
        "Instagram",
        "アプリ",
        "レシート",
        "会員ID",
        "外部フォーム",
        "DM",
        "メール",
        "要確認",
        "未判定",
    }
)


def is_auto_applyable(label: str | None) -> bool:
    """この導入ラベルの案件を自動応募対象に含めてよいか。

    安全優先: X のみ自動応募可。ラベル無し(古いデータ)は自動応募対象から除外し、
    必ず再収集でラベル付与してから判断する（非X案件の混入を絶対に防ぐ）。
    """
    return label == X_LABEL


# ── 非X導線の必須パターン（優先判定） ──
# 注: CSS順で上にあるものほど優先。Instagram「当選率UP」等は言及なので含めない。
_NON_X_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # LINE: 友だち追加・LINE応募
    (
        "LINE",
        re.compile(
            r"(?:line|ライン)"
            r"(?:\s*(?:友だち|友達)\s*(?:追加|登録)|"
            r"(?:@|＠)|"
            r"(?:公式)|"
            r"(?:で|から|にて|より)\s*(?:ご応募|応募|参加|エントリー|予約))|"
            r"(?:友だち追加|友達追加|公式line|line@)"
        ),
    ),
    # Instagram: Instagramが応募手段
    (
        "Instagram",
        re.compile(
            r"(?:instagram|インスタグラム|\bインスタ\b)"
            r"(?:\s*(?:で|から|にて)\s*(?:応募|ご応募|参加|エントリー|フォローを)\s*"
            r"(?:してください|下さい)?|"
            r"\s*(?:で|から)\s*(?:応募|参加)|"
            r"(?:のアカウントをフォローして応募)|"
            r"(?:応募はinstagram|応募はインスタ)|"
            r"(?:instagram(?:で|から)応募))"
        ),
    ),
    # 専用アプリ
    (
        "アプリ",
        re.compile(
            r"(?:専用アプリ|公式アプリ|アプリ内|アプリから|アプリで|アプリを利用)"
            r".{0,12}(?:応募|参加|エントリー|予約|購入|登録)"
        ),
    ),
    # レシート・購入
    ("レシート", re.compile(r"レシート|購入履歴.{0,6}応募")),
    # 会員ID・会員登録
    (
        "会員ID",
        re.compile(
            r"会員ID|会員登録|会員限定|会員にな|メンバー登録|無料会員|会員(?:申込|入会)|ID登録"
        ),
    ),
    # 外部フォーム・外部サイト入力
    (
        "外部フォーム",
        re.compile(
            r"応募フォーム|応募ページ|応募ボタン|こちらから(?:ご)?応募|"
            r"(?:下記|以下の?)(?:フォーム|url|リンク|サイト|ページ).{0,8}(?:から|へ)?応募|"
            r"(?:url|リンク|サイト|ページ).{0,6}から(?:ご)?応募|"
            r"入力して(?:ご)?応募|フォームから(?:ご)?応募|"
            r"応募する(?:ボタン|欄)|申込フォーム"
        ),
    ),
    # DMでの応募（当選通知の「DMをお送りします」等の言及は除外＝導線ではない）
    (
        "DM",
        re.compile(
            r"dmで(?:応募|ご応募|参加|エントリー)|dmから(?:応募|参加)|"
            r"(?:応募|ご応募|参加|エントリー)はdm|dmを(?:送って|送信して)(?:ください|くださいね|下さい)?|"
            r"\bdm\b(?:で|から|にて).{0,10}(?:応募|参加)(?!の当選)|"
            r"(?:dmで|dmから)の?応募"
        ),
    ),
    # メールでの応募
    (
        "メール",
        re.compile(r"メールで(?:応募|ご応募)|(?:応募|ご応募)はメール|メールの送信で応募"),
    ),
]

# X導線（フォロー + リポスト/リツイート/R/いいね）— 改行跨ぎも許容（[\s\S]）
_X_ENTRY: re.Pattern[str] = re.compile(
    r"フォロー[\s\S]{0,40}(?:リポスト|リツイート|(?:\W|^)rt\b|いいね)|"
    r"[\s\S]{0,40}(?:リポスト|リツイート|(?:\W|^)rt\b|いいね)フォロー|"
    r"フォロー(?:&|＆)(?:rt|リポスト|いいね)|"
    r"フォロー後[\s\S]{0,10}(?:リポスト|リツイート|いいね)"
)
_X_CONTEXT: re.Pattern[str] = re.compile(r"応募|参加|キャンペーン|プレゼント|抽選|エントリー")


def classify_pathway(text: str) -> str:
    """tweet_text から応募導線ラベルを返す。"""
    if not text or not str(text).strip():
        return "未判定"
    t: str = str(text).lower()
    # ① 必須の非X導線（最優先）
    for label, pat in _NON_X_PATTERNS:
        if pat.search(t):
            return label
    # ② X導線（フォロー+リポスト/いいね）が明示されていれば X
    if _X_ENTRY.search(t):
        return X_LABEL
    # ③ フォロー/リポスト/RT/いいね というX内操作が応募コンテキストと共にあれば X 扱い
    #    （過剰排除防止。非Xパターンで未検出のものに限る＝危険側混入は生じない）。
    #    改行を跨ぐ投稿（フォロー\n②本投稿をRT 等）も網羅するため \s で連結判定する。
    if re.search(r"フォロー|リポスト|リツイート|(?:^|\s)rt\b|\srt\b|いいね", t) and _X_CONTEXT.search(t):
        return X_LABEL
    # ④ 判別不能 → 要確認（【要ユーザー対応】）
    return "要確認"


# collected アイテムに導入ラベルを持つフィールド名。
# 検証コマンド(タスク本文)は '導線' キーを読むため、このキー名で統一する。
PATHWAY_KEY: str = "導線"

# 本文未取得を表すラベル。"未判定" は確定値ではなく「未取得」の意味なので、
# tweet_text が後から入った時点で再判定する（他のラベルは確定値として保持）。
UNCLASSIFIED_LABEL: str = "未判定"


def assign_pathway(item: dict[str, Any]) -> str:
    """collected アイテムに導入ラベルを付与して返す。

    既存ラベルは保持するが、"未判定" だけは再判定する。
    理由 (2026-10-07 実測): 収集時点では tweet_text が未取得のため全件が
    "未判定" で確定し、その後 tweet_text が付与されても再判定されず、
    applier 側で全件が自動応募対象外になっていた（応募枯渇の真因）。
    "未判定" は「未取得」の意味なので、本文が手に入った時点で分類し直す。
    """
    existing = item.get(PATHWAY_KEY)
    if existing and str(existing) != UNCLASSIFIED_LABEL:
        return str(existing)
    label: str = classify_pathway((item.get("tweet_text") or ""))
    item[PATHWAY_KEY] = label
    return label


def label_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    """collected 全体の導入ラベル別件数を集計。"""
    counts: dict[str, int] = {}
    for it in items:
        lbl = it.get(PATHWAY_KEY) or "未判定"
        counts[lbl] = counts.get(lbl, 0) + 1
    return counts


def non_x_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """導入ラベルが X 以外（自動応募対象外）の案件一覧。"""
    return [it for it in items if not is_auto_applyable(it.get(PATHWAY_KEY))]


def _label_ja(label: str) -> str:
    desc: dict[str, str] = {
        "X": "X上で完結（自動応募対象）",
        "LINE": "LINE友だち追加・LINE応募",
        "Instagram": "Instagramで応募",
        "アプリ": "専用アプリで応募",
        "レシート": "レシート・購入履歴で応募",
        "会員ID": "会員登録・会員IDが必要",
        "外部フォーム": "外部フォーム・サイト入力",
        "DM": "DMで応募",
        "メール": "メールで応募",
        "要確認": "導線判別不能（要ユーザー対応）",
        "未判定": "本文取得不能（要確認扱い）",
    }
    return desc.get(label, label)


def _winner_count_value(item: dict[str, Any]) -> float:
    """winner_count を数値化。欠落・0・不正・非有限は 0.0（=計算不能）。"""
    try:
        wc: float = float(item.get("winner_count"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return wc if math.isfinite(wc) and wc > 0 else 0.0


def easy_win_ranking(
    items: list[dict[str, Any]], n: int = EASY_WIN_TOP_N
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(easy_win_score 高得点順 TOP n, 計算不能リスト) を返す。

    計算不能 = easy_win_score 未付与 または winner_count 欠落・0・不正
    （scorer.compute_easy_win_score はこれらに score=0 を返す仕様）。
    """
    ranked: list[dict[str, Any]] = []
    uncomputable: list[dict[str, Any]] = []
    for it in items:
        score = it.get(EASY_WIN_SCORE_KEY)
        if isinstance(score, (int, float)) and not isinstance(score, bool) and _winner_count_value(it) > 0:
            ranked.append(it)
        else:
            uncomputable.append(it)
    ranked.sort(key=lambda it: float(it[EASY_WIN_SCORE_KEY]), reverse=True)
    return ranked[:n], uncomputable


def _easy_win_prize_cell(item: dict[str, Any]) -> str:
    """賞品優先度セル（prize_score 未評価は '—'。スコア上は通常値1.0=ボーナス0として扱う）。"""
    ps = item.get("prize_score")
    if isinstance(ps, dict) and isinstance(ps.get("priority"), (int, float)):
        return f"{float(ps['priority']):.1f}"
    return "—"


def easy_win_top_md(items: list[dict[str, Any]], n: int = EASY_WIN_TOP_N) -> str:
    """当選易度 TOP50 + 計算不能分離のマークダウンセクション。"""
    top, uncomputable = easy_win_ranking(items, n)
    total = len(items)
    computable_n = total - len(uncomputable)
    lines: list[str] = [
        f"## 当選易度 TOP{n}（easy_win_score 高得点順）",
        "",
        f"- 対象: 全{total}件中 計算可能 {computable_n}件（計算不能 {len(uncomputable)}件は TOP{n} 対象外）",
        "- easy_win_score = winner_count 正規化（log1p/上限1000）と prize_score.priority "
        "正規化（1.0=通常→0.0 / 3.0=満点→1.0）の等重合成 ×100（0-100）",
        "- ※ 当選易度の可視化のみ。応募バッチ配分・応募ロジックには未反映。",
        "",
        "| 順位 | easy_win_score | 当選者数 | 賞品優先度 | 締切 | 導線 | X投稿URL |",
        "|---|---|---|---|---|---|---|",
    ]
    if not top:
        lines.append("| — | — | — | — | — | — | （計算可能な案件なし） |")
    for i, it in enumerate(top, start=1):
        xu = str(it.get("x_url") or it.get("url") or "")
        dl = str(it.get("deadline") or "")
        lbl = str(it.get(PATHWAY_KEY) or "?")
        lines.append(
            f"| {i} | {float(it[EASY_WIN_SCORE_KEY]):.1f} | {int(_winner_count_value(it))} "
            f"| {_easy_win_prize_cell(it)} | {dl} | {lbl} | {xu} |"
        )
    lines += [
        "",
        f"### 計算不能（winner_count 欠落・0）: {len(uncomputable)}件",
        "",
        f"- easy_win_score = 0 として全件付与済み。表示上はここに分離し TOP{n} には含めない。",
    ]
    return "\n".join(lines)


def build_non_x_report_md(items: list[dict[str, Any]], label_counts_map: dict[str, int], today: str) -> str:
    """reports/non_x_manual_<date>.md の本文を組み立てる。"""
    nx = non_x_items(items)
    total = len(items)
    lines: list[str] = [
        f"# 非X応募導線（手動・要確認）レポート {today}",
        "",
        f"- 対象収集件数: {total}",
        f"- 非X判定（自動応募対象外）: {len(nx)}",
        f"- 導入ラベル付与率: "
        f"{len(_with_label(items)) / max(total, 1) * 100:.1f}%（100% = 全件にラベル付与）",
        "",
        "## 導入ラベル別件数",
        "",
        "| ラベル | 件数 | 内容 |",
        "|---|---|---|",
    ]
    for lbl, cnt in sorted(label_counts_map.items(), key=lambda x: -x[1]):
        lines.append(f"| {lbl} | {cnt} | {_label_ja(lbl)} |")
    # ★ t_c1889d30: 当選易度 TOP50（easy_win_score 高得点順）+ 計算不能の分離表示
    lines += ["", easy_win_top_md(items), ""]
    lines += ["## 手動・要確認リスト（自動応募対象外）", ""]
    if not nx:
        lines.append("（該当なし）")
    else:
        lines.append("| 導線 | X投稿URL | 締切 | tweet_text（一部） |")
        lines.append("|---|---|---|---|")
        for it in nx:
            lbl = it.get(PATHWAY_KEY) or "?"
            xu = it.get("x_url") or it.get("url") or ""
            dl = it.get("deadline") or ""
            tt = (it.get("tweet_text") or "").replace("|", "／").replace("\n", " ").replace("\r", "")
            lines.append(f"| {lbl} | {xu} | {dl} | {tt[:80]} |")
    lines.append("")
    lines.append("※ 非X導線は自動操作せずX手動チェック・要ユーザー対応対象。")
    return "\n".join(lines)


def _with_label(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [it for it in items if it.get(PATHWAY_KEY)]

