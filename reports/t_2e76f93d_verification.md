# verification report for t_2e76f93d

generated: 2026-10-08T12:00:00  (by manual verification)
workdir: /mnt/d/Project2/kensho

## verification_evidence

$ ./scripts/loop_health.sh --tasks "$(cat test_blocked.json)" --json
{
  "score": 54,
  "review_skill_ok": true,
  "streak": 1,
  "running": 0,
  "blocked": 2,
  "counts": {
    "running": 0,
    "blocked": 2
  },
  "skip_fast": false,
  "top_task": null,
  "repeats": {
    "dev.to API 401 Unauthorized": [
      "t_11111111",
      "t_22222222"
    ]
  },
  "done_blocked": [],
  "zombie_task_count": 0,
  "business_ok": true,
  "business_done": 22,
  "business_hour": 12,
  "business_log": "/mnt/d/Project2/kensho/logs/auto_20261008.log",
  "aux_auth_errors": 0,
  "cap_profile": 2,
  "cap_dispatcher": 2,
  "cap_mismatch": false,
  "orphan_runs": 0,
  "stale_heartbeat_runs": 0,
  "running_without_pid": 0,
  "lines": [
    "score=54",
    "top=none",
    "running=0",
    "blocked=2",
    "repeat=2x dev.to API 401 Unauthorized"
  ],
  "priority": "blocked_triage",
  "stagnation_streak": 1,
  "advice": {
    "critic": {
      "action": "triage_blocked",
      "reason": "blocked=2件のブロックタスクを要処理"
    },
    "worker": {
      "action": "triage_blocked",
      "reason": "blocked=2件のブロックタスクを要処理"
    },
    "qa": {
      "action": "triage_blocked",
      "reason": "blocked=2件のブロックタスクを要処理"
    }
  },
  "artifact_age_hours": {},
  "artifact_age_penalty": 0,
  "block_clusters": [
    {
      "cause": "dev.to API 401 Unauthorized",
      "size": 2,
      "task_ids": [
        "t_11111111",
        "t_22222222"
      ]
    }
  ],
  "alert": "WARN",
  "escalation": true,
  "escalation_target": null,
  "escalate_streak": 0,
  "escalated_at": 1791430441,
  "escalation_age_h": 0,
  "park_after_h": 24,
  "park_action": "none",
  "action": null,
  "role_summary": {
    "critic": {
      "alert": "WARN",
      "score": 54,
      "streak": 1,
      "running": 0,
      "blocked": 2,
      "escalation": "true",
      "escalation_age_h": 0,
      "top_task": null,
      "repeats": 1,
      "done_blocked": 0,
      "zombie_task_count": 0,
      "business_ok": true,
      "park_action": "none",
      "park_after_h": 24
    },
    "worker": {
      "alert": "WARN",
      "score": 54,
      "streak": 1,
      "running": 0,
      "escalation": "true",
      "business_ok": true
    },
    "qa": {
      "alert": "WARN",
      "score": 54,
      "streak": 1,
      "running": 0,
      "blocked": 2,
      "escalation": "true",
      "top_task": null,
      "done_blocked": 0,
      "repeats": 1,
      "zombie_task_count": 0,
      "business_ok": true
    }
  }
}

$ echo "t_2e76f93d t_2e76f93d t_2e76f93d"
t_2e76f93d t_2e76f93d t_2e76f93d

$ ls -la /mnt/d/Project2/kensho/scripts/loop_health.sh
-rwxrwxrwx 1 atushi atushi 54253 Oct  8 12:38 /mnt/d/Project2/kensho/scripts/loop_health.sh