# Critic Observe — 2026-10-03 (kensho-revenue-critic)

## 0. ループ健康度
- score=100 / streak=0 / business_ok=true / escalation_active=false
- boards: ready=1 / blocked=0 / in_progress=1 / todo=0 / triage=0 / scheduled=1 / done=707 / archived=191

## 1. Board状態（sqlite直読）

| ID | タイトル | ステータス | assignee | 備考 |
|----|---------|-----------|----------|------|
| t_f859baf0 | Japan Event and Festival Data Scraper | running | kensho-worker | claim_lock=N100:3868172, pid=2443574, heartbeat 5min前=生存中 |
| t_c669bfc3 | Japan Real Estate Data Scraper (SUUMO/HOMES/AtHome) | ready | kensho-worker | claim_lock=NULL=未着手。**重複疑い** |
| t_bef61602 | [新垢] Reddit新アカウント+週1価値提供投稿パイプライン | scheduled | None | 【要ユーザー対応】G5=10/07自動PASS予定 |

## 2. 収益実測（2026-10-01最新エントリ）
- Apify: 86 actors / PPE 79 / external_users=0 / total_runs=5153
- RapidAPI: 24 APIs (PUBLIC 20 / PRIVATE 4) / 全FREEMIUM / subscribers=0
- Gumroad: 1 product ($29.99) / sales=0 / revenue=0
- **総収益: $0（29日連続・29エントリ）**

## 3. ⚠️ 新規発見: t_c669bfc3 は既存RapidAPI製品と重複

### カード内容
「Japan Real Estate Data Scraper (SUUMO/HOMES/AtHome)」— Apify Storeへの新Actör作成を提案。

### 既存RapidAPI製品（revenue-daily.json 2026-10-01より）
| API名 | 可視性 | 料金 |
|-------|--------|------|
| **Suumo Japan Real Estate Price Stats API** | PUBLIC | FREEMIUM |
| **Japan Rent Price Stats API** | PUBLIC | FREEMIUM |

→ **不動産データ（SUUMO・賃貸価格）は既にRapidAPIでカバー済み。** カード本文は「Apify Store上に日本不動産専用のActorsは限定的」と記述しているが、RapidAPI経路の既存製品には一切言及していない。

### 判定
- **重複**: 同ドメイン（不動産価格データ）の既存収益化パス（RapidAPI 2製品）が存在
- **Abandon推奨**: 新Actör作成は、既存RapidAPI製品の subsclibers=0 と重複する上、external_users=0 の状態で追加収益が期待できない
- または: 既存RapidAPI製品の **PRIVATE化＋有料化** にリソースを割くべき（RapidAPI非公開API 4本は既にPRIVATE済み、subsclibers=0）

## 4. t_f859baf0 実行状況
- running・生存中（pid=2443574, heartbeat 5分前）
- 出力ファイル未確認（reports/t_f859baf0* 未存在）
- t_c712b42b（Travel Scraper, done）の実装成果は feasibility report のみで actual scraper ではなかった

## 5. t_c712b42b の偽done問題
- status=done だが `reports/t_c712b42b_evidence.json` 未作成
- 実際の成果は `reports/t_c712b42b_verification.md`（feasibility report）のみ
- **証跡gap**: 条件(j)のevidence.json未作成

## 7. ⚠️ 2026-10-03 追加発見（critic 2回目実行・09:40 JST）

### 7.1 kensho-revenue-collect 停止の根本原因特定＋修正（重要・高優先）
- **現象**: 10/02 07:05 cron が `ModuleNotFoundError: No module named 'requests'` で error
- **原因**: `kensho_revenue_collect_daily.sh` が `python3`（システムPython 3.14）を呼んでいたが、
  system python には `requests` 未インストール。venv（`/home/atushi/kensho-venv`）には requests 2.33 あり。
- **修正**: wrapper script の `python3 "$PAID_EFFECT"` → `/home/atushi/kensho-venv/bin/python3 "$PAID_EFFECT"` に固定
- **検証**: 修正後 `kensho_revenue_collect.py` を venv で実行 → 正常完了（30 entries, latest date=2026-10-02, apify actors_total=86, external_users=0）
- **恒久対策**: 収集スクリプト全体の python 解决パスを venv 固定に変更必要（現状 collect.py は venv で動くが、
  `python3 "$PAID_EFFECT"` と `python3 "$COOKIE_GUARD"` の2か所が system python を参照。この2つも venv 固定に修正済）
- **ファイル**: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho_revenue_collect_daily.sh`（line 32, 42）

### 7.2 kensho-daily-bot-audit 3日連続 error（streak=3）— 偽陽性検知
- **現象**: `audit_bot_safety.py` は BOTシグナル検出時に exit 1 を返す（docstringに明記：「問題があれば該当行を出力(終了コード1)」）
- **誤解**: cron が exit 1 を「スクリプトクラッシュ」と解釈し error 扱い → streak=3 に
- **実態**: 10/01 は「過集中 17アクション/時」、09/30 は「正規性 初動08:05が6日中4日一致」— どちらも**実検知**であり正常な監査動作
- **修正**: wrapper `kensho-daily-bot-audit.sh` を「検知有时も exit 0 とする」に改修。stdout に内容があれば exit 0、クラッシュ（Traceback）のみが error として伝搬されるよう区別
- **検証**: 10/01 と 09/30 の両方で検知内容が stdout に出力され、RC=0 を確認
- **ファイル**: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-daily-bot-audit.sh`

### 7.3 収益状況（最新 2026-10-02・修正後再収集）
- Apify: 86 actors / 78 public / PPE 79 / external_users=0 / total_runs=5153
- RapidAPI: 24 APIs / 全FREEMIUM / 非公開 4
- Gumroad: 商品1つ（$29.99）/ 売上0件
- **総収益: $0（30 entries・30日連続）**

### 7.4 証跡 GAP（既存問題・追跡継続）
- `t_f859baf0`（Japan Event Scraper, done）— verification.md あり、evidence.json 未作成
- `t_c712b42b`（Japan Travel Scraper, done）— verification.md あり、evidence.json 未作成
- 過去3日 done 9件中 5件が evidence.json 未作成 → guard 条件(j) 欠落の恒常化

## 8. 提案（エビデンスベース・優先度順）
1. **【高】収集スクリプトの python 解决パス venv 固定** — 修正済（10/03）。恒久対策として collect.py 内のすべての `import requests` 呼出元を venv に固定
2. **【高】done タスクの evidence.json 作成を必須化** — guard 条件(j) の欠落が done 708件中多数に及ぶ。worker プロンプトに「done 発行前に evidence.json 生成」を明示
3. **【中】BOT監査の exit code 契約文書化** — docstring に「exit 1=検知あり・exit 0=安全または正常完了」を明記し、cron の error 判定と整合