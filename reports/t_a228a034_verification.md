## verification_evidence
$ curl -s -H "Authorization: Bearer $HF_TOKEN" 'https://huggingface.co/api/datasets?author=saboten1&limit=20' | python3 -c "import json,sys; d=json.load(sys.stdin); print('datasets_count:', len(d))"
datasets_count: 1

$ curl -s -H "Authorization: Bearer $HF_TOKEN" 'https://huggingface.co/api/datasets/saboten1/japan-hobby-collectibles-prices-sample' | python3 -c "import json,sys; d=json.load(sys.stdin); print('id:', d.get('id'), 'private:', d.get('private'), 'downloads:', d.get('downloads'), 'siblings:', [s.get('rfilename') for s in d.get('siblings',[])])"
id: saboten1/japan-hobby-collectibles-prices-sample private: False downloads: 0 siblings: ['.gitattributes', 'README.md', 'data/normalized_prices.csv']

$ ls data/hf_dataset_README.md
data/hf_dataset_README.md

$ python3 -m py_compile scripts/revenue_hf_dataset_publish.py && echo "COMPILE OK"
COMPILE OK