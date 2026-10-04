# Reddit導線 Phase 1 手順書（実測ベース） — 2026-10-03

対象カード: t_bef61602 [新垢] Reddit新アカウント+週1価値提供投稿パイプライン
作成: kensho-sweeps（実測 = reddit-gate-check.sh + Reddit API 直叩き）

## 0. 結論（先に読む）

Phase 1「新垢作成＋cookie配置」は **すでに完了している**。
止まっているのは Phase 1 ではなく、**Phase 3（=Karma を 150 まで育てる作業）** で、これはユーザーの手作業（1日10分・3週間）が必須。

さらに、既存の自動レポートにある「G5 は 10/07 に自動で PASS する」は **誤り**。
G5 の条件は `total_karma >= 150` **AND** `age_days >= 30` の AND 条件であり、age が 10/07 に通っても karma が 1 のままでは永久に FAIL する。

## 1. 現状の実測（2026-10-03 10:54 JST）

```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/reddit-gate-check.sh
PASS G0: cookie ok (11 entries, reddit_session=True csrf=True)
PASS G1: date ok (today=2026-10-03 >= resume_from=2026-09-28)
FAIL G2: no go.flag - user must enable phone tethering then run: touch .../go.flag
PASS G3: queue ok (OK DataSets 184)
PASS G4: identity ok (u/sabotenJAL == expected u/sabotenJAL)
FAIL G5: account too young (sabotenJAL age_days=26 < 30)
PASS G6: submitter present
GATES: FAIL (2 gate(s) blocked) -> DO NOT POST

$ # Reddit API 実測（cookie_new.json で認証）
me:    sabotenJAL  link_karma=1  comment_karma=0
about: total_karma=1  created_utc=1788732234 (2026-09-07 07:03 JST)  age_days=26
```

要約:
- 垢 u/sabotenJAL は 2026-09-07 作成済み＝**新垢作成は完了**
- cookie_new.json は 2026-09-07 取得・11エントリ・有効（G0/G4 PASS）
- 投稿本文も準備済み（data/reddit/post_queue.json = r/DataSets 184文字タイトル）
- 残る FAIL は G2（人のフラグ）と G5（karma/age）

## 2. ゲート一覧と解除条件

| ゲート | 条件 | 現在 | 解除の方法 |
|---|---|---|---|
| G0 cookie | cookie_new.json に reddit_session | PASS | 失効時のみ再取得 |
| G1 date | today >= resume_from | PASS | - |
| G2 tethering | data/reddit/go.flag が存在し mtime 24h以内 | FAIL | テザリングON → `touch` |
| G3 queue | post_queue.json が有効 | PASS | - |
| G4 identity | 認証垢 == expected_account.txt | PASS | - |
| G5 karma/age | **karma>=150 かつ age>=30** | FAIL | Karma を 150 まで育成（手動） |
| G6 submitter | cdp_submit_v2.js 存在 | PASS | - |

## 3. ユーザーがやること（所要 1日10分 × 約3週）

### 3-1. Karma 形成（G5 の唯一の解除手段）

自動化してはいけない作業（低Karma垢のコメント連投は BOT 判定の最速トリガー。旧垢 Significant-House109 が 9/6 に垢級403を受けた構造そのもの）。
目標: comment karma 150 以上（post karma は不要。comment のほうが速く安全）。

進め方:
1. 1日10分、コメント **3〜5件**（5件を超えない）
2. 1セッション内で連続投稿しない。1件ごとに **30分以上** 空ける
3. 狙うのは「投稿から1〜3時間・コメントがまだ5件以下の rising スレ」
4. 内容は自分の言葉で。事実（自分のデータ・経験）を1つ入れる。リンクは貼らない
5. 写真・スクショの添付は有効（AI slop 判定を避ける最良の手段）

候補 sub（topic は不問。karma は垢全体に転移する）:
- r/NoStupidQuestions, r/AskReddit（流量が多く rising が絶え間ない）
- r/NewToReddit（karma 形成の作法そのものが話題）
- r/japan, r/japanlife, r/JapanFinance（日本データ人設と整合）
- r/DataIsBeautiful, r/datasets（本命 r/DataSets の手前。ここで実績を作る）

AIに毎朝出させる補助（任意）: 上記subの rising から「回答しやすいスレ候補3件＋論点メモ」を用意させる。**下書きはAIに書かせない**（貼るだけの運用は検出リスクが跳ね上がる）。

### 3-2. go.flag（G2）

投稿実行の直前にだけ作る。24時間で失効する設計。
```
# スマホのテザリングをONにし、PCがその回線に繋がっている状態で
touch /mnt/d/Project2/kensho/data/reddit/go.flag
```
作成IP（自宅WiFi 9/07）と投稿IP（テザリング）を分けるための仕組み。

### 3-3. 投稿（週1・Karma達成後）

1. テザリングON → `touch data/reddit/go.flag`
2. gate check が全PASSすることを確認
3. AIが CDP + cookie で投稿実行（data/reddit/cdp_submit_v2.js, DRY_RUN不要）
4. 投稿後 shadowban チェック（ログアウト状態で profile が404でないこと）

## 4. カード再開の手順（AI側）

G5 が PASS した時点で:
```
hermes kanban assign t_bef61602 kensho-revenue-worker
hermes kanban promote t_bef61602     # scheduled → ready
```
`assignee` が空のままでは dispatcher が spawn しない（現在 assignee=None のため、条件が揃っても永久に動かない）。

## 5. 選択肢

- (A) 推奨: sabotenJAL を上記 3-1 で育てる。3週間後（11月上旬）に投稿解禁
- (B) 垢を捨てて作り直す: ただし新垢も同じく Karma 0 から始まるため、3週間は短縮されない。作り直す理由がない
- (C) Reddit 導線を畳む: Gumroad 告知は Reddit 以外（devto 等）に寄せる。t_bef61602 は archive

## 6. 誤りの訂正（後続ワーカー向け）

- reports/revenue-proposals/2026-10-03-revenue-worker-reddit-gate-recheck-7.md の
  「G5 は 10/07 05:03 JST に自動PASS」は誤り。G5 は karma と age の AND 条件。
- 同レポートの「Phase 1 ユーザー手動待ち」も不正確。Phase 1（垢作成+cookie）は 9/07 に完了済み。
- gate check の再実行は「Karma達成後」または「cookie失効検知時」まで不要。毎時の再確認は空回り。

## verification_evidence

```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/reddit-gate-check.sh
FAIL G2: no go.flag / FAIL G5: account too young (sabotenJAL age_days=26 < 30)
$ python3 -c "import json,urllib.request; ... /user/sabotenJAL/about.json"
about: total_karma 1 comment 0 link 1 created_utc 1788732234 age_days 26
$ ls -l /mnt/d/Project2/kensho/data/reddit/cookie_new.json
-rwxrwxrwx 1 atushi atushi 6355 Sep  7 07:37 cookie_new.json
```
