# Killing a hung `flock -c` worker tree & releasing the lock — research findings

Date: 2026-09-06 · Env: WSL2 (Ubuntu, util-linux flock 2.39.3, kernel Linux, no systemd) · All claims below **empirically verified on this machine** unless marked (doc).

## 1. Who holds the flock lock

`flock -n LOCK -c 'cmd'` (no `-F`) does: **flock opens LOCK as fd 3, locks it, forks; the child execs `/bin/sh -c cmd`** (util-linux source: `sys-utils/flock.c` → `build_shell_cmd_argv()` + `fork()` + `waitpid()`).
Source: https://github.com/util-linux/util-linux/blob/master/sys-utils/flock.c

Verified process chain for the real hung worker:

```
flock (fd 3 -> /tmp/kensho-locks/atushi16.lock, LOCKS)
└─ bash -c 'cd ...; export ...; python orchestrator.py ...'   (INHERITED fd 3)
   └─ python orchestrator.py                                   (INHERITED fd 3)
      └─ playwright/driver/node cli.js run-driver              (NO fd 3 — Python subprocess default close_fds=True)
         └─ chromium ...                                       (no fd 3)
```

flock(2) man page: the lock is on the **open file description**, shared by fork/dup, and "the lock is released ... when **all** such file descriptors have been closed."
https://man7.org/linux/man-pages/man2/flock.2.html

### Verified kill semantics (tests on /tmp sandbox)

| Action | Lock released? |
|---|---|
| Kill only python (leaf), flock+bash alive | **NO** — bash/flock still hold fd 3. (flock exits when its direct child dies *if the child is the exec'd program*; with a bash -c wrapper, killing python makes bash exit, then flock exits → released. In TEST A the leaf *was* the exec'd child, so flock exited and lock freed.) |
| Kill only flock, child chain alive | **NO — critical trap.** Children hold inherited fd 3; `flock -n` test stayed BLOCKED until the fd-3-holding descendant also died. |
| Kill flock + bash + python (everything up to the close_fds boundary) | **YES** — lock released even with node/chromium still running (TEST 8). Python's `subprocess` default `close_fds=True` breaks inheritance at the node driver. |
| `fuser -k LOCKFILE` (kills every fd holder) | **YES** — verified `RELEASED-BY-FUSER-K`. |
| `kill -TERM -PGID` on a `setsid`-launched tree | **YES** — group kill caught flock+bash+python+bg grandchildren, lock free afterwards (TEST G). |

flock(1) options that change this: `-F/--no-fork` (flock is *replaced by* the command — python itself holds the lock; killing python releases it), `-o/--close` (close fd before exec — only the waiting flock parent holds the lock; **weakens the guard**: a second worker can start while the first still runs). Man: https://mankier.com/man1/flock (util-linux 2.39.3, `-o` text: "useful if command spawns a child process which should not be holding the lock").

## 2. Process-group kill

- **Current launch is unsafe for group kill**: cron runs `kensho-auto-apply.sh`; its backgrounded `flock ... &` children all share the *script's* PGID (real tree: flock 4158562, bash, python, node all pgid=4158456 = the already-exited cron script). `kill -TERM -4158456` would hit **every account worker spawned in that tick**.
- Fix at launch: `setsid flock -n ... -c '...' &` → flock becomes session leader, pgid == its own pid, whole tree inherits it (verified). Then `kill -TERM -<flock_pid>` targets exactly one account.
- kill(2): "If pid is less than -1, then sig is sent to every process in the process group whose ID is -pid." https://man7.org/linux/man-pages/man2/kill.2.html
- Tree enumeration: `/proc/<pid>/task/<tid>/children` (proc(5), needs CONFIG_PROC_CHILDREN) lists children per-thread; `pgrep -P <pid>` lists by ppid. Both are **one level** — you must BFS either way. /proc children is a live snapshot; after a parent dies, children re-parent to PID 1 and vanish from the tree (see §4), so tree-walk must happen **before** killing the parent, and be backed by a pattern sweep.
- Without setsid, the watchdog must BFS the tree via a ppid map (`ps -eo pid,ppid`) built *before* killing, and kill leaves→root individually.

## 3. Why SIGTERM fails on hung asyncio/Playwright, and TERM→KILL escalation

- SIGKILL/SIGSTOP cannot be caught/blocked/ignored; SIGTERM can (signal(7)). https://man7.org/linux/man-pages/man7/signal.7.html
- Python: signal handlers run **only between bytecodes on the main thread**. A main thread stuck inside a C call (deadlocked `loop.run_until_complete`, blocking socket/pipe read to a dead node driver) never runs the handler → TERM appears ignored. Verified: a `SIG_IGN` asyncio-style loop survived `kill -TERM`, died on `kill -KILL` (TEST E).
- Playwright node driver registers SIGINT/SIGTERM handlers that attempt *graceful* browser shutdown over a pipe that is exactly what's wedged → handler hangs forever (microsoft/playwright#19374 "page.content() hangs indefinitely"; #1847 "Hanging when browser runs out of memory"; issue #41013 documents the handler set `SIGINT/SIGTERM/stdin close + 15s hard exit` and its gaps).
- WSL2 caveat: if a process is in **D state** (uninterruptible I/O — plausible here since the project lives on `/mnt/d` = drvfs/9p), even SIGKILL won't reap it until the 9p request completes. Check `ps -o stat`; a D-state process that won't die needs the 9p/server to be unstuck (or `wsl --shutdown` from Windows).
- Correct escalation (pure bash, verified TEST G/H/I):
  1. `kill -TERM -"$PGID"` (negative = whole group)
  2. poll `kill -0 -"$PGID" 2>/dev/null` (or per-pid) up to N seconds
  3. `kill -KILL -"$PGID"`
  4. poll again; then pattern-sweep orphans (§4); then verify lock (§5).
- `timeout -k <grace> <dur> cmd` does exactly TERM-then-KILL; verified exit **137** (128+9) when the child ignored TERM and was KILLed after `-k`. timeout(1): exit 124 = timed out via TERM, 137 = KILLed. https://man7.org/linux/man-pages/man1/timeout.1.html — but for an already-running tree, do the manual escalation.

## 4. Orphaned chromium / playwright cleanup

- **This is a known upstream bug**: microsoft/playwright#41013 — "@playwright/mcp orphans Chrome process trees when the host dies without SIGINT/SIGTERM": after `kill -9` of the host, the chrome tree is re-parented to PID 1, "each holding 200–500 MB resident. On WSL with a fixed memory cap this drives the VM toward swap. `pgrep -f 'ms-playwright/mcp-chrome' | xargs kill -9` reliably frees hundreds of MB." https://github.com/microsoft/playwright/issues/41013
- Related: playwright-python#984 (chrome processes left after script finished), playwright-dotnet#1749 (node+chromium remain after Dispose), playwright#19374 (zombie/stuck procs after hang).
- Playwright launches chromium with `--user-data-dir=/tmp/playwright-...` (verified on this box: `/tmp/playwright-artifacts-*`, `playwright_firefoxdev_profile-*` leftovers). This repo uses patchright/playwright `chromium.launch()` (non-persistent) — `kensho/application/browser.py:708`.
- Safe sweep patterns (scoped so you don't kill the user's Chrome or Hermes's own playwright-mcp browser — both run on this machine):
  - `pkill -9 -f 'kensho-venv/lib/python3.12/site-packages/playwright/driver'` (node driver)
  - `pkill -9 -f -- '--user-data-dir=/tmp/playwright'` (chromium/headless_shell spawned by playwright)
  - Age-guard: only kill when `ps -o etimes=` > threshold, or when no matching orchestrator python exists (true orphans).
- Also `rm -rf /tmp/playwright-*` older than a day — /tmp is tmpfs on WSL2, so leaked dirs consume RAM directly.

## 5. Verifying lock release

- `/proc/locks`: `1: FLOCK ADVISORY WRITE <PID> <maj:min:inode> 0 EOF` — match inode via `stat -c %i LOCKFILE` (verified exact match, e.g. `08:30:1903249`). https://man7.org/linux/man-pages/man5/proc.5.html
- Functional test (best): `flock -n "$LOCK" -c true && echo FREE || echo HELD` (used in every test above).
- `fuser -v LOCKFILE` lists **every** process with an fd on it (verified: showed both flock and the fd-inheriting child); `fuser -k` kills them all (verified releases lock). Note `fuser -k` defaults to SIGKILL; `-TERM`/`-HUP` selectable.
- `lslocks` (util-linux) = friendlier /proc/locks with names.
- Deep-dive reference: https://gavv.net/articles/file-locks/ ("File locking in Linux" — flock locks the open-file-description, released when all fds close).

## 6. Pidfile best practices (PID-reuse safety)

- Never kill from a bare stored PID. Verify identity: compare `/proc/<pid>/cmdline` (NUL-separated; `tr '\0' ' '`) against the expected command, and/or store `ps -o lstart=`/starttime field 22 of `/proc/<pid>/stat` alongside the PID and compare (unix.SE#675873 accepted approach: write `pid` + `cat /proc/$pid/cmdline` into the pidfile, re-check on stop; unix.SE#610443/#610486: `pkill -f` with a unique label, or PID+elapsed-time cross-check).
  - https://unix.stackexchange.com/questions/675873/how-to-check-if-process-with-pid-x-is-the-one-you-expect
  - https://unix.stackexchange.com/questions/610435/how-to-avoid-killing-a-wrong-process-when-using-pid-number-for-killing
- For this project the **flock wrapper itself is the pidfile**: `pgrep -f "flock -n /tmp/kensho-locks/$acct.lock"` matches exactly one process, cmdline contains the account name — no stale-file problem, kernel-guaranteed. Cross-check with the /proc/locks PID for the lock inode; if they disagree, trust /proc/locks + `fuser`.
- `kill -0 $PID` only proves existence (and permission); it also succeeds on zombies — reap-check with `ps -o stat=` != Z. (Verified: after `wait`, `kill -0` fails.)

## Recommended watchdog algorithm (cron, every 15 min)

```bash
# launcher change (kensho-auto-apply.sh line ~88): add setsid
setsid flock -n "$LOCK_DIR/$acct.lock" -c "..." >>"$LOG_FILE" 2>&1 &

# watchdog, per account:
LOCK=/tmp/kensho-locks/$acct.lock
FP=$(pgrep -f "flock -n $LOCK" | head -1) || continue
ET=$(ps -o etimes= -p "$FP") || continue
[ "$ET" -lt 1800 ] && continue            # threshold: max session 15min + slack
PG=$(ps -o pgid= -p "$FP" | tr -d ' ')
kill -TERM -- -"$PG" 2>/dev/null          # grace
for i in $(seq 1 10); do kill -0 "$FP" 2>/dev/null || break; sleep 1; done
kill -KILL -- -"$PG" 2>/dev/null          # escalation
sleep 1
pkill -9 -f -- '--user-data-dir=/tmp/playwright'   # orphan sweep (age-guarded)
pkill -9 -f 'kensho-venv/.*playwright/driver'
flock -n "$LOCK" -c true || log "LOCK STILL HELD: $(fuser -v $LOCK 2>&1)"
```

## Key sources

- flock(2)/flock(1)/kill(2)/signal(7)/timeout(1)/proc(5): https://man7.org/linux/man-pages/man2/flock.2.html · man1/flock · man2/kill.2.html · man7/signal.7.html · man1/timeout.1.html · man5/proc.5.html
- util-linux flock.c: https://github.com/util-linux/util-linux/blob/master/sys-utils/flock.c
- unix.SE#149767 (flock + background children keep the lock; `-u/--unlock` technique): https://unix.stackexchange.com/questions/149767/linux-bash-prevention-flocking-for-background-process
- unix.SE#594027 (stale locks / robust flock): https://unix.stackexchange.com/questions/594027/handling-of-stale-file-locks-in-linux-and-robust-usage-of-flock
- unix.SE#254457 / #21542 (TERM→KILL timeout patterns): https://unix.stackexchange.com/questions/254457/kill-process-with-timeout · https://unix.stackexchange.com/questions/21542/automatically-kill-process-if-its-runtime-exceeds-some-predetermined-value
- Playwright orphans: https://github.com/microsoft/playwright/issues/41013 · https://github.com/microsoft/playwright-python/issues/984 · https://github.com/microsoft/playwright-python/issues/1847 · https://github.com/microsoft/playwright/issues/19374 · https://playwright.dev/docs/docker (PID-1/zombie/--init guidance)
- File-lock semantics deep dive: https://gavv.net/articles/file-locks/
