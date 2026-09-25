# t_3dbc1fbe 検証レポート — 収益記録の陳腐化（当日entryが失効のまま残る）→ reconcile＋乖離検知

- タスク: t_3dbc1fbe / assignee: kensho-revenue-worker
- 問題: 日次収益収集は 7:05 の1回だけ。Cookie失効で `login_ok=false` の当日entryが書かれた後、
  同日中に Cookie が復旧して収集が成功しても当日entryは失効のまま残る（記録が実態と食い違う）。
  さらに JS単独実行による復旧は `data/gumroad_state.json` しか更新しないため、日次レポートの
  「直近の収益データ」と warnings が終日ズレたままになる。
- 実装コミット: 実装本体 `df91ceb`（`--check` 欠落の是正と契約テスト追加は `5bee7d7`）

## 受入基準の充足

1. `scripts/revenue_record_reconcile.py` — 乖離検出（既定＝読み取りのみ・乖離ありで exit 1）と
   `--apply` による修復（**ライブ state の値のみから再導出**・値の捏造なし）を実装。
   `collectors.gumroad_ok` を同一規則で再計算し、復旧済みなら失効 warning を除去、
   `gumroad_reconciled` に監査記録を追記。過去日entryは不可触（entry date と state date の一致を必須）。
   書込は tmp + `os.replace` の原子的置換。ミラーするキー集合と gumroad_ok 規則は本番
   `kensho_revenue_collect` の単一ソース（`GUMROAD_STATE_MIRROR_KEYS` / `gumroad_ok_flag` /
   `gumroad_collector_flags`）を import して使う（テスト側で再実装しない＝意味論ドリフト防止）。
   → `5bee7d7` で `--check` を受入基準どおりの**明示フラグ**へ（それ以前は `--check` が
   `unrecognized arguments` で exit 2＝カード記載の検証コマンドが実動しなかった）。
2. `gumroad_freshness.py`（レポート3.5節）が乖離を検出したら【要対応】行で修復コマンドを提示。
3. pytest 新規ファイル緑。
4. 当日（2026-09-25）の該当 entry を `--apply` で実際に修復し、`data/revenue-daily.json` に
   監査記録つきで反映（`df91ceb` に収録）。

## verification_evidence

$ python3 -m pytest tests/test_revenue_record_reconcile.py tests/test_revenue_collect.py tests/test_collection_volume.py -q
78 passed in 43.17s

$ python3 scripts/revenue_record_reconcile.py --check
revenue-reconcile OK entry_date=2026-09-25 state_date=2026-09-25 — 記録とライブstateは一致
（exit=0）

$ python3 scripts/revenue_record_reconcile.py --check --apply
usage: revenue_record_reconcile.py [-h] [--daily DAILY] [--state STATE] [--check] [--apply] [--json] [--now NOW]
revenue_record_reconcile.py: error: --check と --apply は同時に指定できない（--check は既定動作・--apply は修復）
（exit=2）

$ python3 -c "当日entryのgumroad節/collectors/warnings/gumroad_reconciledを表示"
gumroad: login_ok=True / sales_page_ok=True / last_success_at=2026-09-25T13:19:41 / balance_usd=0
collectors.gumroad_ok=True / warnings=[] / gumroad_reconciled.at=2026-09-25T18:59:10
gumroad_reconciled.changed_keys=8（balance_usd,last_7_days_usd,last_28_days_usd,total_earnings_usd,login_ok,collected_at,last_success_at,sales_page_ok）
gumroad_reconciled.login_ok_before=False / login_ok_after=True
gumroad_reconciled.removed_stale_warnings=["Gumroadログインセッション失効（Cookie再エクスポートが必要）"]
record_collected_at_before=2026-09-25T07:07:35.390（＝収集時の失効記録）/ state_collected_at=2026-09-25T13:19:36.063（＝復旧後のライブ）

$ python3 -m mypy scripts/revenue_record_reconcile.py
scripts/kensho_revenue_collect.py:156: note: (or run "mypy --install-types" to install all missing stub packages)
scripts/kensho_revenue_collect.py:321: error: Unused "type: ignore" comment  [unused-ignore]
Found 2 errors in 1 file (checked 1 source file)
（既存2件＝156行 requests stubs / 321行 unused-ignore。本diffは `revenue_record_reconcile.py` と CLI契約テストのみで、この2件は本作業前から存在）

$ git rev-list --left-right --count origin/main...HEAD
0	0

$ git log --oneline -1
5bee7d7 fix(revenue): t_3dbc1fbe --check を明示フラグ化（既定動作のエイリアス・--apply併用はexit2）+ CLI契約テスト

## 実測した乖離と修復（2026-09-25・t_3dbc1fbe）

- 乖離の実測値: 当日entryの gumroad 節は `login_ok=false` / `collected_at=2026-09-25T07:07:35.390` /
  `warnings=[Gumroadログインセッション失効（Cookie再エクスポートが必要）]`、同時点のライブ
  `data/gumroad_state.json`（13:19更新）は `login_ok=true` / `sales_page_ok=true` → **8キー乖離＋collectors自己矛盾**。
- 修復: `--apply` でライブ state の8キーを再導出（値のコピーのみ）、`collectors.gumroad_ok=true` へ再計算、
  失効 warning を除去、`gumroad_reconciled` に before/after を記録。修復後 `--check` は OK（exit 0）。
- KPI: before=8 → after=0（当日entryとライブstateの乖離キー数）／warning: before=1件 → after=0件
- 他日への影響: 24 entry のうち変更は 2026-09-25 の1件のみ（過去日entryは日付不一致で対象外・テストで固定）。
- 冪等性: 一致時は書き込みゼロ（バイト同一）をテストで固定。

## 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"t_3dbc1fbe の受入基準未達だった点（カード記載の検証コマンド `--check` が unrecognized arguments で exit 2）を是正し、`--check` を既定動作の明示エイリアスとして実装（--apply との同時指定は usage error=exit 2）。CLI契約テストを --check／--checkなし／--check+--apply／修復後--check の4経路に拡張。実データで `--check`=OK exit 0、3ファイル pytest 78 passed、mypy 新規エラー0 を実測。","what_went_well":["カード本文の検証コマンドを実際に叩いて未達を検出（--check が exit 2）し、実装側を契約に合わせた","既定動作と--checkの等価性を同一 exit code・同一マーカーで機械的に固定した","実データの修復が git 追跡下（revenue-daily.json は df91ceb 収録）にあり、証跡とデータが一致していることを確認した"],"what_could_improve":["前runでカード本文の検証コマンドを実行検証せずに完了報告しようとした（フラグ名の実在確認を最初にやるべきだった）","コミットに兄弟タスクが既に stage していた reports/daily-improvement-2026-09-25.md が1件混入した（git add は明示パスだが、事前stagedの確認を怠った）"],"mistakes_or_risks":["残リスク: 乖離検知はレポート生成時にしか走らない（自動修復はしない設計）","回避策: 修復はライブstateのコピーのみ・過去日不可触・冪等をテストで固定"],"learned":"カード本文に書かれた検証コマンドは『実行して初めて契約になる』。実装完了の判定前に、カード記載コマンドを1回は実際に叩いて exit code を確認する。","confidence":9,"verification_evidence":"pytest 3ファイル78 passed / --check 実データ=revenue-reconcile OK exit 0 / --check+--apply=usage error exit 2 / 当日entry gumroad_reconciled.changed_keys=8・login_ok_before=false→after=true・warning1件除去・collectors.gumroad_ok=True・warnings=[] / mypy 新規0（既存2件は156・321行） / unpushed 0-0"}}
```
