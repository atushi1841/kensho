# critic v77 実装報告: done_guard 条件(e) — 未pushコードコミット + 引用ハッシュ ancestry 検証

- 日付: 2026-09-09
- カード: t_c1ec5f8b
- 対象ファイル: /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py（ガードのみ、applyロジック無変更）
- ベースコミット: commit fb15e40（kensho main repo）

## 実装内容

1. 条件(e)-1 `git_unpushed_state(workdir)`: `git rev-list --count origin/main..HEAD` が >0 のとき、
   そのコミット範囲が触れるファイルを `git log --name-only` で集約し、コードファイル
   （*.py/*.yaml/*.sh/*.js、既存(d)規則準拠: data/ reports/ *.html docs/ 除外）を含めば fail、
   メッセージは `unpushed code commits: N`。ドキュメントのみ/無変更の未pushは注記だけ付けて pass。
2. 条件(e)-2 `check_cited_hashes(workdir, text)`: summary + 採用 report 本文中の
   「commit/コミット + 7〜40桁hex」トークンを抽出し、`git cat-file -t`（コミットオブジェクトか）と
   `git merge-base --is-ancestor HASH HEAD`（HEAD の子孫か）を検証。幽霊ハッシュ
   （存在しない / rebase消滅 / 別ブランチ）は `cited hash not in HEAD ancestry: <h>` で fail。
   誤認対策: 数字1文字以上を必須（"defaced" 等の完全英字hex語を除外）、語境界チェックで
   cron ID（a85cf2d361cf 風）や t_ タスクIDを引用ハッシュとして計上しない。
3. 移行soft期間: 2026-09-12 まで（E_HARD_AFTER="2026-09-13" 以降 hard ブロック）。
   soft期間中は --json の conditions.e=True のまま detail.e_soft=True + stderr WARNING。
   --soft フラグは全条件無効化の非常用エスケープハッチとして維持。
4. 救済フラグ: `--allow-unpushed <hash,...>`（前方一致可）で正当な local-only 運用を除外。
5. セルフテスト: `--selftest [push_gap]`（カード指定の検証コマンド互換、extra 語は忽略）。
   一時 bare origin + clone を作製し、コードコミット1件の未push状態で `evaluate(workdir=clone)`
   が fail すること、幽霊ハッシュ fail と実HEADハッシュ pass、push 後 pass 復归を検証して
   検出成功時 exit 1。

## verification_evidence

$ cd /mnt/d/Project2/kensho && git stash list >/dev/null; bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py --selftest push_gap; echo exit=$?
selftest push_gap: unpushed_detected=True (note=unpushed code commits: 1)
selftest push_gap: ghost_hash_detected=True valid_head_hash_accepted=True
selftest push_gap: after_push_back_to=pass
SELFTEST OK: guard BLOCKs fabricated unpushed code commits (exit 1 = detection works, per card verification command)
exit=1

$ cd /home/atushi/.hermes/profiles/kensho-sweeps && python3 -m pytest tests/test_kanban_done_guard.py -q 2>/dev/null | tail -1
10 passed in 0.12s

$ cd /home/atushi/.hermes/profiles/kensho-sweeps && python3 - <<'PY' (in-context probe)
unpushed_state(real kensho): {'status': 'pass', 'n_code_commits': 0, ...}  # 実repoは clean+pushed → pass
valid head hash: {'status': 'pass', 'cited': ['fb15e40'], 'bad': []}       # 実HEADハッシュ ancestry pass
ghost hash: {'status': 'fail', 'cited': ['a35c7d0'], 'bad': ['a35c7d0 (not a commit ...)']}  # 1文字違い幽霊を検出
no-false-cites: {'cited': []}  # cron a85cf2d361cf / t_35da58ce は引用ハッシュに誤認しない
e_hard_today: False  # 本日はsoft期間内
ALL OK

$ git -C /mnt/d/Project2/kensho rev-list --count origin/main..HEAD
0

## 実装コミット

- kensho-sweeps profile repo: sweeps@36521c0 feat(guard): done_guard condition (e) unpushed-code + cited-hash ancestry (critic v77, t_c1ec5f8b)
  （profile repo は remote 無し = ローカルのみ。ガード本体の所在は card 指定通り kensho-sweeps）
- kensho main repo: 本報告書のコミット（受け入れハッシュは git log -1 で確認可能、HEAD の子孫）

## 成功指標（QA監査行対応）

今後7日間、QA done-vs-HEAD 監査で「done-while-unpushed」新規 0 件を計測。
soft期間（〜9/12）の検出事例は stderr WARNING に `unpushed code commits` /
`cited hash not in HEAD ancestry` として残り、9/13 以降 hard ブロック化。
