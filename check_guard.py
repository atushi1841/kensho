import json, subprocess, sys

r = subprocess.run([sys.executable, "/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py",
                    "t_7060bd39", "--task", "--json"], capture_output=True, text=True)
d = json.loads(r.stdout.strip().splitlines()[-1])
print("pass=", d["pass"])
print("detail:", json.dumps(d["detail"], ensure_ascii=False, indent=1))