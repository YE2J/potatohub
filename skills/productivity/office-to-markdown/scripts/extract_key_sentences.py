#!/usr/bin/env python3
"""
extract_key_sentences — 从 markdown 文本提取"关键数据句"（含数字+领域词）。

用途：批量研报/长文档分析时，先抽关键句再写 report，省 token 且不漏核心数据。
实测（2026-08-22 国信研报 6 篇）：单篇 22-50K 字符可抽 3-156 句关键数据。

用法:
  python3 extract_key_sentences.py <file.md> [--top N] [--min-len 20] [--max-len 300]
输出: 每句一行，按出现顺序（默认），--top 只显示前 N 句。
"""
import re
import sys
from pathlib import Path

# 领域词（可自行扩展）：命中即认为该句与量化/财务内容相关
DEFAULT_KEYWORDS = (
    r"收益|胜率|超额|净值|回撤|夏普|年化|换手|IC|因子|组合|样本|策略|模型|基准|"
    r"跑赢|跑输|聚类|模式|信号|估值|PE|PB|ROE|EPS|资金|行业|指数|权重|评级|"
    r"预测|增速|增长|净利|营收|仓位|波动|成交|涨停|跌停"
)

# 数字模式：百分比 / 小数 / 大数（支持带逗号千分位）
NUM_PATTERN = re.compile(r"\d+(\.\d+)?%|\d+\.\d+|\d{3,}(,\d{3})*|\d+")


def clean_text(text: str) -> str:
    """去封面噪声行（markitdown 的 Page/金融工程研究/孤立表格线）。"""
    lines = []
    for ln in text.split("\n"):
        if re.match(r"^\s*\|?\s*$", ln):
            continue
        if "Page" in ln and len(ln) < 40:
            continue
        if "金融工程研究" in ln and len(ln) < 60:
            continue
        if re.match(r"^\s*\|", ln) and len(ln) < 90:
            continue
        lines.append(ln)
    return "\n".join(lines)


def extract_key_sentences(
    text: str,
    keywords: str = DEFAULT_KEYWORDS,
    min_len: int = 20,
    max_len: int = 300,
    top: int | None = None,
) -> list[str]:
    """返回含数字+领域词的句子列表，去重保序。"""
    t = clean_text(text)
    kw_re = re.compile(keywords)
    sents = re.split(r"[。；\n]", t)
    hits, seen = [], set()
    for s in sents:
        s = s.strip()
        if len(s) < min_len or len(s) > max_len:
            continue
        if not NUM_PATTERN.search(s) or not kw_re.search(s):
            continue
        key = s[:40]
        if key in seen:
            continue
        seen.add(key)
        hits.append(s)
    return hits[:top] if top else hits


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = Path(sys.argv[1])
    top = None
    min_len, max_len = 20, 300
    if "--top" in sys.argv:
        top = int(sys.argv[sys.argv.index("--top") + 1])
    if "--min-len" in sys.argv:
        min_len = int(sys.argv[sys.argv.index("--min-len") + 1])
    if "--max-len" in sys.argv:
        max_len = int(sys.argv[sys.argv.index("--max-len") + 1])

    text = path.read_text(encoding="utf-8")
    hits = extract_key_sentences(text, min_len=min_len, max_len=max_len, top=top)
    print(f"# {path.name}: {len(hits)} 句关键数据")
    for s in hits:
        print(f"• {s[:260]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
