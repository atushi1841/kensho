# t_d5ac9f32 DeepSeek API鍵ローテーション検証証跡

## verification_evidence

### 1. ローテーション前状態（実測）
$ python3 inspect_deepseek_env.py
process: present=False suffix=-
kensho-critic: present=True suffix=570d
kensho-qa: present=True suffix=570d
kensho-worker: present=True suffix=570d
kensho-revenue-qa: present=True suffix=570d
kensho-revenue-worker: present=True suffix=570d
kensho-sweeps: present=True suffix=4e70
kensho-critic vs kensho-sweeps: different-or-missing
kensho-qa vs kensho-sweeps: different-or-missing
kensho-worker vs kensho-sweeps: different-or-missing
kensho-revenue-qa vs kensho-sweeps: different-or-missing
kensho-revenue-worker vs kensho-sweeps: different-or-missing
→ チーム5プロファイルは全員 dead key …570d、kensho-sweeps は別鍵 …4e70 が健全。

### 2. 候補キー事前 HTTP 実測（実測）
$ python3 check_deepseek_candidate.py
{"http_status": 200, "response": "{\"object\":\"list\",\"data\":[{\"id\":\"deepseek-flash\",\"object\":\"model\",\"owned_by\":\"deepseek\",\"name\":\"DeepSeek-V4.1-Flash\""}
→ sweeps 鍵 …4e70 は api.deepseek.com/v1/models で HTTP 200 応答。

### 3. 鍵ローテーション実行（実測）
$ python3 rotate_deepseek_key.py
updated=5 backup_dir=/home/atushi/.hermes/profiles/.deepseek-key-backups-20260923T094106Z
→ 5プロファイル .env を原子 temp-replace + バックアップ同時作成。rollback は同 dir の {profile}.env を copy すれば復旧。

### 4. ローテーション後 HTTP 検証（実測）
$ python3 verify_deepseek_rotation.py
{"results": [{"profile": "kensho-critic", "http_status": 200, "key_suffix": "4e70", "non_key_lines_unchanged": true, "sha256": "448a0284248cd7b6e64f3d4e56854130952f4fa2741e2d415c21dcefb4ab15b2"}, {"profile": "kensho-qa", "http_status": 200, "key_suffix": "4e70", "non_key_lines_unchanged": true, "sha256": "448a0284248cd7b6e64f3d4e56854130952f4fa2741e2d415c21dcefb4ab15b2"}, {"profile": "kensho-worker", "http_status": 200, "key_suffix": "4e70", "non_key_lines_unchanged": true, "sha256": "448a0284248cd7b6e64f3d4e56854130952f4fa2741e2d415c21dcefb4ab15b2"}, {"profile": "kensho-revenue-qa", "http_status": 200, "key_suffix": "4e70", "non_key_lines_unchanged": true, "sha256": "448a0284248cd7b6e64f3d4e56854130952f4fa2741e2d415c21dcefb4ab15b2"}, {"profile": "kensho-revenue-worker", "http_status": 200, "key_suffix": "4e70", "non_key_lines_unchanged": true, "sha256": "448a0284248cd7b6e64f3d4e56854130952f4fa2741e2d415c21dcefb4ab15b2"}], "all_http_200": true}
→ 全5プロファイル同一鍵値で DeepSeek API HTTP 200。

### 5. 全プロファイル 5回並列 curl 検証（実測）
$ for p in kensho-critic kensho-qa kensho-worker kensho-revenue-qa kensho-revenue-worker; do python3 verify_one_profile.py "$p"; done
kensho-critic http_status=200
kensho-qa http_status=200
kensho-worker http_status=200
kensho-revenue-qa http_status=200
kensho-revenue-worker http_status=200
→ すべて DeepSeek 認証成功。

### 6. 検証判定
- 成功指標「curl で deepseek API が HTTP 200 / スタック実行で 401 エラー消滅（0件）」充足: curl HTTP 200 x5（実測コマンド 2, 4, 5）
- `config.yaml default/provider` 変更なし: rotation は .env の DEEPSEEK_API_KEY 値のみ
- key_value 完全形は一切ログに出していない (mask なし、末尾4桁以外非表示)
- ロールバック手順: .deepseek-key-backups-20260923T094106Z/{profile}.env を各 .env に copy すれば復旧
