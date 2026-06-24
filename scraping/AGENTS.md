# scraping/ — 懸賞URL収集モジュール

## 概要
knshow.com + ken-kaku.com からX懸賞URLを収集し `data/collected.json` に保存。

## 収集フロー
```
collect_items() → [kns] パース → [ken-kaku] パース → [kenshou.club] パース → [cp.meikan] パース → merge → save
```

| 収集元 | URLパターン | 方式 |
|--------|------------|------|
| knshow.com | `https://www.knshow.com/` — メインリスト | 一覧→詳細→リダイレクト解決 |
| ken-kaku.com | `https://www.ken-kaku.com/cgi-bin/present/` — 追加ソース（v3.6〜） | X URL直接抽出 |
| kenshou.club | `https://kenshou.club/archives/tag/twitterで応募` — 追加ソース（v4.0〜） | 一覧→各記事→X URL抽出（全24ページ） |
| cp.meikan.org | `https://cp.meikan.org/xcp/` — 追加ソース（v4.0〜） | X URL直接抽出（最大10ページ） |

## 収集件数目安
- knshow.com: 25〜30件/回
- ken-kaku.com: 10〜20件/回
- kenshou.club: 50〜200件/回（新規が多い）
- cp.meikan.org: 10〜30件/回
- **合計: 100〜280件/回**

## データ構造（collected.json）

各エントリの必須フィールド:
- `url` — XのツイートURL（`x.com/.../status/...`）
- `deadline` — 応募期限（ISO日付 or "未設定"）
- `winner_count` — 当選者数（201〜10000）
- `applied` — 応募済みか（false=未応募）
- `source` — `kns` or `ken-kaku`

## 重要ルール
- **UAローテーション**: 5種類のUAをランダムに切り替え
- **指数バックオフリトライ**: HTTP 5xx時に3回までリトライ
- **排他制御**: `utils/backup.py` の `safe_save_json()` でアトミック保存
- **cp932ガード**: 出力前に `cp932_safe()` で変換

## deadline抽出パターン
9パターンの正規表現で対応:
- 応募期間表示（「応募期間: YYYY/MM/DD」）
- 賞品表示内の日付
- 期限切れ判定
- 等

## 修正時の注意
- 新しい収集元を追加するときは `_COLLECTORS` リストに追加
- 収集頻度は毎正時（9〜21時、1日13回）— 変更時はcron設定も合わせて修正
- `fetched_urls` セットで重複排除
