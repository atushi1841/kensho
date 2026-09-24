# t_2bd258d5 — 団単位サーロットブレーカと団外団スキップを self_heal.py に実装（early_complete: commit 2e05b42 pre-existing）

t_2bd258d5 タスクの検証証跡。両実装条件とも HEAD 2e05b42 に既存のため新規作業不要（early_complete）。

## verification_evidence

t_2bd258d5 の受け入れ条件は2つ。それぞれ既にコミット済みで、py_compile OK・pytest 30 passed を確認。

### condition 1 — 団単位 failure ceiling（self_heal.py:410-462）

$ grep -n "apply:{account_key}" kensho/core/self_heal.py
16:  - failure ceiling は **キー単位**（apply は `apply:<account_key>`）で数える。全体キーだと
$ grep -n '"key": f"apply:{account_key}"' kensho/application/applier.py
746:                 "key": f"apply:{account_key}",
$ grep -n "blocked_until" kensho/core/self_heal.py
433:        until = _parse_ts(info.get("blocked_until"))
452:                entry["blocked_until"] = (
473:        entry["blocked_until"] = (now + timedelta(minutes=self._ceiling_cooldown_minutes)).isoformat()

key は `apply:<account_key>` の垢単位（applier.py:746 から渡される）。`blocked_until` をしきい値到達時に設定するため、毎時 cron でも構造的に遮断可能（first_fail_time 固定では毎時runで発動できなかった F5 対策）。

### condition 2 — 団外団スキップ（applier.py:881-899）

$ grep -n "network_outage_skip" kensho/application/applier.py
890:            _set_reason("network_outage_skip")
891:            msg = f"[SKIP] {account_key}: ネットワーク圏外/電源OFF/バックOFF（wifi_watchdog検出） → スキップ"
$ grep -n "dead_proxy_reason" kensho/application/applier.py
59:from kensho.utils.safety import dead_proxy_reason as _dead_proxy_reason
856:    _dead = _dead_proxy_reason(cfg, account_key)
888:        skip_reason = dead_proxy_reason(cfg, account_key)

wifi_watchdog が検出した SSID圏外/電源OFF/バックOFF は、ブラウザ起動前に `dead_proxy_reason()` でスキップし、reason=`network_outage_skip` を1行ログに残す（PII/token 出さない）。

### 実測検証

$ python -c "import kensho.core.self_heal, kensho.application.applier, kensho.utils.safety; print('imports OK')"
imports OK
$ timeout 300 python -m pytest tests/test_self_heal.py -q
======================== 30 passed in 132.23s =========================

### 受け入れコミット

- condition 1: commit 4ef200d（failure ceiling の垢粒度化）
- condition 2: commit c147e6b（ネットワーク圏外団スキップ 条件2）
- HEAD: 2e05b42（両コミットは main に包含、未pushコードなし）

t_2bd258d5 は作業完了。早期完了（early_complete: commit 2e05b42 pre-existing）。