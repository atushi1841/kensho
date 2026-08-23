# Kensho 応募効率改善 実装プラン

作成: 2026-08-08 | 状態: 承認待ち（Aider実行は承認ダイアログでブロックされた）

## 背景（実データによる分析結果）

- 収集947件中 78% (735件) が本文に t.co 等のURLを含む → skip_url_posts で全滅している
- like 実績 3/250 → 本文「いいね」厳格条件が原因
- 収集時 Step4 で `_re` 未定義クラッシュ → 収集サイクルの応募が丸ごとスキップされる（8/2に25回、8/8に1回）
- 複数垢の同一ツイート応募間隔に最速18分のケースあり

## 承認してもらえれば、以下のコマンドをそのまま実行して完了する

cd /mnt/d/Project2/kensho && aider --model deepseek/deepseek-v4-flash --architect --editor-model deepseek/deepseek-v4-flash -m 'Kenshoの応募効率改善のため以下の4つの変更を実装してください。

【変更1: collector.py のバグ修正】
kensho/scraping/collector.py の Step4 (Tweet Text Fetch) で `_re` が UnboundLocalError になるバグを修正する。
- 現在: 160行目付近の関数内で `import re as _re` しているが、331行目と365行目の Step4 コードからは `_re` が参照できず "cannot access local variable _re" でクラッシュする
- 修正: ファイル冒頭の import 群に `import re` を追加し、331行目 `_tweet_id = _re.search(...)` と 365行目 `_m = _re.search(...)` を `re.search(...)` に変更する。160行目の関数内 `import re as _re` は不要なら削除または re に統一する

【変更2: URLフィルタの精緻化】
kensho/application/applier.py の URLフィルター処理を変更する。
- 現在 (skip_url_posts=true時): 本文に http/https URL が1つでもあれば全て "URL含む投稿はNG" でスキップする → 実案件の78%が弾かれている
- 変更後: URLがあっても t.co / x.com / twitter.com リンクは許容し、外部フォームURL（forms.gle / docs.google.com/forms / docs.google.com/spreadsheets / typeform / wsform / formrun など明らかな応募フォーム）のみスキップする
- 実装例: フォームURL判定用の正規表現パターンを関数内で定義し、マッチした場合のみ SKIP する
- config.yaml の skip_url_posts: true は維持（意味が「外部フォームURLのみ除外」に変わる）

【変更3: いいね条件の緩和とconfig化】
kensho/application/applier.py の条件付きいいね判定を変更する。
- 現在: `_like_in_text = "いいね" in body_text` のみ → 実質0件
- 変更後: config.yaml に `like_keywords: ["いいね", "リアクション", "ハート", "❤", "♥", "♡"]` のような設定を追加し、applier.py は cfg から読んで「本文がどれか1つでも含む場合にいいね実行可能」とする
- 確率スキップ (skip_chance_like 30%) は維持する
- config.yaml の rate_limits セクション内に like_keywords を追加

【変更4: 同一ツイートへの複数垢応募の最低間隔ガード】
kensho/application/applier.py の _should_process_item() を拡張し、別アカウントが最近応募したツイートへの応募を抑制する。
- 現在: item["applied"][account_key] が None なら処理対象
- 変更後: item["applied"] に他のアカウントのタイムスタンプがあり、それが config の `min_cross_account_gap_minutes`（デフォルト30分）以内の場合、このアカウントではまだ処理しない（False を返す）。config.yaml の orchestrator セクションに min_cross_account_gap_minutes: 30 を追加
- DEFER ではなく単純に「まだ処理しない」→ 次サイクルで再判定される挙動にする
- 注意: タイムスタンプは ISO形式文字列 (例: 2026-08-02T12:35:40.969487) なので datetime.fromisoformat でパースして比較する。DEFER: プレフィックス付きの値はスキップする

ファイル: kensho/scraping/collector.py kensho/application/applier.py config.yaml
実装後は python3 -m py_compile で構文チェックまで行うこと。' --yes --no-auto-commits --no-dirty --no-suggest-shell-commands --cache-prompts

## 修正1: collector.py の _re バグ（クラッシュ→応募スキップの根絶）

- 場所: kensho/scraping/collector.py
- 現状: 160行目付近の関数内で `import re as _re`（ローカル）、331行目 `_tweet_id = _re.search(...)` と 365行目 `_m = _re.search(...)` で参照不能 → UnboundLocalError
- 修正: ファイル冒頭の import 群に `import re` を追加し、331/365行目を `re.search(...)` に統一。160行目のローカル import は削除

## 修正2: URLフィルタ精緻化（t.co許容、フォームURLのみ除外）

- 場所: kensho/application/applier.py（URLフィルター処理）
- 現状: `if re.search(r"https?://", body_text): SKIP` → 78%の案件が弾かれる
- 修正: t.co / x.com / twitter.com リンクは許容。forms.gle / docs.google.com/forms / docs.google.com/spreadsheets / typeform / wsform / formrun 等の外部フォームURLのみ SKIP
- config.yaml の skip_url_posts: true は維持（意味が「外部フォームURLのみ除外」に変わる）

## 修正3: いいね条件緩和 + config化

- 場所: kensho/application/applier.py（条件付きいいね判定）+ config.yaml
- 現状: `_like_in_text = "いいね" in body_text` のみ → 実質0件
- 修正: config.yaml の rate_limits に `like_keywords: ["いいね", "リアクション", "ハート", "❤", "♥", "♡"]` を追加し、applier は cfg から読んで「いずれか1つ含む場合にいいね実行可能」とする
- 確率スキップ (skip_chance_like 30%) は維持

## 修正4: 同一ツイート複数垢応募の最低間隔ガード

- 場所: kensho/application/applier.py の _should_process_item()
- 現状: 自分の applied が None なら即処理対象
- 修正: item["applied"] に他垢のタイムスタンプがあり、config の `min_cross_account_gap_minutes`（デフォルト30分）以内なら False を返す
- config.yaml の orchestrator セクションに `min_cross_account_gap_minutes: 30` を追加
- ISO形式タイムスタンプを datetime.fromisoformat で比較、DEFER: プレフィックスは無視

## 検証

- python3 -m py_compile kensho/scraping/collector.py kensho/application/applier.py
- dry_run で応募対象の変化を確認（aider 完了後）
