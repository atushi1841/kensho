import glob, os, yaml, json
from collections import Counter

base = "/mnt/d/Project2/kensho"
cfg = yaml.safe_load(open(base + "/config.yaml"))
print("project_dir:", cfg["general"]["project_dir"])

# 導線 in collect logs
clogs = sorted(glob.glob(base + "/logs/collect_20260920_*.log"))
print("\ncollect logs:", len(clogs))
for f in clogs:
    txt = open(f).read()
    n = txt.count("導線")
    print(" ", os.path.basename(f), "導線 lines:", n)

# collected_today.json and non_x report
for p in [base + "/data/collected_today.json"]:
    print("\n", p, "exists:", os.path.exists(p))
print("non_x reports:", glob.glob(base + "/reports/non_x_manual_*.md"))

# collected.json label distribution
cj = json.load(open(base + "/data/collected.json"))
print("\ncollected.json total:", len(cj))
c = Counter(x.get("導線", "(none)") for x in cj)
print("label counts:", dict(c))
nx = sum(v for k, v in c.items() if k != "X")
print("non-X:", nx)

# today's non-X SKIP in auto log
atxt = open(base + "/logs/auto_20260920.log").read()
print("auto_20260920 非X導線 SKIP count:", atxt.count("非X導線"))
