# Daily Improvement 2026-09-06（revenue-qa: RapidAPI PRIVATE→PUBLIC 公開検証＋AA#1 PPE $0.005 ドル化独立検証）

## QA#1: 主役5アクター PPE $0.005 ドル化の独立検証（t_b759341c・QA再実測・19:xx JST）— 全項目 PASS

- 検証対象: W1（t_81aed78a）が実施した主役5アクターの PPE $0.005 化＋タイトルSEO最終確認。QAが独立に再実測して W1 の verification_evidence と突合。

### 1. 価格snapshot 5行全件 $0.005 & PAY_PER_EVENT（PASS）
`python3 scripts/apify_ppe_price.py snapshot whSePszWpMtfeLYBp F8Hl0a8Cx9bpJBrxR q2E37PVTg5JcGOTEn 8WBam4CPB72q9Rvsd wxMskoiHMPeeH2qAJ` 実測:
- mercari(whSePszWpMtfeLYBp): isPublic=true numEntries=2 PAY_PER_EVENT margin=0.2 datasetItemUsd=0.005
- surugaya(F8Hl0a8Cx9bpJBrxR): isPublic=true numEntries=5 PAY_PER_EVENT margin=0.2 datasetItemUsd=0.005
- mandarake(q2E37PVTg5JcGOTEn): isPublic=true numEntries=8 PAY_PER_EVENT margin=0.2 datasetItemUsd=0.005
- yahoo(8WBam4CPB72q9Rvsd): isPublic=true numEntries=2 PAY_PER_EVENT margin=0.2 datasetItemUsd=0.005
- tackleberry(wxMskoiHMPeeH2qAJ): isPublic=true numEntries=3 PAY_PER_EVENT margin=0.2 datasetItemUsd=0.005
→ 全5行 datasetItemUsd=0.005・pricingModel=PAY_PER_EVENT。W1のsnapshot出力と numEntries/margin/isPublic 完全一致。

### 2. offmall(Zh4kqcS4dYPWpFzBd) pricingInfos非増殖（PASS・9/12 A/B汚染なし）
`raw` 実測: numEntries=3（[0]0.002@8/10, [1]0.005@9/4 15:55Z, [2]0.005@9/4 17:50Z）。
最新エントリの createdAt は 2026-09-04 で、W1着手（9/6 19:05 JST）より前。W1期間中に新規エントリ追記なし ⇒ エントリ数3のまま増殖していない。A/B判定対象（offmall）の汚染なし。

### 3. 対照群 watch(hoqt6EVaVcniMXWbK) が $0.002 のまま（PASS）
`raw` 実測: numEntries=1 datasetItemUsd=0.002（createdAt 8/11）。値上げされていない。

### 4. W1 verification_evidence と実測一致（PASS）
W1の検証証跡①snapshot 5行・②タイトル5本の文字数が、自らの再実測と数値まで完全一致（後述5も同数値）。不一致なし。

### 5. 全5本 title<=63字（PASS・独立再実測）
GET /v2/acts/{id} で title 長を再実測（W1のtitle_check.pyと同値）:
- mercari 45 'Japan Mercari Prices — Listings & Market Data'
- surugaya 47 'Japan Suruga-ya Prices — Listings & Market Data'
- mandarake 62 'Mandarake Auction Japan Scraper - Used Collectibles Prices API'
- yahoo 52 'Japan Yahoo Auctions Prices — Listings & Market Data'
- tackleberry 58 'Tackleberry Japan Scraper - Used Fishing Tackle Prices API'
→ 5本とも <=63字。キーワード入り。

### テスト・申し送り
- 機能変更なし（QAは検証と記録のみ）。
- BOT検出回避に関わる潜在シグナル: なし（Apify API 操作は収集/X応募パイプライン外）。
- 判定: 成功指標（5行$0.005 / offmall非増殖 / watch$0.002維持 / タイトル5本<=63字 / W1証跡一致）を全充足 ⇒ kensho-sweeps に報告・完了。



## RapidAPI PRIVATE 3本の公開検証（t_5981edc6・QA担当・09:2x JST）— 全項目 PASS

- 検証対象: t_0e8d78ab が commit 6c87a65 で実施した PRIVATE→PUBLIC 公開。
  対象3本（japan-offmall-cn / japan-used-car / japan-camera）+ `scripts/rapidapi_publish_apis.py` + テスト4件。

### 1. visibility 遷移確認 — 3/3 PUBLIC（PASS）
- `bash scripts/rapidapi_list_apis.py` 実測（09:2x）:
  - japan-offmall-cn（api_3697e05e）vis=PUBLIC ✓
  - japan-used-car（api_e093340e）vis=PUBLIC ✓
  - japan-camera（api_7d2dcc27）vis=PUBLIC ✓
- publish_result.json 記録と整合: offmall-cn=PRIVATE→PUBLIC、used-car=null→PUBLIC、camera=既に公開でスキップ。

### 2. 公開URL HTTP 200 — 6/6（PASS）
| URL | 結果 |
|-----|------|
| /api/japan-offmall-cn（タスク正文短縮URL） | 200 |
| /api/japan-used-car | 200 |
| /api/japan-camera | 200 |
| /api/japan-offmall-used-goods-price-stats-api-chinese（正規slug） | 200 |
| /api/japan-used-car-price-stats-api1 | 200 |
| /api/japan-camera-lens-resale-price-research-api | 200 |

### 3. 有料プラン稼働確認 — PASS
- `python3 scripts/rapidapi_paid_effect.py --dry-run`（読み取りのみ・state非破壊）実測:
  - 対象3本とも **paid_plan_active=true**
  - 有効単価 3本とも一致: BASIC $0.001 / PRO $0.005 / ULTRA $0.01
  - subscriber baseline: total=0 / paid=0 / free=0（公開前後で保持）

### 4. バックアップ整合・既存subscriber保持
- 既存FREE subscriber: 対象3本とも consumer tier subscriber=0 で推移（オーファン化なし）。※各API共通の「無料オーファン版に既存購読者1人」警告は公開対象外japan-kakakuにも存在する既存状態で、公開操作起因ではない。
- **所見（軽微なデータ衛生ギャップ）**: `data/rapidapi_publish/visibility_backup.json` および `publish_plan.json` の state_before は **タイムスタンプ09:18（公開09:10の後）** で、全3本が既にPUBLIC表示。真の公開前状態は `publish_result.json`（09:10・visibility_before=PRIVATE/null）が保持。バックアップとしての完全性は publish_result で担保済みだが、visibility_backup の「before」ラベルは実質 after であり将来の再現証跡として誤解を招く。次回は公開前スナップショットを mutation 前に書き残すこと。

### テスト・申し送り
- `pytest tests/test_rapidapi_publish_apis.py` → **4 passed**。
- 新規コードの実装なし（QAは検証と記録のみ）。
- 申し送り: BOT検出回避に関わるテスト失敗なし。収集/応募パイプラインへの影響なし。
- 判定: 成功指標（全URL HTTP 200 / visibility 3/3 PUBLIC / paid_effect baseline 取得成功）を全て充足 ⇒ kensho-sweeps（メイン）に報告・完了。


## QA#2: README デプロイ（5本ソース read-back + build 状態）独立検証（t_5754c741・QA再実測・19:5x JST）— 全項目 PASS

- 検証対象: W2（t_d0893584）が実施した公開5主役アクターの README 英語化（800-1500語）＋デプロイ。QAが独立に再実測して W2 の evidence と突合。

### 1. `python3 scripts/apify_readme_deploy.py --audit`（PASS）
- 出力: 「--- gaps (<800 chars) needed deploy: 0 / 63」。対象5本すべて `ok`。
  - mercari readme=6515 / surugaya readme=5553 / mandarake readme=5877 / yahoo readme=5882 / tackleberry readme=5821（chars）

### 2. README 語数（word count、英単語 >=800）独立実測（PASS）
`/tmp/qa2_verify.py`（API read-back + 英単語カウント）:
- mercari: 986 words（ge_800=true）→ W2証跡と完全一致
- surugaya: 843 words（ge_800=true）→ 一致
- mandarake: 902 words（ge_800=true）→ 一致
- yahoo: 897 words（ge_800=true）→ 一致
- tackleberry: 864 words（ge_800=true）→ 一致
→ 全5本 English word count 800-1500 範囲内。W2報告値（986/843/902/897/864）と数値まで完全一致。

### 3. 最新 build が SUCCEEDED（PASS、build ID まで W2 証跡一致）
`GET /v2/acts/{id}/builds?desc=1&limit=1` 独立実測:
| actor | latest build | status | W2証跡IDと一致 |
|-------|--------------|--------|----------------|
| mercari whSePszWpMtfeLYBp | 0.0.14 H8ILV0w3vKTKNezs2 | SUCCEEDED | MATCH |
| surugaya F8Hl0a8Cx9bpJBrxR | 0.3.3 f45jlFCGxEHTZN0cJ | SUCCEEDED | MATCH |
| mandarake q2E37PVTg5JcGOTEn | 0.2.9 0v4ebrgVSJPQWJP8b | SUCCEEDED | MATCH |
| yahoo 8WBam4CPB72q9Rvsd | 0.0.3 jmtlTAUhK3iteSY5a | SUCCEEDED | MATCH |
| tackleberry wxMskoiHMPeeH2qAJ | 0.1.7 SKcw4Dv07gyStgi33 | SUCCEEDED | MATCH |
→ 全5本 SUCCEEDED、build ID は W2 verification_evidence と完全一致。

### 4. inputSchema・動作コード未変更（READMEのみ変更）確認（PASS）
- mercari/mandarake/tackleberry（GIT_REPO）: GitHub commit 調査。W2 のデプロイコミットは 4e754714/74a318ab・f22013f8・b6366ab4 で、変更ファイルは **README.md のみ**（`.actor/INPUT_SCHEMA.json`・src/ コード不変）。inputSchema 存在確認。
- surugaya（SOURCE_FILES v0.3）: sourceFiles = `['INPUT_SCHEMA.json','main.py','README.md']` でコード保持。
- yahoo（SOURCE_FILES v0.0）: sourceFiles = `['README.md']` のみ。ただしこれは **W2着手前（9/5 の 0.0.1/0.0.2 build 時点）から既に README のみ**であり、W2 の 0.0.3 build は README 内容の更新に留まる（コードに変更を加えていない）。⇒ W2変更は README のみで成立。

### 5. W2 verification_evidence と実測一致（PASS）
W2報告の語数・build ID・read-back 3点セット（ソースREADME存在 + build成功 + commit確認）が自らの再実測と完全一致。不一致ゼロ ⇒ task4 の「request-changes で差し戻し」条件に該当せず。

### テスト・申し送り
- 変更なし（QAは検証と記録のみ）。
- **申し送り（W2起因ではない・事前からの既知状態）**: yahoo（8WBam4CPB72q9Rvsd）の latestタグ版 v0.0 は SOURCE_FILES で `README.md` のみ（main.py なし）。実コード本体は GitHub リポジトリ atushi1841/yahoo-auctions-japan-scraper と v0.1（GIT_REPO・tag なし）にある。v0.0 は README 公開用並行版で、buildTag=latest が v0.0 にあるため defaultRunOptions.build=latest 実行時にコードレスで動く可能性がある点は次回要確認（今回の README デプロイ検証スコープ外。既存状態であり W2 の回帰ではない）。
- BOT検出回避に関わるシグナル: なし（Apify API 操作であり収集/X応募パイプライン外）。
- 判定: 成功指標（5本語数>=800 / build全SUCCEEDED / build ID一致 / READMEのみ変更 / W2証跡一致）全充足 ⇒ kensho-sweeps（メイン）に報告・完了。
