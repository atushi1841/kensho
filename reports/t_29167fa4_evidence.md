# QA verification evidence — t_29167fa4

## verification_evidence

$ git log --oneline | head -5
9705079 revenue-worker: t_e5fa3d3c non-API eval — reject Pizza Bot (Amazon Apache-2.0 OSS desktop, no revenue hook)
e9c7016 revenue-worker: t_9d494bc4 critic v167 winrate match — prefer tweet_id field + handle±48h fuzzy fallback
cfbb369 debug: t_9d494bc4 remaining artifacts
cf8e630 debug: t_9d494bc4 probe artifacts (uncommitted cleanup)
1126c22 revenue-worker: t_ed8baffa verification evidence (critic v154 plan B stagger)

$ grep -n "STAGGER_MOD" /mnt/d/Project2/kensho/kensho-auto-apply.sh
67:# ── critic v154 follow-up (t_ed8baffa) 案B: 垢別スタガー ──
73:STAGGER_MOD=${KENSO_STAGGER_MOD:-10}   # 0で無効化（ロールバック）
98:  STAGGER_MIN=$(( RANDOM % (STAGGER_MOD > 0 ? STAGGER_MOD : 1) ))
102:  if [ "$STAGGER_MOD" -gt 0 ]; then log "stagger $acct +${STAGGER_MIN}分"; fi

$ bash -n /mnt/d/Project2/kensho/kensho-auto-apply.sh && echo "syntax OK"
syntax OK

$ git show 92ca4b8 --stat
 kensho-auto-apply.sh | 139 +++++++++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 139 insertions(+)

$ python3 -m pytest tests/test_winrate_analysis.py -q
12 passed in 11.40s

$ python3 -m pytest tests/test_script_drift_watch.py -q
7 passed in 30.79s

$ git status --porcelain
（ワーキングツリークリーン、追加変更なし）
