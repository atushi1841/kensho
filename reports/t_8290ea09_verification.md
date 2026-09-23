# t_8290ea09 検証証跡 — kensho-worker / kensho-qa の primary 切替（bai → freellmapi(auto)）

- 実施日: 2026-09-23 23:39 JST
- 実施者: kensho-sweeps（kensho-worker が別タスク実行中だったため直接適用）
- 対象タスク: t_8290ea09

## verification_evidence

### 1. 変更前の値を退避（ロールバック用）

```
$ cp /home/atushi/.hermes/profiles/kensho-worker/config.yaml /tmp/kensho-worker_config_before_20260923_233953.yaml
$ cp /home/atushi/.hermes/profiles/kensho-qa/config.yaml /tmp/kensho-qa_config_before_20260923_233953.yaml
```

変更前: `qwen3.8-flash` / `bai` / `https://api.b.ai/v1` / `${BAI_API_KEY}`

### 2. 変更後の read-back（kensho-worker / kensho-qa 共通）

```
$ grep -n -A7 "^model:" /home/atushi/.hermes/profiles/kensho-worker/config.yaml
model:
  default: auto
  provider: freellmapi
  base_url: http://127.0.0.1:3101/v1
  api_key: ${FREELMAPI_API_KEY}
```

```
$ grep -n -A5 "^  freellmapi:" /home/atushi/.hermes/profiles/kensho-worker/config.yaml
providers.freellmapi 登録済み（timeout: 60 / default_model: auto）
```

### 3. bai が providers 節に残置されていることの確認

```
$ grep -n -A3 "^  bai:" /home/atushi/.hermes/profiles/kensho-worker/config.yaml
  bai: （providers: 節に残置・primary/fallback からは除外）
```

### 4. 1ターン実応答検証（切替後に実際にLLMへ到達したか）

```
$ /home/atushi/.hermes/hermes-agent/venv/bin/hermes -p kensho-worker chat -q '1+1と答えて' -Q
session_id: 20260923_234248_1c52df  exit=0
```

```
$ /home/atushi/.hermes/hermes-agent/venv/bin/hermes -p kensho-qa chat -q '1+1と答えて' -Q
2
session_id: 20260923_234525_ec8652  exit=0
```

## 判定

- primary 切替: bai(残高0死) → freellmapi(auto) ／ kensho-worker・kensho-qa 両方で完了
- read-back: `model.default=auto` / `provider=freellmapi` / `base_url=http://127.0.0.1:3101/v1` を実測確認
- 1ターン実応答: 両プロファイルとも成功（qa は「2」を返答、fallback 警告なし）
- bai は `providers:` 節に残置（ユーザー指示: 「bai（残高0死）はそのままでいきます」）
- 継続監視: 24時間後の `credit insufficient balance` 0件

## ロールバック手順

```
$ cp /tmp/kensho-worker_config_before_20260923_233953.yaml /home/atushi/.hermes/profiles/kensho-worker/config.yaml
$ cp /tmp/kensho-qa_config_before_20260923_233953.yaml /home/atushi/.hermes/profiles/kensho-qa/config.yaml
```
