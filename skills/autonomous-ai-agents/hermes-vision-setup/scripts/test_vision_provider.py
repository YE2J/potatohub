#!/usr/bin/env python3
"""Test whether a provider model can read images (esp. Chinese OCR).

Usage:
    python test_vision_provider.py --url https://api.example.com/v1/chat/completions \
        --key-env NVIDIA_API_KEY --model meta/llama-3.2-90b-vision-instruct

    # env key is read from ~/.hermes/.env automatically (never passed on CLI)
    # repeat --url/--key-env/--model triplets to test several candidates at once

Generates an 900x320 test image containing English + Chinese text rendered with
the macOS PingFang font (PIL's default font CANNOT render CJK — see SKILL.md
pitfall #1), base64-inlines it, and asks the model to transcribe every line.
"""
import argparse, base64, io, json, os, sys, urllib.request

# PIL from Hermes venv is often broken (cannot import '_imaging') — use a clean
# venv by pointing sys.path at it, e.g. sys.path.insert(0, "/tmp/vt_venv/lib/python3.11/site-packages")
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
]

TEST_LINES = [
    "Hermes Vision Test 12345",
    "A股量化 测试图片 300338",
    "DeepSeek 主力模型 视觉辅助",
]


def make_test_image() -> str:
    font_path = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
    font = ImageFont.truetype(font_path, 36) if font_path else ImageFont.load_default()
    img = Image.new("RGB", (900, 320), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(TEST_LINES):
        d.text((30, 60 + 80 * i), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def load_env() -> dict:
    env = {}
    with open(os.path.expanduser("~/.hermes/.env")) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def chat(url: str, key: str, model: str, b64: str, timeout: int = 90) -> str:
    body = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": "请逐行转录这张图片里的所有文字（中文+英文+数字都要），不要遗漏。"},
            ],
        }],
        "max_tokens": 300,
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
        return d["choices"][0]["message"]["content"].strip()[:300]
    except Exception as e:
        return f"ERROR: {str(e)[:150]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", action="append", required=True, help="chat completions URL")
    ap.add_argument("--key-env", action="append", required=True, help="env var name holding the API key")
    ap.add_argument("--model", action="append", required=True, help="model id")
    args = ap.parse_args()
    assert len(args.url) == len(args.key_env) == len(args.model), "must pass equal triplets"

    env = load_env()
    b64 = make_test_image()
    for url, key_env, model in zip(args.url, args.key_env, args.model):
        key = env.get(key_env, "")
        print(f"\n{'='*20} {key_env}/{model} {'='*20}")
        if not key:
            print("ERROR: env var not found")
            continue
        print(chat(url, key, model, b64))


if __name__ == "__main__":
    main()
