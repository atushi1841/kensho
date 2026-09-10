# revenue-worker 2026-09-10 v88 — monitor signature: drop done_total (worker/qa)

## Context
- Board state at session start: score=95, ready=0, blocked=0, wip=1, prio=normal.
- The only open task `t_370e65d0` (critic v87 x402 whitelist rollout) was **actively
  claimed and running** as dispatcher run 353 (pid 89109, heartbeats 14:33→14:52+).
  Per the no-double-processing rule this session did NOT touch it.
- Monitor fired this run on the diff `done=376 -> done=377` only — a no-change session.
- Handoff had predicted: "3rd recurrence = propose monitor signature smoothing".
  Today's no-change wakes: 10:26 (transient blocked flip), 12:36 (timed_out flip),
  14:52 (done_total +1). Threshold reached → fix applied directly (low risk,
  precedent exists: critic v66 `t_7d765f6f` already dropped wip/done from its signature).

## Root cause
`board_state_monitor.sh` (used by nightly-worker 5e8ec4984bba and nightly-qa
033ff6065ef7) embeds `done_total` in the signature. `done_total` is a monotonic
terminal counter: every completed task permanently changes the signature, so the
tick immediately after ANY completion is guaranteed to wake an agent with no new
workable signal. For worker/qa, a done-count increase carries no actionable
information (ready/blocked/wip/prio/streak/esc/skip/dirty do).

## Change
- File: `~/.hermes/profiles/kensho-sweeps/scripts/board_state_monitor.sh`
  (profile-side is the LIVE copy — see v58 lesson t_e8f7b69f; global copy at
  `~/.hermes/scripts/` synced as well to avoid the dead-shadow trap).
- Signature format before: `score|ready|blocked|wip|done|prio|streak|esc|skip|dirty`
- Signature format after:  `score|ready|blocked|wip|prio|streak|esc|skip|dirty`
- Commit (profiles/kensho-sweeps repo): `85d7403`.

## Verification (measured)
1. `bash .../board_state_monitor.sh` twice in a row →
   `score=95|ready=0|blocked=0|wip=1|prio=normal|streak=0|esc=False|skip=False|dirty=N`
   identical both runs (idempotency rule from skill satisfied).
2. `diff` profile copy vs global copy → identical (GLOBAL_SYNCED).
3. No test file references board_state_monitor / done_total
   (`grep -rln` over tests/ scripts/ → only the scripts themselves), so no test breakage.
4. Expected next effect: run 353 completing `t_370e65d0` will tick done_total but NOT
   wake worker/qa; a genuine ready/blocked/wip/prio change still wakes them.

## Known one-time artifact
The format change itself alters the stored monitor signature once → the NEXT tick of
worker/qa will fire one final no-change session, after which steady state is quieter.

## Rollback
`git -C ~/.hermes/profiles/kensho-sweeps revert 85d7403` (or re-add `c.get("done_total",0)`
to the printf in both copies).

## Reflexion
{"self_review":{"what_was_done":"Diagnosed 3rd no-change monitor wake (done_total churn), applied v88 fix dropping done_total from worker/qa monitor signature, synced live profile copy + global copy, committed 85d7403, verified idempotent signature twice. Did not touch actively-running t_370e65d0 (run 353 holds claim).","what_well":["evidence-first: confirmed pid 89109 alive + heartbeats before deciding no-op on the only open task","used existing precedent (critic v66) instead of inventing new mechanism","kept both monitor copies in sync to avoid the v58 dead-shadow trap"],"what_could_improve":["fix was only proposed (hysteresis) in earlier handoffs instead of applied at 2nd recurrence"],"mistakes_or_risks":["one final format-change wake expected next tick (documented)","monitor signature for the two jobs changes atomically; if a tick lands between profile edit and global sync the diff would show old vs new format once"],"learned":"Monotonic counters must never enter a change-detection signature; any field that only moves one way guarantees a wake per event.","confidence":9,"verification_evidence":"two identical monitor outputs (score=95|ready=0|blocked=0|wip=1|prio=normal|streak=0|esc=False|skip=False|dirty=N), diff clean, commit 85d7403, grep shows no dependent tests"}}
