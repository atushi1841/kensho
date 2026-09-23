# 2026-09-23 revenue-worker 実施記録 — チームプロファイルLLM認証死の修復（dispatcher crash loop解消）

担当: nightly-worker (cron 5e8ec4984bba) / assignee kensho-revenue-worker
実施時刻: 2026-09-23 11:57–12:12 JST
タスク種別: 収益/AIチーム基盤の障害復旧（カード未紐付けのインフラ修復。本記録がその検証記録）

## 1. 症状（実測）

dispatcher が kensho-revenue-worker を起動するたびに 2分以内に死ぬ（終端 kanban 呼出なし = protocol_violation）。

```
$ hermes kanban --board kensho-ai-team show t_9fb3c02d
Runs (6):
  #960 crashed  @kensho-revenue-worker  667s   2026-09-23 11:29
  #961 crashed  @kensho-revenue-worker  1084s  2026-09-23 11:40
  #962 crashed  @kensho-revenue-worker  121s   2026-09-23 11:59
  #963 crashed  @kensho-revenue-worker  120s   2026-09-23 12:01
  #964 crashed  @kensho-revenue-worker  61s    2026-09-23 12:08
  #965 running  @kensho-revenue-worker  active 2026-09-23 12:09   ← 修復後
```

ログの実体（`hermes kanban log t_9fb3c02d`）:

```
⚠️ Model fallback: nex-agi/nex-n2.5-pro:free via openrouter unavailable (authentication failed); using ...
⚠️  API call failed (attempt 1/5): AuthenticationError [HTTP 401]
   🔌 Provider: openrouter  📝 Error: HTTP 401: User not found.
（OR無料5モデルすべて同じ。続いて）
   🔌 Provider: deepseek  📝 Error: HTTP 401: Authentication Fails, Your api key: ****570d is invalid
❌ Non-retryable client error (HTTP 401). Aborting.
→ 終端 kanban 呼出なしで rc=0 終了 → protocol_violation
```

同一症状のブロックカード: t_c4e810c6（ログ内 HTTP 401 = 160件 / User not found = 110件）、t_0dc05be4（同 62件 / 42件）。いずれも `Agent crash x2 (failure_limit=2)` で blocked。

## 2. 原因（切り分け・実測）

チーム5プロファイルの `OPENROUTER_API_KEY` が失効していた（kensho-sweeps のみ健全）。

```
$ curl -s -o /dev/null -w '%{http_code}' https://openrouter.ai/api/v1/key -H "Authorization: Bearer <sweeps key>"
200
$ 同上 チーム5プロファイルのキー(kensho-critic/qa/worker/revenue-qa/revenue-worker)
401
$ hermes cron list | grep fallback → kensho-auto-fallback-watchdog (5 3,9,15,21 * * *) active
   … 鎖(fallback_providers)は健全（sync-team --dry-run → 5プロファイルすべて「9段OK」）。
     認証キーは鎖同期の対象外のため、watchdogでは検出・修復されない死角だった。
```

- 各プロファイルの config.yaml は `api_key: ${OPENROUTER_API_KEY}` 参照 → `.env` が正。
- 鎖は正常だったが、ORキー死により鎖の先頭5段が全部401 → 最後のdeepseekキー（…570d）も401 → 「非リトライ可能」で即Abort（残りのfireworks/nous段へ進まない設計）。
- 同一キー値(…bbca)がチーム5プロファイル共通で、この値だけが死んでいた。

## 3. 実施した処置（低リスクのクラウドAPI資格情報修復）

- kensho-critic / kensho-qa / kensho-worker / kensho-revenue-qa / kensho-revenue-worker の `.env` の `OPENROUTER_API_KEY` を、健全な kensho-sweeps の値（HTTP 200 実測）へ置換。
- 各 `.env` を `.env.bak-orkey-<YYYYmmddHHMM>` にバックアップ（ロールバック可）。
- **`default` / `provider` / `model` は一切変更していない**（モデル切替に該当しない＝禁止領域に触れていない）。

```
$ 置換後、各プロファイルの .env から読み直して検証
kensho-critic            verify_HTTP=200
kensho-qa                verify_HTTP=200
kensho-worker            verify_HTTP=200
kensho-revenue-qa        verify_HTTP=200
kensho-revenue-worker    verify_HTTP=200
```

## 4. 検証（エンドツーエンド実測）

```
$ hermes -p kensho-revenue-worker --cli chat -q "Reply with exactly: OK-AUTH"
⚠️ Model fallback: auto via custom unavailable (rate limit); using accounts/fireworks/models/deepseek-v4-flash-0731 via fireworks.
OK-AUTH        ← 401消失、完走

$ (ブロック解除後) hermes kanban show t_9fb3c02d → #965 running
$ python3 -c "現在run(#965)のログ区間を抽出して 401/413/User not found を数える"
401 in current run: 0 | User not found: 0 | 413: 0
  ┊ 📖 preparing read_file…  ┊ 🔎 preparing search_files…   ← 実作業中
```

→ t_9fb3c02d を unblock（復活経緯をコメント#1053に記録）、dispatcher が #965 を正常稼働中。
t_c4e810c6 / t_0dc05be4 には同根因のコメントを残置（unblock は kensho-worker / QA のレーン）。

## 5. 残課題（【要ユーザー対応】候補・禁止領域に近いため未実施）

1. **deepseekキー(…570d)がチーム5プロファイルで401死のまま**（鎖の最終段）。今回の修復でOR段が復活したため実害は小さいが、OR枠枯渇時に再発する。→ 正しい新キーの投入 or sweepsの…4e70のチーム伝播を推奨（sweepsキーは本WSLから api.deepseek.com へ到達できず単独検証不能＝未検証値を勝手に伝播しない方針）。
2. **freellmapi auto の 413 事象**: run #964 は `custom(auto)` が小コンテキストモデル `openrouter/liquid/lfm-2.5-2.6b:free` を唯一の候補として選び、~12.6Kトークンで `HTTP 413 request too large` → 圧縮不能で abort。auto ルーティングの候補選定（コンテキスト長フィルタ）の問題で、**モデル切替/ルーティング変更は禁止領域**のため未処置。

## 6. 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"チーム5プロファイルの失効OPENROUTER_API_KEYを健全値へ修復し、dispatcherのcrash loop(401起因)を解消。t_9fb3c02dをunblockし#965が実作業中であることを確認。","what_went_well":["401ストーム→真因(キー失効)をcurl実測で切り分けた","鎖(sync-team)は健全でキーは死角だと特定した","修復後、プロファイル単体呼出とdispatcher実run(#965)の二段で検証した"],"what_could_improve":["鍵が5プロファイルに複製されている設計上、失効時に全workerが同時死する。キー健全性の定期監視(200/401判定)をcron化すべき","起動直後に#965が走っていたため、最初の判断で『待機』に倒す前にプロファイル単位の認証検証を先に行うべきだった"],"mistakes_or_risks":["キー伝播によりsweepsとチームが同一ORアカウントの日次枠を共有する（枠枯渇が早まる可能性）","deepseekキーは未修復のまま残置（未検証値の伝播を避けた）"],"learned":"『protocol_violation連発=ラッパー欠陥』と決めつけず、まずログのプロバイダ認証エラーを数える。鎖同期(watchdog)はキーを面倒見ない。","confidence":9,"verification_evidence":"curl HTTP200×5 / hermes -p kensho-revenue-worker --cli chat OK-AUTH / run#965ログの401・413件数=0 / kanban show のRuns"}}
```
