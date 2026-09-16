# t_ed8baffa verification — critic v154 Follow-up: 15分グリッド集中対策

## verification_evidence

$ git log --oneline | grep -i "stagger\|plan B\|v154" | head -3
92ca4b8 Apply critic v154 follow-up plan B: stagger sleep 0-9 min

$ grep -n "STAGGER_MOD" /mnt/d/Project2/kensho/kensho-auto-apply.sh
67:# ── critic v154 follow-up (t_ed8baffa) 案B: 垢別スタガー ──
73:STAGGER_MOD=${KENSO_STAGGER_MOD:-10}   # 0で無効化（ロールバック）
98:  STAGGER_MIN=$(( RANDOM % (STAGGER_MOD > 0 ? STAGGER_MOD : 1) ))
102:  if [ "$STAGGER_MOD" -gt 0 ]; then log "stagger $acct +${STAGGER_MIN}分"; fi

$ bash -n /mnt/d/Project2/kensho/kensho-auto-apply.sh && echo "syntax OK"
syntax OK

$ git diff HEAD~1 -- kensho-auto-apply.sh | grep -c "STAGGER"
6

$ git status --porcelain kensho-auto-apply.sh
（ワーキングツリークリーン、追加変更なし）

## 実施内容

critci v154が検出した「15分グリッド±2分98.8%集中度問題」に対し、Plan B（spawn子内sleep 0-9分+覚醒後再ガード）を採用実装。

- `kensho-auto-apply.sh` に STAGGER_MOD ロジック追加（commit 92ca4b8）
- 垢別乱数分(0-9分)の就寝をspawn前に挿入
- 22:30以降はスタガー0（22:47終了スケジュール割れ防止）
- 覚醒後ガード: pgrep二重実行チェック、同時実行数、RAM閾値

## 自己レビュー（Reflexion）

- what_went_well: 既存バッチ構造を壊さず挿入できた。bash -n構文チェック合格。
- what_could_improve: RANDOMはbash組み込みの線形合同法のため偏りあり。本番では`shuf`や`/dev/urandom`推奨。
- mistakes_or_risks: 22:30以降スタガー0は07:00 no_action_windowと重複する可能性（理論上は07:00はno_action_window内だがstartup自体は抑制される）。
- learned: QAの指摘通り、guard条件(i)のcron drift防止効果はc_t_cdcfc7aaでも実証済み。
- confidence: 9/10
