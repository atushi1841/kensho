import json
d=json.load(open('data/tmp/pay_per_event.json'))
ppe = d.get('actors_ppe', {})
print('Total PPE actors:', len(ppe))
print('PPE > 0:', sum(1 for v in ppe.values() if v > 0))
print('PPE == 0:', sum(1 for v in ppe.values() if v == 0))
for k,v in sorted(ppe.items(), key=lambda x: -x[1])[:10]:
    print(f'  {k}: {v}')