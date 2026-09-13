# critic 統合レポート: ツイート8項目のKenshoへの取り込み（t_a972bd85）

日付: 2026-09-13 05:50 JST / 実行: kensho-critic (run440)
元ツイート: https://x.com/aiedge_/status/2098427326723994110（AI Edge, 2026-09-11）
取得根拠: x-fallback-fetch スキル（fxtwitter API 200、本文全文取得済み。run439でも取得済みをセッションDBで確認）

## 結論（8項目評価）

| # | 項目 | 判定 | 状態 |
|---|------|------|------|
| 08 | GitHub - operate your repo on live state | ✅ 統合済・実動検証 | MCP github ツール接続実証（issue #1 作成→close→読み戻し state=closed 確認、list_commits でHEAD 431f87c読取）。git ls-remote も接続OK |
| 07 | XURL - run X using the CLI | ⚠️ 修復済・要ユーザー再認証 | Linuxネイティブv1.3.1を ~/.local/bin/xurl に導入（従来の /mnt/c npmシムはモジュール欠損で壊れていた）。tai-auto OAuth2トークン失効を検出（RefreshTokenError）→要 `xurl auth oauth2 --app tai-auto`（ブラウザ操作）。Kensho応募本体はPlaywright+セッションCookie+twscrape経由のため**業務影響ゼロ** |
| 06 | Competitor Monitor - watches your niche | ✅ 等価物・実動中 | cron `kensho-opportunity-discovery`（enabled, 毎朝8:00、Apify Store競合監視）・`apify_visibility_watch.py`（9/8導入、count読み取り教訓済）・`seo_rank_watch.py`。加えてcompetitor-news-monitorスキルをcriticプロファイルへ導入 |
| 05 | Grounded Citations - cited research | ✅ 統合済 | 運用実態に準拠済み: kensho-research-agent（enabled, 毎日12:00）プロンプトが「最低3情報源・4検索以上」「一次情報まで2〜3階層深掘り」を強制。grounded-citationsスキル（sources.py台帳付き）をcriticプロファイルへ導入 |
| 04 | Notion | ⏸ 導入済・スキップ推奨 | スキルをcriticプロファイルへ導入。**NOTION_API_key未登録（全~/.hermes検索で0件）**、ntn CLIはセキュリティゲート（threat-intel検証不能）でsingle-query導入不可。Kenshoはreports/*.md+Kanbanで同等機能→**ユーザーが明示的に希望しない限り導入不要と推奨** |
| 03 | Meeting Actions | ✅ 等価物・実動中 | Kenshoに会議はないが、AIチームのKanbanハンドオフ（summary/metadata→次のrunのworker_context注入）がまさにこのパターン。run439クラッシュ→run440復帰で機能実証済み。meeting-action-itemsスキルも導入済 |
| 02 | Inbox Triage | ✅ 等価物・実動中 + メール基盤導入済 | Kenshoの実インボックス=当選DM: cron `kensho-dm-winner-check`（enabled, 10:00/21:00、kensho-dm-scan.sh）。メール側はhimalaya v2.1.0を~/.local/binに導入・動作確認済（`himalaya --version` OK）。メールアカウント設定はユーザー資格情報待ち（任意） |
| 01 | Google Workspace | ⏸ 導入済・資格情報待ち | スキル（gws_bridge.py/google_api.py/setup.py同梱）をcriticプロファイルへ導入。google_token.json/google_client_secret.json不在→OAuthブラウザフローはユーザー操作必須。KenshoパイプラインはGoogleに依存しないため**現状スキップで支障なし** |

内訳: 実動統合5（08/06/05/03/02）+ 修復済で再認証1分作業が残り1（07）+ 資格情報待ちでスキップ推奨2（04/01）。

## 本runで実施した状態変更（すべて低リスク・応募パイプライン非接触）

1. xurl v1.3.1 Linux バイナリ導入: `~/.local/bin/xurl`（実行確認済）。`~/.xurl` → `~/.xurl/auth.yml` への自動マイグレーション発生（v1.3.1仕様）。テストでdefault appを一時的にtai-autoへ切替→**`default`へ復元済**（auth.ymlのdefault_app: default確認）
2. himalaya v2.1.0 バイナリ導入: `~/.local/bin/himalaya`（バージョン表示確認済）
3. スキル8点をbundled（~/.hermes/skills）からcriticプロファイルへコピー: github-auth, grounded-citations, competitor-news-monitor, notion, meeting-action-items, google-workspace, email-inbox-triage, himalaya（SKILL.md存在8/8確認）
4. GitHub MCP書き込み検証: atushi1841/kensho issue #1 作成→即close（ライブ状態操作の実証、遗跡なし=closed済み）
5. `npm config set prefix ~/.npm-global`（グローバル導入のsudo回避用、PATH追加は未実施→ユーザー判断）

##  BOT検出リスク評価（絶対ルール準拠）

- 応募・収集・フォローの各レート制限/上限/ランダム遅延には**一切触れていない**（xurl/himalayaはパイプライン非使用、スキルコピーはLLM側のみ）
- xurl再認証後のAPI利用は本パイプラインでは不要。仮に使う場合もPlaywright経路併用で指紋分離を維持すること（x-bot-detectionスキル準拠）

## ユーザーへの申し送り（残り作業）

- [ ] 07: 再認証 1分 — `xurl auth oauth2 --app tai-auto`（ブラウザPKCE）。不要なら放置で可（パイプライン影響ゼロ）
- [ ] 04/01: Notion・Google Workspaceを使う実用目的があれば認証付与（なければスキップ確定でOK）
- [ ] 02(メール): 実際のメールボックスを繋ぐなら himalaya config.toml + IMAP/Gmail資格情報（未設定でもDM選別は稼働中なので任意）
- [ ] PATH: `~/.local/bin` は既存、`~/.npm-global/bin` は今後のグローバルCLI導入時にのみ追加判断

## メタ教訓

- Windows側npmシム（/mnt/c/.../xurl）はWSLからモジュール解決不能で恒久的に壊れていた。WSL内cronがxurlを使う日はLinuxバイナリで統一されていることを今回確認済み（2026-09-13）
- bundledスキルは`~/.hermes/skills/`に全8項目分が既に存在し、プロファイルコピーだけで「取り込み」が成立する（外部インストールほぼ不要）。今後の類似「仕組み取り込み」依頼はまずbundled棚卸しを最初のステップにすべき（run439のprotocol_violationはxurl認証ループで詰まったことが原因）
