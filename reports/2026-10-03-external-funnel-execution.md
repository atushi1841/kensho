# 外部導線の実行 — 2026-10-03（dev.to 完了 / X・MCP 進行中）

「出来る限り自動で全部進める」への実行記録。外部への書き込みはすべて read-back で確認した。

## 1. dev.to 内部リンク → 完了（3本、公開ページで確認済み）

`scripts/devto_internal_links.py` を新設し、公開記事5本を走査。

```
公開記事: 5本
  要追記 id=4767489 懸賞112件の自動応募ログ…        PUT 200 / read-back 反映=True
  要追記 id=4760099 懸賞7件の自動応募ログ…          PUT 200 / read-back 反映=True
  要追記 id=4760098 懸賞112件の自動応募ログ…        PUT 200 / read-back 反映=True
  既存   id=4606013 How to Scrape Mercari Japan…   （既に Store リンクあり）
  既存   id=4587593 Japanese used-goods price data…（既に Store リンクあり）
```

**発見**: 懸賞系の記事3本は Store リンクが**1本も無い**状態で放置されていた
（＝導線として存在していなかった）。`japan-prize-giveaway-scraper` への導線を追加。
Mercari / Yahoo Auctions の2本は既にリンク済みだった。

**外部検証**（無認証の公開APIで再取得）:
```
GET https://dev.to/api/articles/4767489（APIキー無し）
  → "apify.com/fruitful_quintessence" を含む = True
  → 追記部: "## Data used in this post ... available on Apify (pay-per-result, free tier to start)"
```

## 2. X プロモ → 完了（投稿＋独立検証済み）

### 修正した実害（重要）
`data/apify_store_promo_state.json` の 2026-W40 slot a に
**`tweet_id: "placeholder_2026W40a"`（テスト用の偽記録）**が入っており、
`apify_store_promo.py` はそれを「投稿済み」と判定して**週次プロモを無言でスキップし続けていた**。
実際には一度も投稿されていない。

修正: 実ID（数字のみ）以外は未投稿として扱う（class fix）。
```
[warn] 偽の投稿記録を無視します (week=2026-W40, slot=a, tweet_id='placeholder_2026W40a')
```

### 投稿結果（親が公開ページで検証）
```
permalink: https://x.com/atushi16/status/2106325444840833327
tweet_id : 2106325444840833327
時刻     : 10:08 AM · Oct 3, 2026
検証経路 : fxtwitter 経由で公開ページを取得 → 本文一致・Apifyリンクカード展開を確認
本文     : 日本オークション市場の価格モニタリング、今週も更新。
           Mandarake Auction で仕入れ判断・在庫評価を自動化。
           初期費用ゼロで開始 https://apify.com/fruitful_quintessence/mandarake-auction-scraper #まんだらけ #オークション
           📊 週次分析（無料サンプル）: https://atushi5.gumroad.com/l/kutuxe
```

### 通った経路（今後の標準にする）
既存の seleniumbase / Playwright 経路は WSL で死ぬ（下記）ため、
**Windows Chrome (port 9265, headless) → CDP WebSocket → cookie注入 → UI操作で投稿 → プロフィールで確認**
という経路を新規に実装して成功した。Reddit で確立したパターンと同じ。

```
firefox 経路失敗: waiting for locator("[data-testid=\"tweetTextarea_0\"]") to be visible （= 未ログイン）
CDP にフォールバック → 投稿失敗: No module named 'seleniumbase'
seleniumbase 導入 → 投稿失敗: uc_driver unexpectedly exited. Status code was: -5 （= SIGTRAP）
→ WSL の Linux 側 Chrome は使えない。Windows Chrome + CDP + node が唯一の正攻法
```
生成物: `C:\temp\x_post_direct.js`（投稿）, `x_post_verify_final.js`（検証）, `x_post_tweet_screenshot.png`
ローカル記録: `reports/x-post-2026-10-03.md`

## 3. MCP（Smithery 公開）→ 6本すべて完了（registry で親が検証）

子5本の報告後、**親が registry API で6本を一括検証**した結果:

```
japan-anime-figure-mcp  OK | stdio/python | figure_current_price, figure_price_history, figure_lowest_price
kensho-sweep-mcp        OK | stdio/python | current_sweep, sweep_history, top_prize_movers
tcg-price-japan         OK | stdio/python | tcg_current_price, tcg_price_history, tcg_top_movers
kensho-kaku             OK | stdio/python | current_sweep, sweep_history, top_prize_movers
kensho-kclub            OK | stdio/python | current_sweep, sweep_history, top_prize_movers
kensho-kema             OK | stdio/python | current_sweep, sweep_history, top_prize_movers
```

release_id:
| server | release_id |
|---|---|
| japan-anime-figure-mcp | 12124aee-d3f8-47f2-82cd-b42be8ea0b13 |
| kensho-sweep-mcp | 04f46272-3af4-4ace-b493-be4018c2bc40 |
| tcg-price-japan | 1a14baba-db36-4458-bec4-44dc61f13c08 |
| kensho-kaku | 6cb3e881-5c6e-48ad-a9cf-fae035126669 |
| kensho-kclub | dd52c43f-4723-4170-853c-96d627065048 |
| kensho-kema | 40fc0c6f-ab31-46d2-a2e8-a3a1833b48bc |

### 検証で気づいた点（誤解しないための記録）
1. **4本が同じツール名**だが重複ではない。データ源が別:
   kensho-sweep-mcp=自社収集(1133件/1.1MB) / kensho-kaku=ken-kaku.com /
   kensho-kclub=kenshou.club / kensho-kema=ke-ma.net(懸賞マニア)。
   同じスキーマで別ソースという設計なので、ツール名が揃うのは意図どおり。
2. **registry API はサーバー単位の description を返さない**（ツール単位の説明のみ）。
   最初「description が全部空」に見えたのは API の仕様。ツール説明は充実していて
   日本語の入力例（"Amazonギフト", "リザードン" 等）まで入っている＝検索語として有効。
   → 今後の判定でこのAPIだけを見て「説明が無い」と誤診しないこと。
3. `displayName` は API 上はスラグのまま（manifest の display_name は反映されない）。
   Smithery のフロントが別フィールドを見ている可能性がある。**未解決の小物**として残す。
4. kensho-kclub の子は bundle ダウンロードURLが404と報告したが、
   registry は `connections[0].bundleUrl`（パス形式）を返しており、公開自体は成立している。
   `npx smithery run` による実起動確認も別途取れている。

### 手順の資産化
- スキル `smithery-mcpb-publish`（既存・2026-09-13実証）がそのまま効いた。
- 1本目の生成物（src/stdio_main.py, manifest.json, scripts/sync_manifest_tools.py,
  scripts/pack_mcpb.py, .mcpbignore）が2本目以降の雛形として機能し、
  5本を**並列で**公開できた（合計約54分）。再現可能。

## 4. 残件 → 両方とも完了（2026-10-03）

### 4-A. X 週次投稿を新経路（Windows Chrome + CDP）へ切り替え  ✅

判明したこと: 週次プロモは **kensho-revenue-worker プロファイルのHermes cron**
`kensho-apify-store-promo-weekly`（`0 0 * * 1,5` = 月曜/金曜 09:00 JST）から
`kensho-apify-store-promo-weekly.sh` 経由で動いていた。そして**このラッパーが
`KENSHO_PROMO_BROWSER="${KENSHO_PROMO_BROWSER:-firefox}"` と明示的に旧経路を固定**していた。
＝ 投稿スクリプト側だけ直しても、cron は firefox（WSLで必ず失敗）を叩き続ける構造だった。

変更した4か所（全て実測で検証）:

| 層 | 変更 | 検証 |
|---|---|---|
| ラッパー `.sh` (L27) | `firefox` → `win` 既定に変更 | `bash -n` OK ／ grep で既定値確認 |
| `apify_store_promo.py post_promo()` | `auto` の順序を **win → firefox → seleniumbase** に | 構文OK ／ スタブで戻り値検証 |
| `post_with_windows_cdp()` 新設 | 本文を `C:\temp` に書き、node ドライバを実行し結果JSONを読む | ケース1 PASS: 実ID(数字のみ)を返す |
| `scripts/x_post_driver.js` | 依存なし(node内蔵WebSocket)・本文外部化・`--dry-run` | 下記 |

ドライバの dry-run 実測（投稿ボタンは押していない）:
```
Injected cookies: 15
URL: https://x.com/compose/post  title: ホーム / X
Click result: focused
Textarea chars after insert: 206      ← 本文206字が実際に入った
DRY_RUN_OK chars=206
{"status":"dry_run_ok","body_chars":206,"inserted_chars":206,"url":"https://x.com/compose/post"}
```

その過程で潰した2つのバグ（どちらも「失敗が成功に見える」型）:
1. `connectCdp()` が `url.startsWith('http')` を要求 → 起動直後の `about:blank` を
   拾えず45秒待って `CDP unavailable after Chrome launch` で死ぬ。→ `type==='page'` で拾う。
2. 挿入確認が `ta.value.length` → contenteditable では**常に0**。入っていても失敗に見える。
   → `innerText` を見る。
3. `--dry-run` が「ナビゲートまで」で止まり、**挿入の破損を検知できなかった**。
   → 本文挿入まで実行し `inserted_chars` を報告する仕様に変更。

**未検証の残り1点（正直に記載）**: 投稿ボタンのクリック以降。
子が実際に投稿した実績ツイート（2106325444840833327）と**同一のコード行**（無変更）だが、
リポジトリ版ドライバで click を通した実測はまだ無い。次回の実走は
**2026-10-05(月) 09:00 JST**。cron 出力は kensho-revenue-worker 側に出る。

### 4-B. Smithery の displayName  → **対応不要（誤診だった）**  ✅

9/13 に公開した `japan-fuel-price-mcp` も registry API では `displayName = スラグ` を返す。
＝ 新規6本だけの問題ではなく **API の仕様**。manifest の `display_name` が反映されないのは
こちらの不具合ではない（フロント側の別フィールドの可能性は残るが、APIからは追えない）。

教訓: registry API の `description`/`displayName` の見え方だけで
「説明が無い/名前が変」と判断しないこと。既存の成功例と比較すれば誤診を防げる。

## verification_evidence

```
$ python3 scripts/devto_internal_links.py --apply   → 3本 PUT 200 / read-back 反映=True
$ GET https://dev.to/api/articles/4767489（無認証）  → Storeリンク=True（公開ページに反映）
$ python3 scripts/apify_store_promo.py --slot a     → [warn] 偽の投稿記録を無視（バグ修正が効いた）
$ import seleniumbase; seleniumbase.__version__     → 4.55.0（導入済み）
$ python3 scripts/apify_store_promo.py（cdp経路）    → uc_driver exited -5（WSL制約・既知）
```
