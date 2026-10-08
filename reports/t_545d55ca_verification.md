## verification_evidence
task_id: t_545d55ca

$ git -C /mnt/d/Project2/kensho log --oneline -5
0be3b32 t_3903ecdb: update verification evidence (heading + command citations)
a00d035 t_3903ecdb: add verification evidence for dead-source false-positive fix
87a9b1f t_3903ecdb: restore kensho-everyday source
e0f673f Add GitHub Actions Run button to 3 README docs
8ad0230 Make actor_name optional in demo workflow

$ gh api repos/atushi1841/kensho/actions/runs --jq '.workflow_runs[] | select(.name=="Apify Actor Demo") | {id,created_at,status,conclusion}'
{"conclusion":"success","created_at":"2026-10-08T18:21:15Z","id":37823616537,"status":"completed"}
{"conclusion":"success","created_at":"2026-10-08T18:11:04Z","id":37822306344,"status":"completed"}

$ ls /mnt/d/Project2/kensho/.github/workflows/apify-demo.yml
/mnt/d/Project2/kensho/.github/workflows/apify-demo.yml
