# 新垢`u/hbomax` 30-Day Warm-Up計画書（2026-09-07）

## 前提
- **垢**: `u/hbomax`（2026-09-07 08:19 JSTにGalleria RTX3090+hr01ルーター/ワイモバイル回線で作成）
- **旧垢**: `Significant-House109`（垢級403 spam block・8/20否定的履歴→**回復不能**・運用停止）
- **IP分離**: 投稿IP=スマホWi-Fiテザリング（毎セッション・IP回転）/ X垢とは別アダプタ
- **垢数**: **1つのみ**（複数垢は「same device/network」で即リンク検出）
- **自動化境界**: **Karma形成=手動**（rapid-fire=BOTトリガー）/ **週1投稿のみCDP自動**（8/19実績）

## 30-Day Protocol（MediaFast 2026 + alexsignal + reddireach 4ソースコンセンサス）

| 週 | 日次行動 | 目標 | リンク |
|---|---|---|---|
| **Days 1-7** | **Silent Observer** | 観察+upvoteのみ（毎日10分） | ❌ |
| **Days 8-14** | **Helpful Stranger** | 毎日5-10コメント（**rising threadsに1-3時間後先乗り**・1-5番先着=最速Karma） | ❌ |
| **Days 15-21** | **Value Provider** | コメント継続+**高価値テキスト投稿1件**（r/AskReddit or r/todayilearned） | ❌ |
| **Days 22-30** | **Soft Launch** | **週1投稿**（90%価値提供/10%promo・末尾1行） | ✅ |

### 各週の具体行動

#### Days 1-7（2026-09-07〜13）: Silent Observer
- **毎日10分**: r/popular, r/AskReddit, r/explainlikeimfiveを**観察**
- **upvote**: 興味ある投稿10-20件に👍
- **コメント・投稿: 禁止**
- **目的**: 垢の「browse activity」を形成（Redditは閲覧履歴も信頼度評価に使う）

#### Days 8-14（2026-09-14〜20）: Helpful Stranger
- **毎日5-10コメント**（合計40-70件）
- **rising threadsに1-3時間後先乗り**（r/AskReddit, r/explainlikeimfive, r/todayilearned, r/Futurology）
- **コメント内容**: 価値提供（質問への実用的回答・関連経験・追加情報）
- **リンク: 禁止**
- **目標**: comment karma 50-100+（大型subのKarmaは**垢信頼として全subに転移**）

#### Days 15-21（2026-09-21〜27）: Value Provider
- **コメント継続**（毎日5件）
- **高価値テキスト投稿1件**（r/AskReddit or r/todayilearned）
  - 例: 「I analyzed 200 Japanese izakaya datasets and found 3 trends about Tokyo dinner prices」
  - **AI使用開示**: 「I built this analysis with AI」を前置き
  - **自己宣伝: 末尾1行**（「More data here: <link>」）
- **目的**: post karma獲得+「価値提供者」プロファイル形成

#### Days 22-30（2026-09-28〜10-07）: Soft Launch
- **週1投稿**（月曜10:00 CDP自動）
- **90%価値提供/10%promo**
- **末尾1行**に製品リンク（gumroad.com/apify store等）
- **Karma目標**: 150-300（大半のAutoMod閾値10-100通過）

## Red Flags（BANトリガー・絶対禁止）
1. **同一URLの複数sub短時間crosspost**（30分以内2回以上）
2. **0リンク→48時間で5リンク**（急変化）
3. **rapid-fire投稿**（1時間に3件以上）
4. **複数垢の同一device/network操作**（X垢とIP共有）
5. **flagged IPからの新垢+即リンク投稿**（自宅IPはNG）
6. **テンプレコメントの大量投稿**（コピペ検出）
7. **AI slop判定**（箇条書き天国+数字羅列+末尾プロモ）

## 日次checklist（印刷して毎日チェック）

```
□ Days 1-7: r/popular+AskReddit+ELI5を10分観察+10-20upvote
□ Days 8-14: 5-10コメント（rising threads先乗り・1-5番先着）
□ Days 15-21: 5コメント+高価値投稿1件（AI開示+末尾1行）
□ Days 22-30: 週1投稿（月曜10:00 CDP自動）
□ 毎日: IP=スマホテザリング（自宅IP禁止・X垢と別アダプタ）
□ 毎日: 垢は1つのみ（u/hbomax）
```

## Karma形成の自動化境界（重要）

| 行動 | 自動化 | 理由 |
|---|---|---|
| **upvote** | ❌ 手動 | rapid-fire=BOTトリガー |
| **コメント** | ❌ 手動 | 同上+テンプレ検出 |
| **投稿** | ✅ CDP自動（週1） | 8/19実績・頻度抑制で安全 |

## 投稿内容5原則（r/tokyo失敗+2026調査統合）
1. **データの実体と限界を冒頭で正直開示**（「掲載予算帯の中央値で実払額ではありません」）
2. **小サンプルは断定せず**「N=○○の傾向として」
3. **箇条書き天国+数字羅列を避ける**（AI slop判定回避）
4. **人間の見解を必ず1つ入れる**（「この地区ならこの1軒」）
5. **自己宣伝は末尾1行**（9:1以上で価値提供）+ **AI使用は開示**

## 技術経路（2026-09-07確定）

| 経路 | 判定 | 理由 |
|---|---|---|
| **CDP headed Chrome + cookie内fetch** | ✅ 採用 | 検出最低・8/19投稿成功実証済 |
| OAuth API | ❌ | 週1投稿では不要。新垢+API=botプロファイル |
| playwright stealth | ❌ | Cloudflare強化。WSL Python PlaywrightはSIGTRAP |
| 匿名curl | ❌ | 403確定（8/19実測） |

## Phase計画

| Phase | 担当 | 期間 | 状態 |
|---|---|---|---|
| **1. 新垢作成+cookie取得** | ユーザー | 2026-09-07 | ✅ 完了（Galleria RTX3090+hr01ルーター） |
| **2. CDP週1投稿パイプライン** | AI | 2026-09-07 | 🔄 構築中（`reddit_cdp_submit_v2.js`） |
| **3. warm-up 21日** | ユーザー | 2026-09-07〜27 | ⏳ 開始待ち（1日10分） |
| **4. 週1投稿** | AI+ユーザー | 2026-09-28〜 | ⏳ Phase3完了後（cron自動+確認） |

## 関連ファイル
- `/mnt/d/Project2/kensho/reddit_cdp_submit_v2.js` — CDP週1投稿スクリプト（新垢用）
- `/mnt/d/Project2/kensho/data/reddit/cookie_new.json` — 新垢cookie（JSON形式・ヘッダー文字列化して使用）
- `/mnt/d/Project2/kensho/data/reddit/post_queue.json` — 投稿キュー（週1投稿内容）
- `/mnt/c/temp/reddit_cookie_set.js` — cookie注入（8/19実績・9/7でJSON対応確認）
- `/mnt/d/Project2/kensho/reports/2026-09-07-reddit-newaccount-research.md` — 統合レポート
