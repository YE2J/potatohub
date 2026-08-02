# Sina Finance Free Index API

Free real-time A-share index quotes from Sina Finance. Requires no API key.

## Endpoint

```
GET https://hq.sinajs.cn/list=<codes>
```

## Required Headers

| Header | Value | Purpose |
|--------|-------|---------|
| `User-Agent` | `Mozilla/5.0` | Anti-block |
| `Referer` | `https://finance.sina.com.cn` | Anti-leech (Sina blocks direct curl/wget) |

Without both headers the request is rejected or empty.

## Code Format

Prefix each code with `s_`:

| Code | Index | Prefix |
|------|-------|--------|
| `s_sh000001` | 上证指数 | `s_` + Shanghai prefix |
| `s_sz399001` | 深证成指 | `s_` + Shenzhen prefix |
| `s_sz399006` | 创业板指 | `s_` |
| `s_sh000688` | 科创50 | `s_` |
| `s_sh000300` | 沪深300 | `s_` |

Full URL: `https://hq.sinajs.cn/list=s_sh000001,s_sz399001,s_sz399006,s_sh000688`

## Response Format

```
var hq_str_s_sh000001="上证指数,最新价,涨跌,涨跌幅%,成交额(万元),成交量(手),...";
var hq_str_s_sz399001="深证成指,最新价,涨跌,涨跌幅%,成交额(万元),成交量(手),...";
```

JS variable assignment per line, one per requested code. Data inside double quotes, comma-separated:

| Field | Index | Example |
|-------|-------|---------|
| Name | 0 | `上证指数` |
| Current price | 1 | `4028.3681` |
| Change | 2 | `-0.5357` |
| Change % | 3 | `-0.01` (already percentage, no `/100` needed) |
| Volume (万元) | 4 | `0` (0 outside trading hours) |
| Volume (手) | 5 | `0` |

## Encoding

Sina returns data in **GBK** encoding (not UTF-8). Chinese index names will decode incorrectly if treated as UTF-8.

### Python: `subprocess.run` with encoding

```python
import subprocess

result = subprocess.run(
    ["curl", "-s", "--max-time", "5",
     "-H", "User-Agent: Mozilla/5.0",
     "-H", "Referer: https://finance.sina.com.cn",
     "https://hq.sinajs.cn/list=s_sh000001,s_sz399001,s_sz399006,s_sh000688"],
    capture_output=True, text=True, encoding="gbk", timeout=10
)
```

### Python: Manual decode

```python
result = subprocess.run(["curl", "-s", ...], capture_output=True, timeout=10)
raw = result.stdout.decode("gbk")
```

### Parsing

```python
sina_data = {}
for line in result.stdout.strip().split("\n"):
    if "hq_str_" not in line:
        continue
    try:
        fields = line.split('"')[1].split(",")
        if len(fields) >= 4:
            name = fields[0].strip()
            price = fields[1].strip()
            pct_chg = fields[3].strip().replace("%", "")
            if price and pct_chg:
                sina_data[name] = (float(price), float(pct_chg))
    except (IndexError, ValueError):
        pass
```

## Pitfalls

- **GBK encoding**: `subprocess.run(..., text=True)` defaults to UTF-8 and will raise `UnicodeDecodeError` on the Chinese characters. Always pass `encoding="gbk"` or decode manually.
- **Referer required**: Direct curl without `-H "Referer: https://finance.sina.com.cn"` returns empty or times out.
- **Off-hours data**: When markets are closed, some indices return `0.00` for price/change fields while others (上证指数, 科创50) return the last closing data with near-zero change.
- **Rate limiting**: Not documented but keep requests infrequent (one per morning report run).
- **No historical data**: This is a real-time snapshot API only. For historical index data use Tencent API (`tencent_data_api.md`).

## Use Case: Daily Morning Report

This API fills the gap when `index_daily` DB table only has 沪深300. The four major indices (上证指数, 深证成指, 创业板指, 科创50) are not stored in `index_daily` — fetch them from Sina first, fall back to DB only.

Preference order:
1. DB `index_daily` (has pct_chg calculated from prior close) — only 沪深300 available
2. Sina API (real-time) — all major indices
3. Show "数据暂缺" on failure
