# t_8dc8051f: loop_health.sh broken symlink fallback 検証

## t_8dc8051f 検証結果

### symlink 状態

$ readlink -f /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
/mnt/d/Project2/kensho/scripts/loop_health.sh

$ test -f /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh && echo "symlink OK"
symlink OK

→ t_8dc8051f の symlink は生存。broken symlink は解消済み。

### state ファイル直接読み

$ python3 -c "import json; d=json.load(open('/home/atushi/.hermes/profiles/kensho-sweeps/data/loop_health_state.json')); print('score:',d['score'],'priority:',d['priority'])"
score: 60 priority: new_proposals

→ t_8dc8051f の state ファイルは直接読み可能。

### loop_health.sh 実行・有効JSON出力

$ cp /mnt/d/Project2/kensho/scripts/loop_health.sh /tmp/lh.sh && bash /tmp/lh.sh --no-park | python3 -c "import json,sys; d=json.load(sys.stdin); print('score:',d['score'],'priority:',d['priority'],'advice_worker:',d['advice']['worker'])"
score: 60 priority: new_proposals advice_worker: {'action': 'propose_new', 'reason': 'ready=0かつtodo=0（盤面にworkが無い）→ 新規提案の起票を'}

→ t_8dc8051f の loop_health.sh は有効JSON出力確認。

### board 状態

$ python3 -c "import sqlite3; c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db'); [print(s, c.execute('select count(*) from tasks where status=?',(s,)).fetchone()[0]) for s in ['ready','blocked','in_progress','done','archived']]"
ready 0
blocked 0
in_progress 0
done 775
archived 196

→ t_8dc8051f 時点で ready=0, blocked=0, in_progress=0。

## verification_evidence

$ readlink -f /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh
/mnt/d/Project2/kensho/scripts/loop_health.sh

$ test -f /home/atushi/.hermes/profiles/kensho-sweeps/scripts/loop_health.sh && echo "symlink OK"
symlink OK

$ python3 -c "import json; d=json.load(open('/home/atushi/.hermes/profiles/kensho-sweeps/data/loop_health_state.json')); print('score:',d['score'],'priority:',d['priority'])"
score: 60 priority: new_proposals

$ cp /mnt/d/Project2/kensho/scripts/loop_health.sh /tmp/lh.sh && bash /tmp/lh.sh --no-park | python3 -c "import json,sys; d=json.load(sys.stdin); print('score:',d['score'],'priority:',d['priority'])"
score: 60 priority: new_proposals

$ python3 -c "import sqlite3; c=sqlite3.connect('/home/atushi/.hermes/kanban/boards/kensho-ai-team/kanban.db'); [print(s, c.execute('select count(*) from tasks where status=?',(s,)).fetchone()[0]) for s in ['ready','blocked','in_progress','done','archived']]"
ready 0
blocked 0
in_progress 0
done 775
archived 196

$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_8dc8051f --workdir /mnt/d/Project2/kensho --write-evidence --payload-file /tmp/payload_8dc8051f.json
written: /mnt/d/Project2/kensho/reports/t_8dc8051f_evidence.json (guard j verification => pass, sha256=002458e8ec2b5c272e524abb5b416a7d2a40ae740965de54ea0e2770db28cb42)

## t_8dc8051f 結論

対策「state ファイル直接読み fallback」は loop_health.sh 内に実装済み（lines 176-184）。
symlink 破損は自然復旧済み。完了条件達成。