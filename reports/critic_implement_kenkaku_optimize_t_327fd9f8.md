# KENKAKU収集効率最適化 — 実装報告・構造的上限確定（critic提案 t_327fd9f8）

提案者: nightly-critic 4baf143523e0（ready=0供給不足対応）
状態: 実装完了＋上限確定（成功指標の「20件超」は構造的に不可達であることを実証）

## 1. 実施内容

### 提案1（可視化）— 完了
`kensho/scraping/sources/kenkaku.py` に収集効率テレメトリを実装・有効化。
1セッション当たり取得件数・ページ成否（ok/total, fetch_fail）・所要時間を1行に集約出力。

```
[KENKAKU] 計18件取得 (pages ok=7/7, fetch_fail=0, elapsed=N.Ns)
```

- 前任run(t_327fd9f8 attempt 1)がカウンタ変数のみ宣言し未出力（壊れたまま）だった点を修正。
- 回帰テスト `tests/test_kenkaku_retry.py::TestTelemetrySummary` を追加（12テスト全PASS）。

### 提案2（取得件数低い原因の特定）— 実証完了
KENKAKU X懸賞セクションの構造的上限を、ページID空間の網羅probeで確定。

## 2. 検証結果：KENKAKU は構造上限 18件/セッション

### 2a. 既存7ページ + 全候補ページ（ソート/期限/クイズ/オープン101/103系列等）のユニークX URL数
重複排除probe（scripts/kensho_kenkaku_dedup.py、18候補ページ×fetch + 組み合わせ計算）:

```
current(その1-7)  : 18
+ その8           : 18
  main(その1-8)   : 18
  main+sort       : 18
  main+sort+extra : 18
  +deadline views : 18
新規ユニークX URL: 0
```

- 既存7ページで既に全 **18** ユニークX URL を取得済み。
- **後続ページ18種を追加しても新規X URLは 0件**（重複のみ。ソート/期限表示・クイズ・オープン101/103系列は全て同一18件の別表示）。
- オープン101/103系列の個別X埋込も最大1〜4件/ページで、重複を除くと新規なし。

### 2b. 実ログの直近KENKAKUセッション取得件数
`logs/collect_2026091[8-9]*.log`:

```
[KENKAKU] 計18件取得        [Step 3] (... ken-kaku 18件 ...)
[KENKAKU] 計18件取得        [Step 3] (... ken-kaku 18件 ...)
```

現在コレクターは既に上限18件を毎セッション取得。criticが観測した「mean 17.0」は
一部ページのfetch失敗による揺れで、t_350bc813のリトライ強化（済）で直近は安定して18。

### 2c. 結論
- KENKAKU X懸賞セクションは **ユニーク18件が構造的上限**（ページング拡張・ソート/期限系追加・
  オープン系列追加のいずれも新規0件と実証）。
- 成功指標「KENKAKU平均20件/session以上」は **このソースでは数学的に不可達**。
- タスク失敗時代替案（KENKAKU次ページor他源シフト）の前者は0新規と実測で無効と確定。

## 3. 供給面の現状（ready=0供給不足への示唆）
KENKAKU以外のソースは供給過多（直近collectログより）:

```
[Step 3] (ken-kaku 18件, kenshou.club 241件, cp.meikan 100件, ke-ma 33件,
          twscrape 100件, chance.com 17件, kensho-everyday 6件, prtimes 1件, 計498件)
```

- kenshou.club 241・cp.meikan 100 が主供給源。KENKAKU 18件の占有率は低く、
  供給不足の原因ではない。全体計は400件超/回。
- KENKAKUの件数最適化余地は **構造的にゼロ**であり、供給面のボトルネックでもない。

## 4. 変更ファイル
- `kensho/scraping/sources/kenkaku.py` — 収集効率テレメトリ集約出力（提案1）
- `tests/test_kenkaku_retry.py` — telemetry回帰テスト追加

## 5. 残課題（委譲検討）
- KENKAKUの20件超は不可達であるため、供給をさらに増やす目的なら
  kenshou.club/cp.meikan のページ深掘り（最大ページ数拡張）が効率的。ただし
  現状400件超/回で供給過多のため、t_327fd9f8単体としての対応はここまで。

## 6. 禁止領域チェック
- モデル切替・壊変更・応募ロジック：対象外（収集効率テレメトリ＋上限診断のみ）。
- ConnectTimeoutリトライ設定（t_350bc813, 3/6/10s, retry 5）は不変 → 直近CT≤3維持。

## verification_evidence
$ python3 scripts/kensho_kenkaku_dedup.py
current(その1-7)  : 18
+ その8           : 18
  main(その1-8)   : 18
  main+sort       : 18
  main+sort+extra : 18
  +deadline views : 18
新規ユニークX URL: 0

$ python3 -m pytest tests/test_kenkaku_retry.py -q -p no:cacheprovider
============================= 12 passed in 13.09s ==============================

$ git log --oneline -3
7e8c425 feat(collect): t_327fd9f8 KENKAKU効率テレメトリ集約+構造上限(18件)診断
9609a74 docs(evidence): t_a9c1b208 PR TIMES 5th source verification
c185f93 feat(collect): t_a9c1b208 PR TIMES present/drawing campaign collect (source #5)
