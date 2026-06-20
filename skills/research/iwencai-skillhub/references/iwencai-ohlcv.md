# 问财批量 OHLCV 同步 — 完整模板 + 8 个关键坑点

## 用法
一次性拉取所有自选股的当日完整 OHLCV（开盘/最高/最低/收盘/成交量/涨跌幅），写入 `daily_kline` 表。

## 完整脚本模板

```python
#!/usr/bin/env python3
"""问财批量拉全量 OHLCV + 涨跌幅，每批 10-15 只"""
import os, json, secrets, requests, sqlite3, time

# 1. 从 .env 读 API Key（不是环境变量，Hermes 会遮蔽 terminal exports）
key = ''
with open(os.path.expanduser('~/.hermes/.env')) as f:
    for line in f:
        if 'IWENCAI_API_KEY' in line and '=' in line:
            key = line.strip().split('=', 1)[1].strip('"').strip("'")
            break

DB = os.path.expanduser("~/my_quant_system/stock_data.db")
conn = sqlite3.connect(DB)

# 2. 读自选股（覆盖所有分组）
stocks = [r[0] for r in conn.execute(
    "SELECT DISTINCT stock_code FROM watchlist"
).fetchall()]

headers = {
    'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
    'X-Claw-Skill-Id': 'hithink-market-query',
    'X-Claw-Skill-Version': '1.0.0',
}

batch_size = 12  # 推荐 10-15，过大可能触发截断
updated = 0

for i in range(0, len(stocks), batch_size):
    batch = stocks[i:i+batch_size]
    headers['X-Claw-Trace-Id'] = secrets.token_hex(32)

    try:
        resp = requests.post('https://openapi.iwencai.com/v1/query2data',
            json={'query': ','.join(batch) + ' 开盘价 最高价 最低价 收盘价 成交量 涨跌幅',
                  'page': '1', 'limit': '20'},
            headers=headers, timeout=30)

        for row in resp.json().get('datas', []):  # ← 注意：是 datas，不是 data！
            # 3. 代码去后缀
            code = str(row.get('股票代码', '')).replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
            if not code: continue

            o = h = l = c = v = chg = 0.0
            # 4. 字段名用前缀匹配（带日期戳如 收盘价[20260617]）
            for k, val in row.items():
                if val is None: continue
                try:
                    fv = float(val)
                    if '开盘' in k: o = fv
                    elif '最高' in k: h = fv
                    elif '最低' in k: l = fv
                    elif '收盘' in k: c = fv
                    elif '成交' in k: v = fv / 100.0  # ← 5. 成交量：股 → 手，除以 100
                    elif '涨跌幅' in k and '最新' in k: chg = fv
                except: pass

            if c > 0:
                conn.execute("""INSERT OR REPLACE INTO daily_kline
                    (stock_code, date, open, high, low, close, volume, pct_change)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (code, time.strftime('%Y%m%d'), o, h, l, c, v, chg))
                updated += 1

    except Exception as e:
        print(f"  batch {i//batch_size+1}: {e}")

    time.sleep(0.3)  # 6. 请求间隔 0.3-0.5s，避免限流

conn.commit()
conn.close()
```

## 8 个关键坑点

### 1. 数据在 `datas` 不在 `data`
响应的实际数据在 `resp.json()['datas']`（复数），访问 `['data']` 会返回 `None`。
```python
rows = resp.json().get('datas', [])  # ✅
rows = resp.json().get('data', [])   # ❌ 永远是空
```

### 2. 股票代码带后缀
返回的代码是 `000988.SZ` / `600519.SH` / `830799.BJ` 格式，写入 SQLite 前必须 strip。
```python
code = raw_code.replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
```

### 3. 字段名带日期戳
动态字段如 `收盘价[20260617]` 随日期变化，不能用硬编码 key 名。
```python
for k, val in row.items():
    if '收盘' in k: c = val   # ✅ 前缀匹配
    # c = row['收盘价[20260617]']  # ❌ 日期变化就失效
```

### 4. 批大小限制
单批超过 30 只代码可能触发 API 截断或异常响应。推荐 10-15 只/批。

### 5. 成交量单位：股 → 手
问财返回的成交量单位是**股**，`daily_kline` 存的是**手**（1手=100股）。
```python
volume_hands = float(val) / 100.0
```

### 6. ETF 特殊处理
问财对 ETF（159xxx、51xxxx、58xxxx）可能不返回 `股票代码` 字段或名称字段。
降级到腾讯 API：`https://qt.gtimg.cn/q=sh{code}` / `sz{code}`（51/58/5开头用 sh，15/16开头用 sz）。

### 7. API Key 读取方式
Hermes 的 `terminal` 工具会遮蔽环境变量（`export IWENCAI_API_KEY=***`）。
必须从文件读取：
```python
with open(os.path.expanduser('~/.hermes/.env')) as f:
    for line in f:
        if 'IWENCAI_API_KEY' in line:
            key = line.strip().split('=', 1)[1].strip('"').strip("'")
```

### 8. INSERT OR REPLACE 需要主键
`daily_kline` 的主键是 `(stock_code, date)`，用 `INSERT OR REPLACE` 可原子覆盖。
但 ETF 代码可能问财没返回 → 降级到腾讯 API 时需确保 code 正确匹配。
