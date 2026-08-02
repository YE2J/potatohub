# 反爬安全策略（政府网站，安全第一）

## 核心原则

> 政府网站（www.csrc.gov.cn），宁可慢十倍，不可封一次。

## 请求频率控制

| 操作 | 最小间隔 | 说明 |
|------|:---:|------|
| 列表页 → 详情页 | ≥ 5 秒 | `time.sleep(random.uniform(5, 8))` |
| 翻页 | ≥ 10 秒 | `time.sleep(random.uniform(10, 15))` |
| 单日总量上限 | ≤ 200 篇 | 达到后自动停止 |
| 单次运行上限 | ≤ 2 小时 | 到时间自动退出 |
| 每天运行次数 | ≤ 1 次 | 不重复跑 |
| 运行时间窗口 | 工作日 9:00-18:00 | 模拟正常办公时间 |

## Selenium 反检测配置

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import random

options = Options()
options.add_argument("--headless")  # 无头模式
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

# 随机化窗口尺寸（模拟真实用户）
width = random.randint(1200, 1400)
height = random.randint(800, 900)
options.add_argument(f"--window-size={width},{height}")

# 通用 User-Agent（不要用 HeadlessChrome 标识）
options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 禁用自动化特征
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--no-sandbox")

driver = webdriver.Chrome(options=options)
# 注入 JS 隐藏 webdriver 属性
driver.execute_script(
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)
```

## 请求头伪装

```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
}
```

## 详情页提取（web_extract，不需要 Selenium）

详情页是纯 HTML，用 `web_extract` 工具即可，**不走 browser**。这有两个好处：
1. 不消耗 Selenium 资源
2. 请求频率更可控

## 紧急熔断机制

| 触发条件 | 动作 | 理由 |
|----------|------|------|
| 连续 3 次 HTTP 403/503 | **立即停止，24 小时内不重试** | 可能触发反爬 |
| 响应时间 > 30秒 × 连续 3 次 | 停止，等人工检查 | 服务器问题或限流 |
| 页面出现"验证码"关键词 | **立即停止，72 小时内不重试** | 已触发反爬验证 |
| 页面出现"访问过于频繁" | **立即停止，72 小时内不重试** | IP 已被标记 |
| 单日已采集 ≥ 200 篇 | 自动停止 | 达到日上限 |

### 熔断代码模板

```python
class SafetyBreaker:
    def __init__(self):
        self.consecutive_errors = 0
        self.daily_count = 0
        self.DAILY_LIMIT = 200
        self.ERROR_THRESHOLD = 3

    def check_response(self, status_code, content):
        if status_code in (403, 503):
            self.consecutive_errors += 1
        else:
            self.consecutive_errors = 0

        if self.consecutive_errors >= self.ERROR_THRESHOLD:
            raise EmergencyStop("连续错误达阈值，24h 内禁止重试")

        if "验证码" in content or "访问过于频繁" in content:
            raise EmergencyStop("检测到反爬验证，72h 内禁止重试")

    def check_daily_limit(self):
        self.daily_count += 1
        if self.daily_count >= self.DAILY_LIMIT:
            raise EmergencyStop("达到单日采集上限")
```

## 代理池 / IP 轮换？

**不建议**。原因：
1. 政府网站通常不封 IP（除非极端频率）
2. 代理池增加延迟和不稳定性
3. 家用宽带 IP 足够，控制频率才是关键

如果未来确实需要：可考虑家庭宽带断线重拨换 IP（PPPoE）。

## 合规提示

- **采集前检查** `www.csrc.gov.cn/robots.txt`
- **仅采集公开的行政处罚决定书**，不碰依申请公开内容
- **仅供个人研究使用**，不公开分发原始数据
- **不修改、不篡改**原文内容
- **敏感信息处理**：身份证号、详细住址等，存储时做标记处理
- 处罚决定书是政府主动公开信息，属于《政府信息公开条例》第十九条规定的公开范围

## 异常处理和重试

```python
MAX_RETRIES = 2  # 最多重试 2 次
RETRY_BACKOFF = [30, 120]  # 重试等待秒数（递增）

def fetch_with_retry(url, breaker):
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            breaker.check_response(resp.status_code, resp.text)
            return resp
        except (RequestException, EmergencyStop):
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF[attempt])
            else:
                raise
```

## 分时段采集建议

```
工作日 9:00-12:00  — 上午窗口
工作日 14:00-18:00 — 下午窗口
─────────────────────────────
非工作日（周末/节假日）— 不运行
```

首次全量回填可以分多天跑，每天 2 小时即可积累可观数量。
