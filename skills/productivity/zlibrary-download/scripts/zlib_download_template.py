#!/usr/bin/env python3
"""
Z-Library 批量下载模板（无凭据版，供复制使用）。
与工作脚本 ~/.hermes/scripts/zlib_download_guoxin.py 同构，但：
  - 凭据用环境变量占位（绝不硬编码真实账号）
  - BOOKS 需按需填写（id/hash 来自 MCP search_books 返回）
用法:
  python3 zlib_download_template.py [--check] [--books-file books.json]
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

PKG = Path.home() / ".npm-global/lib/node_modules/zlibrary-mcp"
sys.path.insert(0, str(PKG / "zlibrary/src"))

from zlibrary.eapi import EAPIClient, resolve_eapi_domain  # noqa: E402

# ── 凭据：环境变量占位，真实值放 ~/.hermes/scripts/ 工作副本（chmod 600）──
EMAIL = os.getenv("ZLIB_EMAIL", "YOUR_EMAIL")
PASSWORD = os.getenv("ZLIB_PASSWORD", "YOUR_PASSWORD")
OUTDIR = Path(os.getenv("ZLIB_OUTDIR", str(Path.home() / "Downloads/书库")))

# ── 书单：默认空，用 --books-file 传入 ──
DEFAULT_BOOKS: list[dict] = []


def load_books(books_file: str | None) -> list[dict]:
    if books_file:
        data = json.loads(Path(books_file).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("books", [])
    return DEFAULT_BOOKS


async def main(check_only: bool, books_file: str | None):
    books = load_books(books_file)
    if not books:
        print("⚠️ 书单为空：用 --books-file 传入 JSON，或编辑 DEFAULT_BOOKS")
        return 1

    domain = await resolve_eapi_domain()
    print(f"[1/3] EAPI 域: {domain}")
    client = EAPIClient(domain)
    result = await client.login(EMAIL, PASSWORD)
    if result.get("success") != 1:
        print(f"❌ 登录失败: {result.get('error', result)}")
        return 1
    print(f"[2/3] 登录成功 userid={client.remix_userid}")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    ok, blocked, skipped = 0, 0, 0
    for b in books:
        bid, bhash, fname = b["id"], b["hash"], b["filename"]
        out = OUTDIR / fname
        # 断点续传：已存在且像 PDF → 跳过
        if out.exists() and out.stat().st_size > 100_000:
            r = subprocess.run(["file", str(out)], capture_output=True, text=True)
            if "PDF document" in r.stdout:
                print(f"   ⏭️  {fname}: 已存在且为 PDF，跳过")
                skipped += 1
                continue

        dl = await client.get_download_link(int(bid), bhash)
        allow = dl.get("file", {}).get("allowDownload")
        if allow is not True:
            msg = dl.get("file", {}).get("disallowDownloadMessage", "")
            print(f"   ⛔ {fname}: 配额未重置 ({msg[:60]}...)")
            blocked += 1
            continue
        try:
            await client.download_file(int(bid), bhash, str(OUTDIR), filename=fname)
        except Exception as e:
            print(f"   ❌ {fname}: {type(e).__name__}: {e}")
            blocked += 1
            continue
        r = subprocess.run(["file", str(out)], capture_output=True, text=True)
        is_pdf = "PDF document" in r.stdout
        print(f"   ✅ {fname}: {out.stat().st_size} bytes, PDF={is_pdf}")
        if is_pdf:
            ok += 1
        else:
            blocked += 1

    await client.close()
    print(f"[3/3] 完成: 成功 {ok}, 失败/受阻 {blocked}, 跳过 {skipped}")
    return 0 if ok == len(books) else (2 if ok > 0 else 1)


if __name__ == "__main__":
    check_only = "--check" in sys.argv
    bf = None
    if "--books-file" in sys.argv:
        bf = sys.argv[sys.argv.index("--books-file") + 1]
    sys.exit(asyncio.run(main(check_only, bf)))
