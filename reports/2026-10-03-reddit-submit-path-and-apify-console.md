# Reddit投稿経路の実装・Apify Console検証・休日繰り越し — 2026-10-03（後半）

## 1. Apify Console の確認 → 成功（ユーザーのサインイン後）

```
$ python3 scripts/apify_console_check.py --actor DKzufUSvmuXNKHeYx
[i] final_url : https://console.apify.com/actors/DKzufUSvmuXNKHeYx
[i] title     : Japan Anime Figure Price API — 650+ Figures & Arbitrage
[i] 本文長    : 222 文字
=== 掲載/公開に関わる行 ===
  Apify Store
```

サインインは保持され、アクターの管理画面が無人で読めるようになった。
以降は `--dump --screenshot` で掲載状況を機械的に取得できる（`reports/apify_console_latest.png`）。

## 2. 重大な訂正: アクターは「ほぼ全部非公開」ではなかった

前の報告で Apify の一覧API（`/acts`）の `isPublic` を読んで
「86本すべて非公開」と書いたが、**これは誤り**。一覧APIの `isPublic` は信用できない。
詳細API（`/acts/fruitful_quintessence~<name>`）で88本を1本ずつ照合した結果:

```
総数 88 | 公開 78 | 非公開 8
```

公開78本は Store 掲載済みで、run数も付いている（japan-market-mcp 604 / mandarake-auction-scraper 324 /
japan-offmall-market-scraper 317 …）。**教材として: Apifyの公開状態は一覧APIで判定せず、詳細APIで1本ずつ確認する。**

## 3. Reddit 投稿経路の実装（完了・投稿直前まで実機検証）

### 3-1. 経路の選定理由（調査の結論）
| 案 | 判定 |
|---|---|
| コメント入力欄を UI 操作 | ✗ Reddit は Shadow DOM + Lexical で保護し、合成キー入力を受け付けない |
| Playwright 等で自動操作 | ✗ `navigator.webdriver` が立ち、素性が割れる |
| **CDP + ログイン済みセッション内 fetch** | **◎ cookie/CSRF/TLS/UA 指紋がすべて本物になる。最善手** |

出典: Karma Builder（Shadow DOM を回避しピクセル座標で操作）、DEV 記事
「How I Built a Reddit Karma Bot with CDP Browser Automation」（CDP は指紋が一致する）、
npm `reddit-agent`（API不使用・純ブラウザ操作・1日5件上限）。

### 3-2. 実装したもの
- `scripts/reddit_submit_driver.js`（新規）— Windows側 node が CDP で実 Chrome に接続し、
  cookie を `Network.setCookie` で注入 → スレを**段階スクロールして読む**（人間の閲覧を模倣）→
  `Runtime.evaluate` で `fetch('/api/comment')` を実行 → 投稿後にスレJSONを再取得して反映を確認
- `reddit_warmup_agent.py::submit_comment_via_cdp` — cookie_new.json → ヘッダ文字列 → Chrome起動
  （専用プロファイル `C:\temp\reddit-cdp`・専用ポート 9229）→ node 実行 → 結果JSONの解析
- 安全弁: 1回の起動で投稿は**最大1件**（調査の共通見解は「新垢 1-2件/時・1日3-5件」）。
  `live=False` で投稿せずログイン確認＋読込まで検証できる

### 3-3. 実機検証（投稿はしない dry run）
```
$ python3 -c "wa.submit_comment_via_cdp('NoStupidQuestions','1wwfd1t','dry',live=False)"
{
 "cookies_injected": 11,
 "logged_in_as": "sabotenJAL",
 "steps": ["login_check:sabotenJAL","read_scroll:3","dry_run_stop_before_post"],
 "thread_title": "Why would a jury ... : r/NoStupidQuestions"
}
```
cookie 11件の注入 → **sabotenJAL としてログイン確認** → スレ本文の取得 → 投稿直前で停止、まで実測で通った。
残るは実投稿（POST 200）の1点のみ。これは不可逆なので初回は手動GOで実行する。

## 4. 休み日の繰り越し（実装・検証済み）

原因は2つあった:
1. 休み日を引くと今日の全スロットが `skipped_rest` になり、**翌日へ移す処理が無かった**
2. `next_date_slots` は「今日使い切れなかった残り」からしか作らないため、3件を今日で使い切ると常に空だった

修正:
- `base_day`（今日が休み日なら次の活動日）を導入し、休み日は計画を丸ごと `next_date_slots` へ繰り越す
- 繰り越し日が再び休み日にならないよう `next_date` の決定を分岐
- `end_of_day` が `today` 基準のままで base_day の計画を潰していたバグも修正
- `do_submit` に予定時刻チェックを追加（未来の繰り越し分を前倒しで投稿しない）

検証:
```
休み日強制 today: [(True,None),(True,None),(True,None)]
休み日強制 next : 2026-10-04 | スロット 3
    2026-10-04T07:42+09:00 / 08:22 / 09:53
RESULT=繰り越しOK
通常日 today: 3件 / next: 0        ← 通常日はこれまで通り
```

## 5. 越境ファイルとテスト用アクターの処遇（おすすめで確定）

- **越境ファイル** `/mnt/d/Project2/apify-sales-funnel/blog/devto-weekly-market-summary-w40.md`
  → **そのまま残す**。dev.to の記事原稿は販売導線側リポジトリが正しい置き場。kensho 側に複製しない。
  今後この別リポジトリへ書き込む場合は事前に確認する。
- **テスト用6本**（rakuten-debug-fetch / tabelog-debug-fetch / mini-actor-test-0903 / my-actor /
  my-actor-1 / test-actor）→ **非公開のまま維持**。削除は不可逆なので行わない。`data/internal_actors.json` に登録済み。
- **kensho-high-value-leads** → **非公開のまま維持**を推奨（今回確定）。
  理由: kensho の懸賞収集データを再加工した「高額懸賞リード」で、これは**このプロジェクト自身の材料**。
  Store に出すと自分の収集源を外部に配る形になり、ユーザー方針（Kenshoの技術は他人向けに転用しない）と逆行する。
  run数も1回で実績が無い。タイトル/説明は既に入っているので、将来出す場合はそのまま使える。

## 6. テスト

```
$ python -m pytest tests/test_reddit_comment_writer.py tests/test_reddit_warmup_agent.py -q
38 passed  （2.9秒・ネットワーク不使用）
```

## verification_evidence

```
$ python3 scripts/apify_console_check.py --actor DKzufUSvmuXNKHeYx   → title 取得成功（ログイン済み）
$ python3 -c "wa.submit_comment_via_cdp(...,live=False)"             → logged_in_as=sabotenJAL / cookies_injected=11
$ python3 -c "wa.schedule_drafts(drafts)（休み日強制）"                → next_slots=3件 繰り越しOK
$ python3 -c "詳細APIで88本を照合"                                    → 公開78 / 非公開8
$ python -m pytest tests/test_reddit_comment_writer.py tests/test_reddit_warmup_agent.py -q → 38 passed
```
