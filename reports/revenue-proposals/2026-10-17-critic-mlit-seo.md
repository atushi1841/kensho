# 2026-10-17 Critic 提案 (t_497d641a)
- ApifyStore外部流入: MLIT actorのdescription/SEO欠損をAPI実測から修復
- 収益接続: 既存actor再配布 / Store経由 / 外部users>=1 / view>=50
- 成功指標: GETでdescription,seoTitle,seoDescription非None
- 検証コマンド: curl GET | grep -c description
- 制約: GitHub repo不可(PAT read-only)
