# 问财批量行情同步 — 全量 daily_kline 更新模板

## 用途
每日 cron 触发：从问财 API 拉取所有自选股当日 OHLCV，写入 `daily_kline`。

## 部署位置
- 脚本：`~/.hermes/scripts/daily_update_iwencai.py`
- Cron wrapper：`~/.hermes/scripts/daily_update_v2.sh`（一行 exec 指向上述脚本）
- Cron job：Hermes cron `fda7975b8524`，每日 00:00

## 脚本

```python
#!/usr/bin/env python3
"""每日行情更新 — 用问财 OpenAPI"""
import os, json, secrets, requests, sqlite3, time

key = ''
with open(os.path.expanduser('~/.hermes/.env')) as f:
    for line in f:
        if 'IWENCAI_API_KEY' in line and '=' in line:
            key = line.strip().split('=', 1)[1].strip('"').strip("'")
            break

DB = os.path.expanduser("~/my_quant_system/stock_data.db")
conn = sqlite3.connect(DB)

# 覆盖所有分组（不限于 default）
stocks = [r[0] for r in conn.execute(
    "SELECT DISTINCT stock_code FROM watchlist"
).fetchall()]

headers = {
    'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
    'X-Claw-Skill-Id': 'hithink-market-query',
    'X-Claw-Skill-Version': '1.0.0',
}

print(f"📊 每日行情更新 | {len(stocks)} 只")
updated = ok = 0
batch_size = 15

for i in range(0, len(stocks), batch_size):
    batch = stocks[i:i+batch_size]
    headers['X-Claw-Trace-Id'] = secrets.token_hex(32)
    try:
        resp = requests.post('https://openapi.iwencai.com/v1/query2data',
            json={'query': ','.join(batch)+' 开盘价 最高价 最低价 收盘价 成交量 涨跌幅',
                  'page': '1', 'limit': '20'},
            headers=headers, timeout=30)

        for row in resp.json().get('datas', []):
            code = str(row.get('股票代码','')).replace('.SZ','').replace('.SH','').replace('.BJ','')
            if not code: continue

            o = h = l = c = v = chg = 0.0
            for k, val in row.items():
                if val is None: continue
                try:
                    fv = float(val)
                    if '开盘' in k: o = fv
                    elif '最高' in k: h = fv
                    elif '最低' in k: l = fv
                    elif '收盘' in k: c = fv
                    elif '成交' in k: v = fv / 100.0
                    elif '涨跌幅' in k: chg = fv
                except: pass

            if c > 0:
                today = time.strftime('%Y%m%d')
                conn.execute("""INSERT OR REPLACE INTO daily_kline
                    (stock_code,date,open,high,low,close,volume,pct_change)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (code, today, o, h, l, c, v, chg))
                ok += 1
            updated += 1
        time.sleep(0.3)
    except Exception as e:
        print(f"  batch {i//batch_size+1}: {e}")

conn.commit()
conn.close()
print(f"✅ {ok} 只完整OHLCV / {updated} 总处理")
```

## Cron wrapper

```bash
#!/bin/bash
cd ~/my_quant_system
exec ~/my_quant_system/.venv/bin/python3 ~/.hermes/scripts/daily_update_iwencai.py
```

## 增强功能（2026-06-20）

脚本已升级到 v3，新增以下能力：

### 1. 问财 → 腾讯 API 自动降级
问财 OpenAPI 调用失败（HTTP 错误 / 数据缺失）时，自动降级到腾讯 `qt.gtimg.cn` API：
- 问财返回的 `datas` 为空或某只股票无数据 → 该股自动走腾讯
- 问财 HTTP 请求异常 → 整批次降级到腾讯

### 2. 昨日数据缺口检测与回补
启动时自动检查 `daily_kline` 表昨日数据完整性：
- 对比 `watchlist` 股票数与昨日 `daily_kline` 行数
- 缺口 > 0 时，自动通过腾讯 API 回补昨日缺失数据
- 不阻塞今日数据拉取

### 3. 腾讯 API 格式
- URL: `http://qt.gtimg.cn/q=sh600519,sz000001`
- 编码: GBK（需 `decode('gbk')`）
- 字段: 名称[1] 代码[2] 最新价[3] 昨收[4] 今开[5] 成交量手[6] 涨跌额[31] 涨跌幅%[32] 最高[33] 最低[34] 成交额万[37] 换手率[38] 振幅[43]
- 成交量已是"手"单位，无需换算

### 4. 命令行
```
python3 daily_update_iwencai.py           # 正常更新
python3 daily_update_iwencai.py --help    # 帮助
python3 daily_update_iwencai.py --dry-run # 只检测不写入
```

### 5. Exit Code
- 0: 成功（含部分成功）
- 1: 配置错误
- 2: 无数据写入
- 3: 全部失败

## 旧方案（已废弃）
旧 cron 用 akshare `StockDataManager.update_data()`，本机频繁 `Connection aborted` 不可用。
