#!/usr/bin/env python3
"""Probe whether a provider/model accepts image input (OpenAI-compatible chat/completions).

Usage:
  python3 probe_vision_models.py <image.png> [provider] [model]
    provider: xiaomi | deepseek | zai | nvidia   (default: xiaomi)
    model:    defaults per provider — xiaomi: mimo-v2.5, deepseek: deepseek-v4-flash,
              zai: glm-5.2, nvidia: meta/llama-3.2-90b-vision-instruct

Reads API keys from ~/.hermes/.env (XIAOMI_API_KEY / DEEPSEEK_API_KEY /
ZAI_API_KEY or GLM_API_KEY / NVIDIA_API_KEY).

Interpreting results (see skill SKILL.md Step 2):
  - HTTP 400 "unknown variant image_url, expected text"  -> TEXT-ONLY model
  - HTTP 404 "No endpoints found that support image input" -> model has no vision endpoint
  - OK + image_tokens>0                                    -> vision works
  - OK but content empty + finish=length                   -> raise max_tokens (retry with >=2000)
"""
import base64, json, os, sys, time, urllib.request

PROVIDERS = {
    "xiaomi":  {"url": "https://api.xiaomimimo.com/v1", "key": "XIAOMI_API_KEY", "model": "mimo-v2.5"},
    "deepseek": {"url": "https://api.deepseek.com/v1", "key": "DEEPSEEK_API_KEY", "model": "deepseek-v4-flash"},
    "zai":     {"url": "https://api.z.ai/api/paas/v4", "key": "ZAI_API_KEY", "model": "glm-5.2"},
    "nvidia":  {"url": "https://integrate.api.nvidia.com/v1", "key": "NVIDIA_API_KEY", "model": "meta/llama-3.2-90b-vision-instruct"},
}

def load_env():
    env = {}
    p = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def chat(base, key, model, b64, timeout=120):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": "请识别并转录这张图片中的所有文字内容"},
        ]}],
        "max_tokens": 2000,
    }
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
        msg = d["choices"][0]["message"]
        usage = d.get("usage", {})
        img_tok = usage.get("prompt_tokens_details", {}).get("image_tokens")
        return {
            "status": "OK",
            "latency_s": round(time.time() - t0, 1),
            "finish": d["choices"][0].get("finish_reason"),
            "content": (msg.get("content") or "(empty)")[:500],
            "reasoning_len": len(msg.get("reasoning_content") or ""),
            "image_tokens": img_tok,
        }
    except urllib.error.HTTPError as e:
        return {"status": f"HTTP {e.code}", "body": e.read().decode()[:300]}
    except Exception as e:
        return {"status": "ERROR", "body": str(e)[:300]}

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    img_path = sys.argv[1]
    provider = sys.argv[2] if len(sys.argv) > 2 else "xiaomi"
    model = sys.argv[3] if len(sys.argv) > 3 else PROVIDERS[provider]["model"]

    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    E = load_env()
    key = E.get(PROVIDERS[provider]["key"]) or (E.get("GLM_API_KEY") if provider == "zai" else "")
    if not key:
        print(f"ERROR: no key for provider {provider} ({PROVIDERS[provider]['key']})")
        sys.exit(1)

    print(f"== probing {provider}/{model} with {img_path} ==")
    res = chat(PROVIDERS[provider]["url"], key, model, b64)
    for k, v in res.items():
        print(f"  {k}: {v}")
    print("\n结论: ", end="")
    if res["status"] == "OK" and res.get("image_tokens"):
        print("✅ 支持图片识别")
    elif res["status"] == "OK":
        print("⚠️ 200但无image_tokens标记；content为空可能是max_tokens不足")
    elif "404" in res["status"]:
        print("❌ 该模型无图片输入端点")
    elif "400" in res["status"]:
        print("❌ 纯文本模型(400)")
    else:
        print(f"❌ {res['status']}")

if __name__ == "__main__":
    main()
