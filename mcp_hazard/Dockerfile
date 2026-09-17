# MCP Hazard Server — Apify Actor (standby mode)
# ベース: apify/actor-python 3.12 (port 3000 開放, APIFY_CONTAINER_PORT 互換)
FROM apify/actor-python:3.12

# 必要な依存のみ (fastmcpは不使用 — 軽量カスタム実装)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# アプリコード
COPY . actor_code/
WORKDIR /actor_code

# standby MCP ではコンテナが webserver として起動される
# APIFY_CONTAINER_PORT が設定されるため、それで listen する
CMD ["sh", "-c", "uvicorn mcp_hazard.server:app --host 0.0.0.0 --port ${APIFY_CONTAINER_PORT:-8000}"]
