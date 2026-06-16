# 腾讯 API 数据增量更新

## 数据源

Tencent Finance API（已验证可用）：`https://ifzq.gtimg.cn/appstock/app/fqkline/get`

## 参数格式

```
param={sz|sh}{code},day,{start_date},{end_date},{max_records},
```

- 市场前缀：`sh`（6/5/8/9 开头）或 `sz`（0/1/2/3 开头）
- 日期格式：`YYYY-MM-DD`
- `max_records`：最大返回条数（建议 500）
- 末尾逗号后不加 qfq 返回未复权 `day` 数据，加 `qfq` 返回前复权 `qfqday` 数据

## 响应格式

```json
{
  "code": 0,
  "msg": "",
  "data": {
    "sz000001": {
      "day": [
        ["2025-01-02", "10.50", "10.80", "10.30", "10.60", "1000000.000"],
        ...
      ],
      "qfqday": [
        // 仅当请求含 qfq 时存在
      ]
    }
  }
}
```

每行格式：`[日期, 开盘, 收盘, 最高, 最低, 成交量, (可选分红除权字典)]`

> **注意**：部分行包含第 7 个字段，值为 dict（分红除权信息）。处理时取前 6 个字段即可。

## 增量更新策略

### no_agent cronjob 模式

使用 Hermes cronjob 的 `no_agent=True` 模式运行数据下载脚本：

- **stdout 为空** → 不推送（无新数据时静默）
- **stdout 非空** → 推送内容作为消息
- **非零 exit code** → 推送错误警报

### 脚本模板

```python
# 核心逻辑
for stock in watchlist:
    max_date = db.execute("SELECT MAX(date) FROM daily_kline WHERE stock_code=?", (code,)).fetchone()
    if max_date >= today:
        continue  # 已是最新
    data = fetch_tencent(code, start_date, today)
    for _, row in data.iterrows():
        db.execute("INSERT OR IGNORE INTO daily_kline (...) VALUES (...)")
```

### 请求间隔
每只股票之间至少间隔 0.12 秒，防止 API 限流。104 只股票约需 30 秒。
