# t_d28cf2a8 verification: Hugging Face Hub Space 公開

## verification_evidence

$ curl -s 'https://huggingface.co/api/spaces?author=saboten1&limit=20' | python3 -c "import json,sys; d=json.load(sys.stdin); print('count:', len(d)); [print(' -', s['id']) for s in d]"
=> count: 2
 - saboten1/kensho-kaku
 - saboten1/kensho-kclub

$ curl -s 'https://huggingface.co/api/spaces?search=kensho-kaku&limit=5' | python3 -c "import json,sys; d=json.load(sys.stdin); print('found:', len(d)>0); [print(' -', s['id'], s.get('sdk','?')) for s in d]"
=> found: True
 - saboten1/kensho-kaku static

$ curl -s 'https://huggingface.co/api/spaces?search=kensho-kclub&limit=5' | python3 -c "import json,sys; d=json.load(sys.stdin); print('found:', len(d)>0); [print(' -', s['id'], s.get('sdk','?')) for s in d]"
=> found: True
 - saboten1/kensho-kclub static

$ curl -s https://huggingface.co/saboten1/kensho-kaku | grep -o 'Apify Store' | head -1
=> Apify Store

$ curl -s https://huggingface.co/saboten1/kensho-kclub | grep -o 'Apify Store' | head -1
=> Apify Store

## 実施内容
- HF Space 2本作成: saboten1/kensho-kaku, saboten1/kensho-kclub
- README.md に Apify Store URL (https://apify.com/atushi1841/acts/kensho-sweep-mcp) と GitHub URL (https://github.com/atushi1841/kensho) を埋め込み完了
- SDK: static (Hugging Face Hub Space)

## 成功指標
- HF Space 公開数: 2 (target: >=2) -> 達成
- README に Apify Store URL 埋め込み: 2/2 -> 達成
- 30日以内に external_runs>=1 or Space stars>=1: 継続監視必要

## 自己レビュー
{"self_review":{"what_was_done":"HF Space 2本作成+README埋め込み完了","what_went_well":["huggingface_hub 2.1.1 install OK","create_repo + upload_fileで即座に完了","READMEにApify/GitHub link確認済"],"what_could_improve":["CommitOperationAdd API mismatchで1回失敗→upload_fileに切替"],"learned":"create_repoはspace SDK staticで自動生成READMEあり。upload_fileで上書可。","confidence":9,"verification_evidence":"GET huggingface.co/api/spaces?author=saboten1 → count=2; GET huggingface.co/saboten1/kensho-kaku → Apify Store link found"}}
