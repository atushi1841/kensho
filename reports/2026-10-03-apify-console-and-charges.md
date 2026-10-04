# Apify Console確認の自動化・課金判断・内部アクター整理 — 2026-10-03

## 1. Apify Console の publishing 画面を読めるようにした（自動化）

これまで「APIからは打ち手がなく、Consoleを人が見るしかない」で止まっていた部分を自動化した。

### 作ったもの
- `scripts/apify_console_check.py` — WSLから呼ぶ本体
- `scripts/apify_console_driver.js` — Windows側で動くCDPドライバ（生WebSocket、puppeteer非依存）

### 仕組み
WSLからはWindowsの `127.0.0.1:9222` に到達できないため、**Chrome起動とnode実行は powershell.exe 経由**。
永続プロファイル `C:\temp\kensho-apify-cdp` を使うので、**初回だけ手動ログインすれば以降は無人で読める**。

```
$ python3 scripts/apify_console_check.py --actor DKzufUSvmuXNKHeYx --screenshot
[i] Chrome を起動します（profile=C:\temp\kensho-apify-cdp）
[i] final_url : https://console.apify.com/sign-in
[i] 本文長    : 94 文字

[!] Apify Console にログインしていません（初回のみ手動が必要）
    1. 開いている Chrome ウィンドウ（profile=C:\temp\kensho-apify-cdp）を前面に出す
    2. https://console.apify.com にサインインする
    3. このコマンドをもう一度実行する（以降は無人で読めます）
EXIT=3
[i] スクリーンショット: reports/apify_console_latest.png   ← 135,200 bytes 出力済み
```

### 残る人の作業（1回だけ）
開いているChrome（profile=`C:\temp\kensho-apify-cdp`）で Apify にサインインする。以降は無人で画面を読める。
読み取った結果は `--dump` で全文、`--screenshot` でPNG（reports/apify_console_latest.png）に出る。

## 2. 課金の要否 → **要（追加した）**

判断: PPEは維持し、**値上げはしない**（競合実測$4/1K水準で値上げ却下の既結論に従う）。
一方で、結果1件ごとの課金が無い2本には `apify-default-dataset-item` **$0.002/件** を追加して全MCPで揃えた。

| アクター | PUT | 変更前 | 変更後 | dataset-item価格 |
|---|---|---|---|---|
| japan-fuel-price-mcp (RdCHlXHphoLsWnyhh) | 200 | 1件 | 2件 | $0.002 |
| japan-minimum-wage-mcp (ODh1F4XP5sLlXu6Ep) | 200 | 1件 | 2件 | $0.002 |

外部run が0のため現時点の売上影響は0。**利用された時に取りこぼさないための整備**。
台帳: `data/apify_ppe_dataset_item_2026-10-03.json`

## 3. テスト用6本の処遇 → **非公開のまま維持・削除しない・台帳化した**

削除は不可逆なので行わない。isPublic=false のまま維持し、商品ではないものとして扱う。
台帳 `data/internal_actors.json` に登録し、SEO監査・プロモ・収益集計の対象から除外する。

rakuten-debug-fetch / tabelog-debug-fetch / mini-actor-test-0903 / my-actor / my-actor-1 / test-actor（全て run=0）

### 台帳化で見つかった別件（要判断・今回は未処置）
- **kensho-high-value-leads (SWVTsribU0AIJVXtR) は isPublic=false のまま**。テスト用ではなく実プロダクトなのに Store から見えていない
- **japan-property-hazard-mcp も非公開**（本日PPEを追加したばかり）

## 4. 消えていたレポートの復旧

`reports/qa_t_8bc59e8d_2026-10-02.md` を復旧した（5,169 bytes）。
兄弟ワーカーの確定コミットを消さないため、`git checkout -- <file>` ではなく `git show HEAD:<path> > <path>` で作業ツリーへ書き戻した（indexは触っていない）。git status の削除エントリは0になった。

## verification_evidence

```
$ python3 scripts/apify_console_check.py --actor DKzufUSvmuXNKHeYx --screenshot
final_url: https://console.apify.com/sign-in / 本文長: 94 文字 / EXIT=3
$ ls -la reports/apify_console_latest.png
-rwxrwxrwx 1 atushi atushi 135200 reports/apify_console_latest.png
$ PUT /v2/acts/RdCHlXHphoLsWnyhh {"pricingInfos":[…,+1件]} → 200 / read-back entries=2, dataset-item=$0.002
$ PUT /v2/acts/ODh1F4XP5sLlXu6Ep {"pricingInfos":[…,+1件]} → 200 / read-back entries=2, dataset-item=$0.002
$ git show HEAD:reports/qa_t_8bc59e8d_2026-10-02.md > reports/qa_t_8bc59e8d_2026-10-02.md
復旧OK: 5169 bytes / git status の D エントリ = 0
```
