"""
collect_csrc.py — CSRC 行政处罚决定书采集脚本

架构：
  - 列表页：Selenium（必须，JS 渲染）
  - 详情页：requests + BeautifulSoup（纯 HTTP）
  - 频率控制：详情页间 ≥ 5s，翻页 ≥ 10s
  - 紧急熔断：连续错误 / 反爬信号 → 立即停止

依赖：pip install selenium beautifulsoup4 requests lxml

用法：
    python collect_csrc.py --max-pages 5 --max-daily 200

环境要求：
    - Chrome + Chromedriver（版本匹配）
    - Python 3.8+（推荐 ~/.hermes/python-standalone/bin/python3）
"""

import os
import re
import csv
import time
import random
import hashlib
import argparse
from datetime import datetime, date
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException


# ============================================================
# 配置
# ============================================================

# 列表页 URL（参考 GitHub Gist goldluo126）
LIST_URL = (
    "http://www.csrc.gov.cn/csrc/c101925/zfxxgk_zdgk.shtml"
    "?channelid=29ae08ca97d44d6ea365874aa02d44f6"
)

# 存储路径
SAVE_ROOT = os.path.expanduser("~/my_quant_system/case_library")
RAW_HTML_DIR = os.path.join(SAVE_ROOT, "raw_html")
META_CSV = os.path.join(SAVE_ROOT, "meta_all.csv")

# 反爬参数
DETAIL_INTERVAL = (5, 8)      # 详情页间间隔（秒）
PAGE_INTERVAL = (10, 15)      # 翻页间隔（秒）
DAILY_LIMIT = 200             # 单日上限
SESSION_LIMIT_HOURS = 2       # 单次运行上限
BUSINESS_HOURS = (9, 18)      # 运行时间窗口

# HTTP 头
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# ============================================================
# 紧急熔断
# ============================================================

class EmergencyStop(Exception):
    """紧急停止异常"""

class SafetyBreaker:
    def __init__(self):
        self.consecutive_errors = 0
        self.daily_count = 0
        self.start_time = datetime.now()

    def check_response(self, status_code, content=""):
        if status_code in (403, 503):
            self.consecutive_errors += 1
        else:
            self.consecutive_errors = 0

        if self.consecutive_errors >= 3:
            raise EmergencyStop("连续错误 ≥3 次，立即停止")

        if "验证码" in content or "访问过于频繁" in content:
            raise EmergencyStop("检测到反爬验证")

    def check_limits(self):
        self.daily_count += 1
        if self.daily_count >= DAILY_LIMIT:
            raise EmergencyStop(f"达到单日上限 {DAILY_LIMIT} 篇")
        if (datetime.now() - self.start_time).seconds > SESSION_LIMIT_HOURS * 3600:
            raise EmergencyStop(f"达到单次运行上限 {SESSION_LIMIT_HOURS} 小时")

    def check_business_hours(self):
        now = datetime.now()
        if now.weekday() >= 5:  # 周末
            raise EmergencyStop("非工作日，停止运行")
        if now.hour < BUSINESS_HOURS[0] or now.hour >= BUSINESS_HOURS[1]:
            raise EmergencyStop(f"非工作时间（{BUSINESS_HOURS[0]}:00-{BUSINESS_HOURS[1]}:00）")


# ============================================================
# Selenium 配置
# ============================================================

def create_driver():
    """创建反检测 Selenium WebDriver"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")

    w = random.randint(1200, 1400)
    h = random.randint(800, 900)
    options.add_argument(f"--window-size={w},{h}")
    options.add_argument(f"--user-agent={HEADERS['User-Agent']}")

    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


# ============================================================
# 列表页采集
# ============================================================

def fetch_detail_links(driver, url, max_pages=5):
    """
    从列表页提取所有详情页链接
    返回：[{"url": "...", "title": "..."}, ...]
    """
    driver.get(url)
    links = []
    page = 0

    while page < max_pages:
        soup = BeautifulSoup(driver.page_source, "lxml")
        rows = soup.select("#codeId_list > ul > table > tbody > tr")

        for row in rows:
            a_tag = row.find("a", href=True)
            if a_tag:
                href = a_tag["href"]
                if not href.startswith("http"):
                    href = "http://www.csrc.gov.cn" + href
                links.append({
                    "url": href,
                    "title": a_tag.get_text(strip=True)
                })

        try:
            next_btn = driver.find_element(By.LINK_TEXT, "下一页")
            next_btn.click()
            page += 1
            time.sleep(random.uniform(*PAGE_INTERVAL))
        except NoSuchElementException:
            break  # 没有下一页

    return links


# ============================================================
# 详情页采集
# ============================================================

def fetch_detail_content(url, breaker):
    """请求详情页并提取正文"""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    breaker.check_response(resp.status_code, resp.text)
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "lxml")
    detail_div = soup.select_one("div.detail-news")
    if not detail_div:
        return None, resp.text

    text = detail_div.get_text(separator="\n", strip=True)
    return text, resp.text


def extract_metadata(text):
    """从正文提取基本元数据"""
    meta = {}

    # 文号：〔2024〕125号
    m = re.search(r"〔(\d{4})〕(\d+)号", text)
    if m:
        meta["year"] = m.group(1)
        meta["doc_number"] = m.group(0)

    # 罚没金额
    amounts = re.findall(r"(?:罚款|罚没|没收)[^\d]*?([\d,]+(?:\.[\d]+)?)\s*(?:万?元|亿)", text)
    meta["has_amount"] = len(amounts) > 0

    # 时间戳（秒级 HH:MM:SS）
    timestamps = re.findall(r"\d{1,2}:\d{2}:\d{2}", text)
    meta["timestamp_count"] = len(timestamps)
    meta["has_second_timestamps"] = len(timestamps) > 2

    return meta


# ============================================================
# 存储
# ============================================================

def save_raw_html(url, html, meta):
    """保存原始 HTML"""
    os.makedirs(RAW_HTML_DIR, exist_ok=True)
    doc_num = meta.get("doc_number", "unknown")
    safe_name = re.sub(r"[\\/*?:\"<>|〔〕]", "", doc_num)[:60]
    filepath = os.path.join(RAW_HTML_DIR, f"{safe_name}.html")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    return filepath


def append_meta_csv(url, title, meta, html_path, text_path=""):
    """追加元数据到 CSV"""
    file_exists = os.path.exists(META_CSV)
    with open(META_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "url", "title", "doc_number", "year",
                "has_amount", "timestamp_count", "has_second_timestamps",
                "html_path", "text_path", "collected_at"
            ])
        writer.writerow([
            url, title,
            meta.get("doc_number", ""),
            meta.get("year", ""),
            meta.get("has_amount", False),
            meta.get("timestamp_count", 0),
            meta.get("has_second_timestamps", False),
            html_path, text_path,
            datetime.now().isoformat()
        ])


# ============================================================
# URL 去重
# ============================================================

def load_known_urls():
    """从已有 CSV 加载已采集 URL"""
    if not os.path.exists(META_CSV):
        return set()
    known = set()
    with open(META_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            known.add(row.get("url", ""))
    return known


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="CSRC 处罚决定书采集")
    parser.add_argument("--max-pages", type=int, default=5, help="最大翻页数")
    parser.add_argument("--max-daily", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true", help="仅列出 URL，不下载")
    args = parser.parse_args()

    breaker = SafetyBreaker()

    # 检查时间窗口
    try:
        breaker.check_business_hours()
    except EmergencyStop as e:
        print(f"[停止] {e}")
        return

    # 加载已知 URL
    known_urls = load_known_urls()
    print(f"已知 URL: {len(known_urls)} 条")

    # 获取列表页链接
    print("启动 Selenium 获取列表页...")
    driver = create_driver()
    try:
        all_links = fetch_detail_links(driver, LIST_URL, max_pages=args.max_pages)
    finally:
        driver.quit()

    # 去重
    new_links = [l for l in all_links if l["url"] not in known_urls]
    print(f"列表页共 {len(all_links)} 条，新发现 {len(new_links)} 条")

    if args.dry_run:
        for l in new_links:
            print(f"  {l['title'][:60]} → {l['url']}")
        return

    # 逐篇下载
    saved = 0
    for i, link in enumerate(new_links):
        if saved >= args.max_daily:
            break

        try:
            breaker.check_limits()

            print(f"[{i+1}/{len(new_links)}] {link['title'][:60]}")
            text, html = fetch_detail_content(link["url"], breaker)

            if text is None:
                print("  → 跳过（无正文）")
                continue

            meta = extract_metadata(text)
            print(f"  文号={meta.get('doc_number','?')} "
                  f"时间戳={meta['timestamp_count']}个 "
                  f"有金额={meta['has_amount']}")

            html_path = save_raw_html(link["url"], html, meta)
            append_meta_csv(link["url"], link["title"], meta, html_path)

            saved += 1

            # 间隔
            if i < len(new_links) - 1:
                delay = random.uniform(*DETAIL_INTERVAL)
                time.sleep(delay)

        except EmergencyStop:
            print("[紧急停止]")
            break
        except Exception as e:
            print(f"  错误: {e}")
            continue

    print(f"\n完成。本次采集 {saved} 篇，存储于 {SAVE_ROOT}/")


if __name__ == "__main__":
    main()
