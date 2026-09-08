# all-status dedup guard (hear-saisei-boushi) — t_58335360

## 目的
kensho-non-api-revenue-hunter が毎晩同じ案件を再作成する事故を根絶する。
原因: 旧 idempotency 照合がアクティブ状態のみで、`done`/`archived` に解決済みの
案件が dedup 対象外となり再作成されていた。

## 変更
1. `scripts/kanban_norm.py`
   - 追加 `ALL_STATUSES = ACTIVE_STATUSES + ("done","archived","scheduled")`
   - 追加 `dedup_key(title, organizer="", condition="")` — Stripe-style 決定的キー
     (norm_title + organizer + condition を pipe 連結・正規化)
   - `is_duplicate(..., include_all_statuses=False)` を追加。True のとき全
     ステータス(done/archived 含む)で重複判定。デフォルト False で後方互換。
   - `fetch_existing_normalized_titles` は title_like=None 対応を既存実装維持。
2. `kensho-non-api-revenue-hunter.py` (repo root + profile/sweeps 両方)
   - dedup 呼び出しを `include_all_statuses=True` に変更
   - idempotency key を `sha1(dedup_key(title, url, body[:80]))` に変更
     (title+organizer+condition から決定)

## デプロイ
repo root と profile copy(sweeps cron 実行実体)を同一内容に同期済み。

## verification_evidence
$ python3 verify.py
ALL_STATUSES: ('ready', 'todo', 'running', 'blocked', 'triage', 'done', 'archived', 'scheduled')
PASS: ALL_STATUSES covers active + done + archived + scheduled
PASS: dedup_key deterministic across case/whitespace
PASS: dedup_key with no extra args == norm_title
PASS: is_duplicate(all_statuses) matched done/archived existing task t_00a820f2
INFO: active-only match for done/archived = False

$ python3 -m py_compile kensho-non-api-revenue-hunter.py scripts/kanban_norm.py .../kensho-non-api-revenue-hunter.py   -> COMPILE OK

$ python3 scripts/kanban_norm.py   -> self-check 4 samples OK
