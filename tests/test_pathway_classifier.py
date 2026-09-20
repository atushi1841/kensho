"""Tests for scraping/pathway_classifier — 応募導線分類（t_f7b0d3bd）。

応募導線ラベル（導入/導線）を tweet_text から判別し、非X案件を自動応募対象から
分離するロジックを検証する。安全優先: X 判定は明示的なX導線がある場合のみ行い、
判別不能・非Xは自動応募対象外（手動・要確認）になることを保証する。
"""
from __future__ import annotations

from kensho.scraping.pathway_classifier import (
    PATHWAY_KEY,
    X_LABEL,
    assign_pathway,
    build_non_x_report_md,
    classify_pathway,
    is_auto_applyable,
    label_counts,
    non_x_items,
)


def test_classify_follow_and_repost_is_x() -> None:
    """フォロー+リポスト（RT）の明示がある通常のX懸賞は X。"""
    text = "① @foo をフォロー ②この投稿をRT ③ #タグ で抽選に参加"
    assert classify_pathway(text) == X_LABEL


def test_classify_follow_and_rt_across_newline_is_x() -> None:
    """改行を跨ぐ フォロー→リポスト も X（X_ENTRYの [\\s\\S] 対応）。"""
    text = "① @foo をフォロー\n②本投稿をリポスト\n#プレゼント"
    assert classify_pathway(text) == X_LABEL


def test_classify_rt_only_with_context_is_x() -> None:
    """「リポストするだけ！」等、RT単独でも応募コンテキストがあれば X。"""
    text = "抽選で10名にプレゼント！応募方法：リポストするだけ！"
    assert classify_pathway(text) == X_LABEL


def test_classify_follow_only_with_context_is_x() -> None:
    """フォローだけでもキャンペーン/応募コンテキストがあれば X。"""
    text = "参加方法：このアカウントをフォローしてください。キャンペーン開催中。"
    assert classify_pathway(text) == X_LABEL


def test_classify_line_friend_add_is_non_x() -> None:
    """LINE友だち追加で応募する案件は LINE（自動応募対象外）。"""
    text = "LINE公式アカウントを友だち追加してご応募ください。"
    label = classify_pathway(text)
    assert label == "LINE"
    assert not is_auto_applyable(label)


def test_classify_instagram_entry_is_non_x() -> None:
    """Instagramで応募する案件は Instagram。"""
    text = "Instagramのアカウントをフォローして応募してください。"
    label = classify_pathway(text)
    assert label == "Instagram"
    assert not is_auto_applyable(label)


def test_classify_app_entry_is_non_x() -> None:
    """専用アプリから応募する案件は アプリ。"""
    text = "専用アプリからご応募・エントリーいただけます。"
    label = classify_pathway(text)
    assert label == "アプリ"
    assert not is_auto_applyable(label)


def test_classify_member_id_is_non_x() -> None:
    """会員登録・会員IDが必要な案件は 会員ID。"""
    text = "応募には会員登録（無料）と会員IDが必要です。"
    label = classify_pathway(text)
    assert label == "会員ID"
    assert not is_auto_applyable(label)


def test_classify_external_form_is_non_x() -> None:
    """外部フォーム入力で応募する案件は 外部フォーム。"""
    text = "下記の応募フォームからご応募ください。"
    label = classify_pathway(text)
    assert label == "外部フォーム"
    assert not is_auto_applyable(label)


def test_classify_dm_entry_is_non_x() -> None:
    """DMで応募する案件は DM。"""
    text = "応募はDMでお願いします。"
    label = classify_pathway(text)
    assert label == "DM"
    assert not is_auto_applyable(label)


def test_dm_winner_notification_is_not_dm_route() -> None:
    """当選通知の「DMをお送りします」は応募導線でないため、フォロー+RTのX案件は X のまま。"""
    text = "応募方法: ①フォロー ②本投稿をRT。当選者にはDMをお送りいたします。"
    assert classify_pathway(text) == X_LABEL


def test_classify_empty_is_unknown() -> None:
    """本文無しは 未判定（自動応募対象外・要確認扱い）。"""
    label = classify_pathway("")
    assert label == "未判定"
    assert not is_auto_applyable(label)


def test_assign_pathway_sets_key() -> None:
    item: dict[str, object] = {"tweet_text": "フォロー&RTでプレゼントに応募"}
    assign_pathway(item)
    assert item.get(PATHWAY_KEY) == X_LABEL


def test_assign_pathway_keeps_existing() -> None:
    item: dict[str, object] = {"tweet_text": "LINE友だち追加で応募", PATHWAY_KEY: "LINE"}
    assign_pathway(item)
    assert item.get(PATHWAY_KEY) == "LINE"


def test_label_counts_categorizes() -> None:
    items: list[dict[str, object]] = [
        {"tweet_text": "フォロー&RTで応募", PATHWAY_KEY: "X"},
        {"tweet_text": "LINE友だち追加", PATHWAY_KEY: "LINE"},
        {"tweet_text": "未ラベル"},
    ]
    counts = label_counts(items)
    assert counts["X"] == 1
    assert counts["LINE"] == 1
    assert counts["未判定"] == 1


def test_non_x_items_excludes_x_and_unlabeled() -> None:
    items: list[dict[str, object]] = [
        {"tweet_text": "フォロー&RT", PATHWAY_KEY: "X"},
        {"tweet_text": "LINE", PATHWAY_KEY: "LINE"},
        {"x_url": "https://x.com/foo/status/1"},  # ラベル無し → auto-apply対象外
    ]
    nx = non_x_items(items)
    # X は含まれず、LINE と ラベル無し(None) が対象外リストに入る
    labels = {it.get(PATHWAY_KEY) for it in nx}
    assert None in labels
    assert "LINE" in labels
    assert all(not is_auto_applyable(it.get(PATHWAY_KEY)) for it in nx)


def test_is_auto_applyable_only_x() -> None:
    assert is_auto_applyable("X")
    assert not is_auto_applyable("LINE")
    assert not is_auto_applyable(None)
    assert not is_auto_applyable("要確認")
    assert not is_auto_applyable("未判定")


def test_build_non_x_report_md_has_label_table() -> None:
    items: list[dict[str, object]] = [
        {"tweet_text": "フォロー&RT", PATHWAY_KEY: "X"},
        {"tweet_text": "LINE友だち追加で応募", PATHWAY_KEY: "LINE"},
    ]
    counts = label_counts(items)
    md = build_non_x_report_md(items, counts, "20260920")
    assert "導入ラベル付与率" in md
    assert "LINE" in md
    assert "手動・要確認リスト" in md
    assert "非X判定（自動応募対象外）: 1" in md
