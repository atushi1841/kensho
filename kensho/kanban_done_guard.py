import subprocess
import json
import sys


def get_task_diff_paths(task_id):
    # git log --all --grep=<task_id> --name-only のパス集合を取得
    result = subprocess.run(["git", "log", "--all", "--grep", task_id, "--name-only"], capture_output=True, text=True)
    return set(result.stdout.splitlines())


def get_current_diff_paths():
    # git diff --name-only origin/main..HEAD のパス集合を取得
    result = subprocess.run(["git", "diff", "--name-only", "origin/main..HEAD"], capture_output=True, text=True)
    return set(result.stdout.splitlines())


def get_commit_diff_paths(commit_hash):
    # git show --name-only <commit_hash> のパス集合を取得
    result = subprocess.run(["git", "show", "--name-only", commit_hash], capture_output=True, text=True)
    # Filter out empty lines and whitespace
    return set(line.strip() for line in result.stdout.splitlines() if line.strip())


def validate_evidence(evidence_path, task_id):
    with open(evidence_path, "r") as f:
        evidence = json.load(f)
    artifact_paths = set(evidence.get("artifact_paths", []))
    code_artifacts = {path for path in artifact_paths if path.endswith(('.py', '.sh', '.js'))}

    if not code_artifacts:
        print(f"Warning: No code artifacts found in {evidence_path}")
        return True

    # (k)-1: At least one code artifact must be in task's own diff or current diff
    task_diff_paths = get_task_diff_paths(task_id)
    current_diff_paths = get_current_diff_paths()
    if not code_artifacts.intersection(task_diff_paths) and not code_artifacts.intersection(current_diff_paths):
        print(f"Error: artifact not bound to task diff in {evidence_path}")
        return False

    # (k)-2: source_commits must exist and each commit must touch at least one code artifact
    source_commits = evidence.get("source_commits", [])
    if not source_commits:
        print(f"Error: source_commits missing or empty in {evidence_path}")
        return False
    for commit in source_commits:
        commit_diff_paths = get_commit_diff_paths(commit)
        if not code_artifacts.intersection(commit_diff_paths):
            print(f"Error: commit {commit} does not touch any code artifact in {evidence_path}")
            return False

    return True

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--validate":
        print("Usage: python kanban_done_guard.py --validate <evidence_path>")
        sys.exit(1)

    evidence_path = sys.argv[2]
    task_id = evidence_path.split("_")[1]
    if not validate_evidence(evidence_path, task_id):
        sys.exit(1)