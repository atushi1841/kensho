# 手動実装記録 — 2026-08-26 01:30（ユーザー指示による緊急実装）

## 実施サマリー

Critic提案（2026-08-26版）の提案1〜3を**ユーザー指示により手動実装**（worker自動サイクル外）。
「危険度高もOK」の方針変更に伴い、nightly-workerプロンプトも更新済み（高リスク実装可）。

## 実装した変更

| # | コミット | 内容 |
|---|---------|------|
| 1 | 973efcb | セッション内重複アクション防止（RT済みtweet_id set + フォロー済み主催者set）<br>collectorでtweet_id保存 + _dedup_x_url_mergeでバックフィル<br>actions_apply.pyのdo_follow/do_rt/do_likeにtarget引数（監査n/a解消）<br>UIフォールバック(do_follow)でもFollowStateManager.record_follow |
| 2 | 009948d | extract_tweet_id_and_screen_nameがscreen_nameなしURL(x.com/status/, i/web/status/)で誤抽出する問題を修正 |
| 3 | a713729 | バックアップファイル(bak_)をgit管理から除外 |

テスト: **148 passed, 4 skipped**（+6テスト追加）
mypy: 変更行に新規エラーなし（既存エラーのみ）

## 実装の詳細

### 提案1: RT再試行ループ防止（973efcb）
- セッション内RT済みtweet_id set（rt_done_ids）— 同一ツイートへの重複RTを防止
  - 実測: chugakujukenが同一ツイート2075388882238275638にRT試行11回（22:19-22:45 JST）
- 応募成立判定に_rt_already_doneフラグ追加（RT不要でも成立扱い = 重複エントリでの応募機会喪失を防ぐ）
- **重要な設計変更**: RT重複チェックはキュー追加前（if not skip_rt: の外）に移動。ブロック内チェックだと fallback_rt が実行されてしまう

### 提案2: collector tweet_id保存（973efcb）
- knshow収集アイテムにtweet_idフィールド追加
- _dedup_x_url_mergeで全アイテムにtweet_idバックフィル（新規・既存問わず）
- actions_apply.pyのdo_follow/do_rt/do_likeにtarget引数追加（デフォルト"n/a"で後方互換）
  - これまでUIフォールバックの監査targetが常に"n/a"（実測: 直近500件中115件）→ 実値に
- 既存data/collected.jsonに手動バックフィル適用済み: tweet_id 1027件全件付与、/i/web/status/ 193件はx_url復元（screen_name誤抽出のため正規化はしない）

### 提案3: フォロー済み主催者set（973efcb）
- セッション内フォロー済み主催者set（followed_owners_session）— 同一主催者への2回目フォローをスキップ
- **根本原因発見**: UIフォールバック（x_api_ok=False時）のdo_followはrecord_followを呼んでいなかった
  - → FollowStateManagerの日次2回/通算4回上限が機能せず、同一主催者へ8回フォロー（critic実測）
  - → do_follow成功時もrecord_followするよう修正

## 追加対応: extract_tweet_id_and_screen_name誤抽出（009948d）

- `https://x.com/status/123` 形式でscreen_name="x.com"、`x.com/i/web/status/123` 形式でscreen_name="web"と誤抽出し、フォローAPIが誤爆する問題
- 該当形式ではscreen_name=Noneを返すようガード追加

## 次サイクル向けメモ

- 提案1〜3は実装済み → criticは「実装済み確認」に切り替えること
- 残存: 提案4（atushi16バッチ10件化）は5391cedで対応済み、提案5（TankanNotes 1085 / inobase1-4 1089）はスマホ側物理確認待ち（ユーザー判断）
- 次サイクルの検証ポイント:
  - RT成功率の改善（31%→50%目標）
  - audit.jsonlのtarget=n/a消滅（tweet_id実値化）
  - 過フォロー・多重アクションシグナルの消滅
