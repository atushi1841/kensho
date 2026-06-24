# application/ — X(Twitter)応募モジュール

## 概要
Playwright Firefox を使ってXの懸賞に自動応募（いいね・RT・フォロー・リプライ）。

## 構成
| ファイル | 役割 |
|----------|------|
| `browser.py` | Firefox起動・指紋偽装・Xログイン確認 |
| `applier.py` | 応募ロジック（Like/RT/Follow/Reply） |
| `session_manager.py` | Xセッション（auth_token/ct0）管理 |

## 重要ルール（BOT検出回避）

### 人間らしい振る舞い
- アクション間隔は **12〜40秒のランダム**（固定間隔禁止）
- 1セッション **最大15件**
- 同一ツイートへの連続アクション禁止（いいね＋リプライ同時NG）
- リプライはテンプレート直貼り禁止、投稿に合わせた自然な内容に

### 指紋偽装（`browser.py`）
- アカウントごとに **WebGL / Canvas / Fonts** を偽装
- UAは5種類ローテーション
- Firefoxプロファイルはアカウント別（`firefox_profile_<key>/`）

### アカウント運用
- 稼働時間: **09:00〜23:59**（深夜は絶対停止）
- 日次上限: フォロー120 / RT80 / いいね200 / リプライ10
- 4アカウント構成（IP分離: ForceBindIP）
- 各アカウント: atushi16 / kudou_aoshi / atushi1840 / zin20120731

### 排他制御
- `collected.lock` で排他ロック（30秒タイムアウト）
- 多重起動防止: PIDロックファイル

## 修正時の注意
- `applier.py` 内で `_is_active_hours()` を変更するときは全アカウントの稼働時間帯に注意
- リプライテンプレートは `_generate_reply()` — コンテキストに合った返信のみ
- Firefoxのバージョンが変わるとfingerprint生成が変わることがある
