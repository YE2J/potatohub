#!/usr/bin/env python3
"""批量 book_library 入库同步脚本（office-to-markdown 批量模式辅助，v2.5.1）。

用法:
  python3 book_library_sync.py --src-dir <文档源目录> --manifest books.json

manifest JSON（list）:
  [{"name":"可读目录名","short":"国信42","title":"国信42：...","author":"...",
    "pages":29,"img":37,"note":"# 学习笔记\n- ..."}]

行为（每本）:
  ~/book_library/<name>/ 下建 images/，从 --src-dir 复制 <name>.pdf（原文件）、
  <name>.md（→ <short>.md）、images/，写 meta.json + <short>.note.md；
  幂等插入 ~/book_library/INDEX.md 表格（已有同名行跳过，表格末尾、首个 ## 之前插入）。
"""
import argparse
import json
import shutil
from pathlib import Path

HOME = Path.home()
BL = HOME / "book_library"


def sync_one(entry: dict, src_dir: Path, existing_names: set) -> str | None:
    name = entry["name"]
    if name in existing_names:
        return f"⏭️  {name}: INDEX 已有同名，跳过"
    d = BL / name
    d.mkdir(parents=True, exist_ok=True)
    imgs = d / "images"
    imgs.mkdir(exist_ok=True)
    # 原文件 + md 转换 + images
    src_pdf = src_dir / f"{name}.pdf"
    if src_pdf.exists():
        shutil.copy(src_pdf, d / src_pdf.name)
    src_md = src_dir / f"{name}.md"
    if src_md.exists():
        shutil.copy(src_md, d / f'{entry["short"]}.md')
    src_imgs = src_dir / name / "images"
    if src_imgs.exists():
        for p in src_imgs.glob("*"):
            shutil.copy(p, imgs / p.name)
    # meta.json
    meta = {
        "title": entry["title"], "author": entry["author"],
        "publisher": entry.get("publisher", "国信证券经济研究所"),
        "format": entry.get("format", "pdf"), "pages": entry["pages"],
        "downloaded_at": entry.get("date", "2026-08-22"), "source": entry.get("source", "zlibrary"),
        "converted_by": entry.get("converted_by", "markitdown"),
        "image_count": entry["img"], "note_status": "已学习",
        "related_skills": entry.get("related_skills", []),
    }
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / f'{entry["short"]}.note.md').write_text(entry["note"], encoding="utf-8")
    return f"✅ {name}: images={len(list(imgs.glob('*')))}"


def update_index(new_rows: list[str]) -> int:
    index_path = BL / "INDEX.md"
    lines = index_path.read_text(encoding="utf-8").splitlines() if index_path.exists() else []
    anchor = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
    existing = {ln.split("|")[1].strip() for ln in lines if ln.startswith("|") and "|" in ln[1:]}
    added = 0
    out = lines[:anchor]
    for r in new_rows:
        nm = r.split("|")[1].strip()
        if nm not in existing:
            out.append(r)
            added += 1
    out.extend(lines[anchor:])
    index_path.write_text("\n".join(out), encoding="utf-8")
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-dir", required=True)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()
    src_dir = Path(args.src_dir)
    entries = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    index_path = BL / "INDEX.md"
    existing = {ln.split("|")[1].strip() for ln in index_path.read_text(encoding="utf-8").splitlines()
                if ln.startswith("|") and "|" in ln[1:]} if index_path.exists() else set()
    rows = []
    for e in entries:
        msg = sync_one(e, src_dir, existing)
        print(msg)
        if msg.startswith("✅"):
            rows.append(f"| {e['name']} | {e['author']} | pdf | 已学习 | {e.get('date','2026-08-22')} | {e['name']} |")
    added = update_index(rows)
    print(f"INDEX.md +{added} 行")


if __name__ == "__main__":
    main()
