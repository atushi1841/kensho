# t_8aa7c2fa verification evidence

## verification_evidence
$ /home/atushi/kensho-venv/bin/python -c "import importlib.metadata as m;print(m.version('scrapling'))"
0.4.15
$ grep -c scrapling pyproject.toml
1
$ python3 scripts/check_dep_drift.py
{"ok": true, "drift": []}
$ echo exit=$?
0