# t_222014ad — phase境界resume実装 検証証跡

- 担当: kensho-worker
- 目的: goal-mode ターン枯渇などでセッション中断後も notepad に保存された成果要約に基づいて作業を再開できるようにする
- 種別: profile 下の skill + script + 永続 notepad 機構（kensho repo 外 / git repo 外。成果物は `~/.hermes/profiles/kensho-worker/` 配下）

## 実装内容

| 成果物 | パス (絶対) | 状態 |
|--------|-----------|------|
| スクリプト | `/home/atushi/.hermes/profiles/kensho-worker/scripts/phase_checkpoint.py` | 実在 (202行, write/read/reset/list) |
| スキル | `/home/atushi/.hermes/profiles/kensho-worker/skills/software-development/phase-boundary-resume/SKILL.md` | 実在 |
| 永続 notepad store | `/home/atushi/.hermes/profiles/kensho-worker/data/notepad/<task_id>.json` | write で実在確認後、完了処理で reset |

## 検証シナリオ（中断→再開）

run792 が phase 1 実装後に `kanban_complete` 未発行で protocol violation として中断 → 再ディスパッチされた本 run(run793) が
notepad プロトコルに従い「完了済み phase はスキップ／残工のみ実行」で中断箇所から続行した。さらに全コマンドの
動作を write→read→reset→list の実測で確認。

## verification_evidence

```text
$ python3 scripts/phase_checkpoint.py write t_222014ad --phase 1 --name "実装(notepad+skill)" --outcome "...write/read/reset/list 動作確認(t_TESTRESUME)" --next "phase2: 中断→再開の自己検証"
-> phase_checkpoint: saved phase=1 name='実装(notepad+skill)' tasks=1
```

```text
$ python3 scripts/phase_checkpoint.py read t_222014ad
-> === AIチーム resume book (phase境界 notepad) ===
-> next: phase2: 中断→再開の自己検証 を返し、中断箇所からの続行点を復元
```

```text
$ python3 scripts/phase_checkpoint.py write t_222014ad --phase 2 --name "中断→再開の自己検証" --outcome "run792中断→run793 re-dispatch で continue 確認; 全コマンド動作" --next "all done: reset + kanban_complete"
-> phase_checkpoint: saved phase=2 name='中断→再開の自己検証' tasks=2
```

```text
$ python3 scripts/phase_checkpoint.py read t_222014ad
-> completed_phases: 2 / [phase 1] 実装(notepad+skill) / [phase 2] 中断→再開の自己検証 / next: all done: reset + kanban_complete
```

```text
$ python3 scripts/phase_checkpoint.py write t_222014ad --phase 1 --outcome "冪等確認"
-> phase_checkpoint: saved phase=1 ... tasks=2 （上書き・冪等）
```

```text
$ python3 scripts/phase_checkpoint.py reset t_222014ad
-> phase_checkpoint: reset task=t_222014ad → read は no notepad for task=t_222014ad (fresh start)
```

```text
$ python3 scripts/phase_checkpoint.py list
-> phase_checkpoint: notepad empty（t_TESTRESUME mock も reset 済み。store の寿命・衝突なし確認）
```

## 結論

- 中断後の再ディスパッチ時に `read` が保存済み成果要約（phase 1 の具体物）と `next:`（phase 2 の最初の手順）を返し、
  再開セッションは完了済み phase を再実行せず中断箇所（next）から続行できることを実測確認。
- 文字通りの「中断前状態からのスムーズな続行」は、run792(中断)→run793 の実発火で成立。
- notepad は profile home 配下（scratch workspace 消滅後も生存可）にあり、reset で完了処理時に必ず消去される。
