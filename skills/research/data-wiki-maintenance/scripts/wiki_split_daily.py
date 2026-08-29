#!/usr/bin/env python3
"""wiki_split_daily.py — 将 wiki 大概念页按日期段落拆分为日切片 + _latest.md 指针
处理: concepts/每日盘面.md, concepts/资金流追踪.md, concepts/估值动态.md
用法: python3 wiki_split_daily.py  (先备份 wiki 目录)
"""
import os, re

WIKI = os.path.expanduser("~/.hermes/wiki")

# 每个页面: (源文件, 目标目录, 页面标题, tags)
PAGES = [
    ("concepts/每日盘面.md",  "concepts/每日盘面",  "每日盘面",  "stock, technical, fund-flow"),
    ("concepts/资金流追踪.md", "concepts/资金流追踪", "资金流追踪", "stock, fund-flow"),
    ("concepts/估值动态.md",  "concepts/估值动态",  "估值动态",  "valuation"),
]

DATE_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})")

def split_page(src_rel, dst_dir, title, tags):
    src = os.path.join(WIKI, src_rel)
    with open(src, encoding="utf-8") as f:
        lines = f.readlines()

    # 找 frontmatter 结束 (---)
    fm_end = 0
    if lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end = i + 1
                break

    # 找所有日期标题行号
    date_marks = []
    for i, line in enumerate(lines):
        m = DATE_RE.match(line)
        if m:
            date_marks.append((i, m.group(1)))

    if not date_marks:
        print(f"  [SKIP] {src_rel}: 无日期段落")
        return

    os.makedirs(os.path.join(WIKI, dst_dir), exist_ok=True)

    created_files = []
    for idx, (start_line, date_str) in enumerate(date_marks):
        end_line = date_marks[idx + 1][0] if idx + 1 < len(date_marks) else len(lines)
        body = "".join(lines[start_line:end_line]).rstrip() + "\n"
        title_line = body.split("\n", 1)[0]
        content = body.split("\n", 1)[1] if "\n" in body else ""
        fm = (
            "---\n"
            f"title: {title} {date_str}\n"
            f"created: {date_str}\n"
            f"updated: {date_str}\n"
            "type: concept\n"
            "category: A股量化\n"
            f"tags: [{tags}]\n"
            "sources: [量化系统/数据管线.md]\n"
            "---\n\n"
            f"# {title_line[3:].strip()}\n"
            f"{content}"
        )
        out = os.path.join(WIKI, dst_dir, f"{date_str}.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write(fm)
        created_files.append((date_str, out))

    # _latest.md = 最新一天的完整内容 (供快速读取)
    latest_date, latest_file = created_files[-1]
    with open(latest_file, encoding="utf-8") as f:
        latest_content = f.read()
    latest_md = os.path.join(WIKI, dst_dir, "_latest.md")
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(latest_content)
    created_files.append(("_latest", latest_md))

    # 源文件移到 _archive/ 保留
    arch_dir = os.path.join(WIKI, "_archive")
    os.makedirs(arch_dir, exist_ok=True)
    arch = os.path.join(arch_dir, os.path.basename(src_rel))
    os.rename(src, arch)

    print(f"  [OK] {src_rel}: {len(date_marks)} 天 → {dst_dir}/  (最新={latest_date}, 原文件→_archive/)")

def main():
    for src, dst, title, tags in PAGES:
        split_page(src, dst, title, tags)
    print("完成")

if __name__ == "__main__":
    main()
