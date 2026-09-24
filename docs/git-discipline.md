# Git Discipline in Shared Repository (/mnt/d/Project2/kensho)

To maintain stability and prevent destructive git operations from affecting sibling tasks, the following rules are strictly enforced:

## Prohibited Operations on Shared Tree
- `git reset --hard`
- `git stash`
- `git checkout -- <path>`

## Mandatory Workflow
If you need to perform actions that modify the HEAD of the shared repository (e.g., experimental testing, complex rebase, extensive refactoring):

1. **Isolate your workspace:**
   Use a git worktree to create an isolated environment for your branch.
   `git worktree add ../wt_<task_id> -b wt_<task_id> origin/main`

2. **Immediate Persistence:**
   Adopt an "edit -> commit -> push" cycle.
   - Make small, incremental changes.
   - Commit as soon as a logical unit of work is completed.
   - Push immediately to avoid data loss in case of shared repo rewinds.

3. **Recovery:**
   If you suspect your work has been lost due to a shared repo rewind:
   - Use `scripts/salvage_lost_commits.py` to search for dangling commits.
   - If not found, use `git fsck --lost-found`.

## Reporting Destruction
If you identify a destructive operation, notify the team via Kanban comment, including the time and the offending command if possible, to allow for quick identification and remediation.
