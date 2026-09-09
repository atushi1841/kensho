# 評価レポート: Show HN: PixelDraw – simple drawing software for web(WASM) and desktop（t_77395222）

- Task: t_77395222
- 対象: HN https://news.ycombinator.com/item?id=49587721（score 2, コメント 0）
- ライブデモ: https://akshy.codeberg.page/pixeldraw/ / ソース: https://codeberg.org/akshy/pixeldraw
- カテゴリ（Hunter）: アプリ/ツール（pixel 描画ツール）
- 実装工数推定: 適用外（実装すべき収益商品が存在しない）
- 判断: **却下（実装対象外）**

## 対象の実態（サイト・Codeberg API・HN API で実測）
PixelDraw は Rust+WASM で書かれた、クライアントサイド完結のピクセル描画ツール。
- ライブデモ（akshy.codeberg.page/pixeldraw）は単一の HTML + `.wasm` + `.js` のみ。`/robots.txt` 検証、RSS/API/ダウンロード可能DS は存在しない。サーバー側処理・バックエンドなし。
- MIT ライセンスの無料OSS。配布経路は Snap Store / Codeberg Releases / `cargo install`。
- Codeberg API 実測: stars 3 / forks 0 / watchers 1。HN score 2・コメント 0 = 観客規模はほぼゼロ。

## 3点評価
### 1) プロトタイプ
不成立。描画ツールにはスクレイピング対象データ・公開RSS/API・ダウンロード可能DS が一切ない（生成するのはユーザー自身の画像で、サーバー非蓄積）。Kensho の Python scraping + LLM 要約資産を再利用する余地が皆無。データ商品やスクレイピング商品に構成できない。

### 2) ローンチ手順
不成立。配置経路（データAPI / 自動化 / 自前FastAPI / Apify/RapidAPI）に載せる対象がゼロ。競合（無料のピクセル描画ツールは多数）が飽和しており、収益化余地なし。

### 3) 集客
不成立。Kensho が再現・販売できる観客資産・データ資産なし。原 HN スコア 2 でスキルの卻下閾値（score<20）を大きく下回る。

## 卻下理由（スキル判定例と一致）
- スキルの卻下パターン「大企業/一般的な OSS ソフトウェア（Apache/MIT 等で無料配布）: 収集データ・有料化余地なし → 卻下」に該当。
- 無料 MIT 描画ツールで、収集データ・API・サーバー・有料化余地が全て無く、既卻下の Engrim / Dsnitch / Blunderbase と同一カテゴリ・同一結論。
- 24h 以内の プロトタイプ / ローンチ / 集客 の3点を worker 実装へ切り出すべき商品ではない。

## Verification evidence

対象がクライアントサイド完結の無料OSS描画ツールであることを、ライブデモ HTML・robots.txt・Codeberg API・HN API の実コマンド出力で検証した。

```sh
$ curl -s https://hacker-news.firebaseio.com/v0/item/49587721.json
{"by":"yhska","descendants":0,"id":49587721,"score":2,"title":"Show HN: PixelDraw – simple drawing software for web(WASM) and desktop",
 "type":"story","url":"https://akshy.codeberg.page/pixeldraw/"}
（descendants=0 → コメント0件, score=2）
```

```sh
$ wc -c pixeldraw.html && grep -oiE 'modulepreload|_bg.wasm' pixeldraw.html
1097 pixeldraw.html
modulepreload
..._bg.wasm
（ページは HTML+WASM+JS のみ。サーバー側ロジック無し）
```

```sh
$ curl -s https://codeberg.org/api/v1/repos/akshy/pixeldraw
"stars_count":3 "forks_count":0 "watchers_count":1
（無料OSS, 観客規模ほぼゼロ）
```

```sh
$ curl -sL https://codeberg.org/akshy/pixeldraw/raw/branch/main/README.md | grep -iE 'License|MIT'
This software is distributed under The MIT License (MIT).
```
