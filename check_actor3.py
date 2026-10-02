import json
with open('/mnt/d/Project2/kensho/apify-figure-price/.actor/actor.json') as f:
    d = json.load(f)
print('.actor/actor.json keys:', list(d.keys()))
print('Has input:', 'input' in d)
print('Has output:', 'output' in d)
print('Has inputSchema:', 'inputSchema' in d)
print('Has outputSchema:', 'outputSchema' in d)