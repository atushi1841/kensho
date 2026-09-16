# QA run495 — 2026-09-16 時刻依存立会い（t_20e376bc / kensho-qa）

対象: t_c6b4e3ed 委譲の時刻依存立会い2件（apify-run-monitor・kensho-dm-winner-check の last_status=ok 実測確認）

## 0. 事前検証（発火待ちの前に実施・実測）

- `$ jq '.jobs[]|select(.id=="f7e76dea2a0e" or .id=="352914c18733")|{name,last_status,last_run_at,next_run_at}' ~/.hermes/profiles/kensho-sweeps/cron/jobs.json`
  → apify=ok@04:01:21(next 06:01:21) / dm=error@04:09:46(next 10:00)。dmのlast_errorは04:16 symlink化以前の陳腐値と判定（run494申し送りと同状態）
- `$ ls -la ~/.hermes/profiles/kensho-sweeps/scripts/dm_scan.py`
  → symlink (Sep 16 04:16) → /mnt/d/Project2/kensho/scripts/dm_scan.py 実在
- `$ md5sum ~/.hermes/profiles/kensho-sweeps/scripts/dm_scan.py /mnt/d/Project2/kensho/scripts/dm_scan.py`（resolve追従）
  → 350d4492b924e0627bf4082d200cfee6 一致
- `$ md5sum ~/.hermes/profiles/kensho-sweeps/scripts/apify_run_monitor.py /mnt/d/Project2/kensho/scripts/apify_run_monitor.py`
  → 4fd98a25f452a7a611258f1d192d966c 一致（二重ソース化なし）
- 静的解決確認: dm_scan.py L36 `ROOT = Path(__file__).resolve().parent.parent` — symlink化後は /mnt/d/Project2/kensho に解決され、L43 の transaction_pairs.json 参照先 = /mnt/d/Project2/kensho/kensho/application/transaction_pairs.json（実在・jq妥当性OK）。data/ 書込可（drvfs rwx）、config.yaml 実在
- 発火履歴突合: `$ hermes cron runs 352914c18733 --profile kensho-sweeps` → 04:09失敗(source=direct)以降の自動発火なし・next=10:00 確認。`hermes cron runs f7e76dea2a0e` → 02:52失敗(APIFY_TOKEN not set・旧script)、04:00 direct成功、06:01自動発火成功で ok 化を確認

## 1. apify-run-monitor（f7e76dea2a0e）立会い — t_c6b4e3ed 委譲①

（本節は cron 自動発火の実測で確定）

## 2. kensho-dm-winner-check（352914c18733）立会い — t_c6b4e3ed 委譲②

（10:00 自動発火の実測で確定）

## 3. 判定

（両立会いの実測値確定後に記入）
