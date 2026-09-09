# Reddit新アカウント戦略 × 最適自動化手法 深掘りレポート
作成: 2026-09-07 (kensho-sweeps) / 出典: Web(8ソース)+X(2件)+既存スキル/実測

## 0. 結論 (TL;DR)
- **旧垢Significant-House109は回復不可**（垢級403 spam block+8/20 r/tokyoでscore0/karma-7の否定的履歴）。新垢作成が正解
- **新垢の作成はユーザー手動**（新アカウント登録はCAPTCHA/メール認証がBOT検出の最高リスク、自動化不可）
- **新垢の運用は半自動が最適**: 投稿は週1の価値提供型、Karma形成(コメント/vote)は自動化しない。旧垢の失敗原因は「投稿」の頻度ではなく「価値欠如+低Karma」
- **最適技術経路 = 既存のCDP+cookie方式を新垢に流用**（reddit-posting-automationスキルで実証済・playwright不要・Chromeはheaded=検出困難）
- **API OAuthは不要**（投稿はcookie fetchで完結。APIは商用で$0.24/1K+要承認、個人使用は週1投稿で100QPM枠の0.1%も使わない）

## 1. 背景: 旧垢の失敗解剖（実測データ）
| 項目 | 事実 |
|---|---|
| 8/19 | r/tokyoにHOT PEPPER 200店データ記事投稿 |
| 結果 | score 0 / 批判多数 / comment karma -7 |
| 批判の本質 | 「データの実体不明示」「小サンプルの断定」「AI slopと読める」(reddit-posting-automationスキルに教訓化済み) |
| 9/6 | Gumroad告知で/api/submit → **垢級403 spam block**（cookieは有効） |
| 判定 | Kamma 0以下+低信頼度垢の自己promo = 自動スパム判定。7日Karma形成では回復不能（垢が既にflagged） |

## 2. 2026年Reddit enforcementの構造（Web実測ソース）
Redditのスパム判定は**4層**（reddireach 2026-03）:
1. **アカウント信頼**: 垢年齢+Karma+投稿頻度+リンク比率+重複度
2. **ドメイン信頼**: リンク先URLの評判（gumroad.comは低評価ドメイン可能性）
3. **subreddit規則**: 各subのAutoMod（Karma閾値10〜数百+垢年齢要件）
4. ** Crowd Control**: 低Karma垢のコメントは折りたたまれる

**重要統計**:
- 340件のstartup marketing試行の分析: **89%が30日以内BAN、7% shadowban**（reddireach）
- Reddit Transparency Report 2025 H1: admin削除の**57.5%がspam**（upvotegg）
- shadowbanは自動実行で通知なし。log-outでprofileが404=確定
- 最も速いトリガー: ①flagged IPからの新垢+即リンク投稿 ②同一URLを複数subへ短時間投稿 ③複数垢を同一device/networkから操作 ④rapid-fire投稿

**Karma閾値**: 多くのsubは10〜数百Karma+垢年齢で投稿ブロック。100 Karma+コメント履歴が多くのfilterをクリア（growditt/growwithreddit）

## 3. 新垢の安全な立ち上げ（最適warm-up）
**共通コンセンサス（reddireach+growditt+growwithreddit+redditmaster 4ソース一致）**:

| 週 | 行動 | リンク |
|---|---|---|
| 第1週 | 観察+upvoteのみ。投稿ゼロ | ❌ |
| 第2週 | コメント毎日5-10件（1-3時間後のrising threadに先乗り） | ❌ |
| 第3週 | コメント継続+1件の高価値テキスト投稿 | ❌（本文内の関連リンクのみ） |
| 第4週以降 | 週1投稿。90%価値提供/10% promo | ✅ 自然な文脈で1行 |

**Karmaの最速経路 = コメント先乗り**（growwithredditのr/NewToReddit実例: 6日で684 Karma、大半はrising threadの1-5番コメント）
- 大型sub（r/AskReddit, r/relationship_advice等）でKarmaを形成→**垢信頼は全subに転移**する（topicは関係ない）
- comment karmaはpost karmaより高速（削除リスク低・1日10件の機会）

## 4. 技術経路比較（実測ベース）
| 経路 | 検出リスク | 2026現状 | 判定 |
|---|---|---|---|
| **CDP headed Chrome+cookie fetch**（現行） | **最低** | 実証済（8/19投稿成功） | ✅ **採用** |
| OAuth API (/api/submit) | 中 | 無料枠100QPMは個人用OKだが、新垢+API OAuthの組み合わせは「script/bot」プロファイル（socialcrawl/redditapis） | ❌（週1投稿では不要） |
| playwright+stealth | 高 | Cloudflare検出強化（browserstack 2026-06）。headed Chromeより脆弱 | ❌（WSL Python PlaywrightはSIGTRAPで不可=メモリ記載済） |
| 匿名curl | - | 403確定（8/19実測） | ❌ |

**CDP方式が最优の理由**:
1. 実Chromeバイナリ（headless非）= Cloudflare/Turnstile困難
2. ブラウザ内fetchはcookie+csrf自動付与 → /api/submit成功
3. WSL PlaywrightはSIGTRAP（環境制約=メモリ記載）
4. 投稿は週1 = レート制限（rolling window）の実質無影響
5. XのBOT検出対策（x-bot-detection）と**分離**（Reddit垢はX垢とIP/UA/指紋を別にする）

## 5. 新垢の運用設計（推奨）
### 5.1 垢設計
- **1垢のみ**（複数垢は「same device/network」トリガー。1垢+IP分離で十分）
- **IP分離必須**: Kenshoの6 WiFiアダプタSOCKS5（1081-1085）から**1ポートをReddit専用**に割り当て。X垢とは**別アダプタ**（例: TankanNotes用1085を転用 or 未使用アダプタ）
- **メール**: Gmail別垢（atushi1841@gmail.comと同一メール禁止=垢リンク検出）
- **人設**: 日本データ/趣味系（データセット告知と整合）。AI使用は**開示**（「I built this with AI」前置き=reddit-posting-automationの倫理線）

### 5.2 自動化境界（人間らしさ≠欺瞞）
| 作業 | 自動化 | 理由 |
|---|---|---|
| 投稿（週1） | ✅ 半自動（Hermesが草稿作成→ユーザー確認→CDP投稿） | 価値提供型+週1=スパムシグナルなし |
| Karma形成（コメント/vote） | ❌ **自動化しない** | 第1-3週はコメント5-10件/日が必要=BOT判定の最速トリガー。ユーザーが10分/日で手動 |
| upvote | ❌ | 同上 |

**判断根拠**: 旧垢の失敗は「自動化」ではなく「価値欠如+低Karma」。新垢を週1投稿+手動warm-upにすれば、403再発の構造を根本除去。

### 5.3 投稿内容ルール（r/tokyo失敗教訓の転用）
1. データの実体と限界を**冒頭で正直開示**（「予算帯は掲載価格で実払額ではない」）
2. 小サンプルは断定しない（「N=○○のサンプルベースで傾向として」）
3. 箇条書き+数字羅列を避ける（AI slop判定）
4. 人間の見解を必ず1つ入れる（「この地区ならこの1軒」）
5. 自己宣伝は末尾1行（9:1以上で価値提供）

## 6. 実行計画
| # | 作業 | 担当者 | 期間 |
|---|---|---|---|
| 1 | 新Reddit垢作成（Gmail別+CAPTCHA+メール認証） | **ユーザー手動** | 10分 |
| 2 | cookie取得（F12→.cookie.txt上書き） | **ユーザー手動** | 5分 |
| 3 | IP分離設定（SOCKS5ポート1つをReddit専用へ） | AI | 15分 |
| 4 | warm-up第1週（観察+upvoteのみ） | **ユーザー** | 1日10分×7日 |
| 5 | warm-up第2-3週（コメント5-10/日） | **ユーザー** | 1日10分×14日 |
| 6 | 週1投稿パイプライン構築（CDP+cookie） | AI | 1時間 |
| 7 | 週1投稿実行（Hermes草稿→確認→投稿） | AI+ユーザー | 週1×5分 |

**総コスト**: ユーザー1日10分×3週 + 投稿週1×5分。AI側は投稿パイプライン構築のみ。

## 7. リスクと対案
| リスク | 確率 | 対策 |
|---|---|---|
| 新垢も即403（作成IPがflagged） | 中 | 作成は**自宅WiFi直結**で、運用はSOCKS5（作成IP≠投稿IPが安全） |
| Gumroadドメインが低信頼 | 高 | 本文は**データサンプルを直接提示**（CSV 10行）+Gumroadは末尾1行。データが主役 |
| r/DataSetsが自己promo禁止 | 中 | まずr/japan, r/AskData等100%価値提供subで2-3週。r/DataSetsは3週後に1回 |
| shadowban再発 | 低（上記順守時） | log-out profile週1チェック（404検出） |

## 8. 旧垢の最終処遇
- **Significant-House109: 削除推奨**（403+否定的履歴=回復コスト>新垢コスト。redditgrow: shadowban appeal成功60-70%だが、Karma0+flagged垢の第2犯は不寛容）
- 代替: 放置+無関心（運用停止）
- **推奨は削除**（IP/メールの垢リンクを断ち切る）

## 出典
- reddireach.com (2026-03) — 4層スパム判定構造
- redditgrow.ai — shadowban appealフロー
- upvotegg.com (2026-07) — Transparency Report spam 57.5%
- postiz.com (2026-01) — API rolling window
- socialcrawl.dev (2026-05) — API価格$0.24/1K
- redditapis.com (2026-05) — per-token budget
- redditmaster/growditt/growwithreddit — Karma warm-upコンセンサス
- browserstack.com (2026-06) — Cloudflare+Playwright検出
- X: @Soranlan (Agent Reach, 2026-06), @deflepard260 (bot farms)
- 既存: reddit-posting-automationスキル (8/19実測), x-bot-detectionスキル, 旧垢403実測 (9/6)
