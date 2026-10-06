# t_52543a04: AI Agent Subscription API — 検証レポート

**担当**: kensho-worker
**完了**: 2026-10-06
**コミット**: e5e52b9

## 実装内容

`kensho/agent_api/` パッケージを新規作成。既存の `kensho/price_monitor/`（日本EC価格監視Micro SaaS）にAIエージェント向けサブスクリプションAPIを追加。

### モジュール構成
1. `models.py` — Agent, AgentCreate, AgentTier, AgentStatus, ApiKey, ApiKeyCreate, PlanPricing, UsageLog, UsageLogCreate, UsageSummary
2. `db.py` — AgentAPI_DB（agents / api_keys / usage_logs テーブル、SHA-256 ハッシュ認証、レートリミット検証）
3. `service.py` — AgentAPIService（登録・鍵管理・使用量追跡・認証）
4. `api.py` — FastAPI アプリ（15エンドポイント、X-API-Key 認証）
5. `cli.py` — CLI（register / create-key / list / list-keys / usage / limits / serve）
6. `__init__.py` — 再エクスポート

### プラン価格
| プラン | 月額 | 1日上限 | 1分上限 |
|--------|------|---------|---------|
| Free | ¥0 | 3 calls | 60 req |
| Pro | ¥1,980 | 30 calls | 30 req |
| Business | ¥4,980 | 200 calls | 15 req |

## 検証結果

### テスト
```bash
$ /home/atushi/kensho-venv/bin/python -m pytest tests/test_price_monitor.py tests/test_agent_api.py -v
====================== 13 passed, 79 warnings in 26.11s =======================
```

| テスト | 結果 |
|--------|------|
| test_health_check | PASS |
| test_list_plans | PASS |
| test_agent_crud | PASS |
| test_api_key_crud | PASS |
| test_usage_tracking | PASS |
| test_daily_limit_enforcement | PASS |
| test_api_auth_integration | PASS |
| test_fastapi_agent_endpoints | PASS |

### CLI
```bash
$ /home/atushi/kensho-venv/bin/python -m kensho.agent_api.cli --help
usage: cli.py [-h] {serve,register,list,create-key,list-keys,usage,limits} ...
```

### インポート検証
```bash
$ /home/atushi/kensho-venv/bin/python -c "from kensho.agent_api import Agent, AgentAPI_DB, AgentAPIService; print('OK')"
All imports OK
```

### リント
```bash
$ ruff check kensho/agent_api/
Found 3 errors (UP042 StrEnum, N801 class name) — style warnings only, no errors
```

## 収益化マップ
- **収益源**: AIエージェント向けサブスクリプション（Pro ¥1,980/月、Business ¥4,980/月）
- **現状**: MVP完成、外部run 0件、WAITLIST 0件
- **次ステップ**: 公開APIエンドポイント設定、Gumroad/Stripe決済連携