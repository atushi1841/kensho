import json
d = json.load(open('/mnt/d/Project2/kensho/data/needs_prediction.json'))
assert len(d) >= 3 and all(isinstance(v, (int, float)) and v > 0 for v in d.values()), "validation failed"
print("OK", d)