import json
import os
import urllib.request

KEY = (
    os.environ.get("BAI_API_KEY")
    or open("/home/atushi/.hermes/profiles/kensho-sweeps/.env").read().split("BAI_API_KEY=")[1].splitlines()[0].strip()
)
BASE = "https://api.b.ai/v1"


def chat(model):
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise assistant. Reply in one short Japanese word."},
            {"role": "user", "content": "元気? 一言で"},
        ],
        "max_tokens": 32,
    }).encode()
    req = urllib.request.Request(
        BASE + "/chat/completions",
        data=body,
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode())
            return d["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return f"ERR {e!r}"


# mask key in any output
safe_key = KEY[:6] + "..." + KEY[-4:]
print("KEY(masked):", safe_key)

for m in ["deepseek-v4-flash", "mimo-v2.5", "hy3", "deepseek-v4-flash-vision-exp", "deepseek-v4-pro"]:
    print("---", m)
    print("   =>", chat(m))
