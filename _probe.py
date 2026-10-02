import json, os
a = json.load(open('/mnt/d/Project2/kensho/apify-figure-price/actor.json'))
i = json.load(open('/mnt/d/Project2/kensho/apify-figure-price/input_schema.json'))
o = json.load(open('/mnt/d/Project2/kensho/apify-figure-price/output_schema.json'))
print('actor.json input type:', type(a.get('input')).__name__)
print('actor.json output type:', type(a.get('output')).__name__)
print('input_schema.json type:', type(i).__name__, 'top keys:', list(i.keys())[:5] if isinstance(i, dict) else len(i))
print('output_schema.json type:', type(o).__name__, 'top keys:', list(o.keys())[:5] if isinstance(o, dict) else len(o))
print('input equal actor.input:', i == a.get('input'))
print('output equal actor.output:', o == a.get('output'))
print('env APIFY_TOKEN set:', bool(os.environ.get('APIFY_TOKEN') or os.environ.get('APIFY_TOKEN_DEFAULT')))
try:
    import apify_client
    print('apify_client version:', getattr(apify_client, '__version__', '?'))
    import inspect
    from apify_client import ApifyClient
    sig = inspect.signature(ApifyClient.actor)
    print('ApifyClient.actor sig:', sig)
except Exception as e:
    print('apify_client import error:', repr(e))