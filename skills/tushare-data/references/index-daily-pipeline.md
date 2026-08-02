# Tushare 指数日线 (index_daily) 增量数据管道

## 接口特征

| 维度 | 值 |
|------|-----|
| **接口名** | `pro.index_daily(ts_code=..., start_date=..., end_date=...)` |
| **最低积分** | 2000（5000 分可用） |
| **单次覆盖** | **1 个指数** × 日期区间（不支持多指数批量） |
| **分钟限频** | 500 次/分钟 |
| **日线更新** | 交易日 17:00~18:00 完成入库 |

### ⚠️ 不支持多代码批量查询

```python
# ❌ 无效：多 ts_code 用逗号拼接返回空结果
pro.index_daily(ts_code='000001.SH,399001.SZ,399006.SZ', start_date='20260702', end_date='20260702')
# → 空 DataFrame

# ✅ 正确：每个指数独立调用
pro.index_daily(ts_code='000001.SH', start_date='20260702', end_date='20260702')
pro.index_daily(ts_code='399001.SZ', start_date='20260702', end_date='20260702')
```

**已验证**（2026-07-03，5000 积分账户）：

| 指数 | 代码 | 状态 |
|------|------|------|
| 上证指数 | `000001.SH` | ✅ 返回 pct_chg/close 正确 |
| 深证成指 | `399001.SZ` | ✅ |
| 创业板指 | `399006.SZ` | ✅ |
| 科创50 | `000688.SH` | ✅ |
| 沪深300 | `000300.SH` | ✅ （已有历史数据） |

## 字段映射（→ index_daily 表）

| 目标 DB 字段 | Tushare 字段 | 转换 |
|------------|-------------|------|
| `ts_code` | `ts_code` | 直接映射 |
| `trade_date` | `trade_date` | YYYYMMDD → YYYY-MM-DD |
| `open` / `high` / `low` / `close` | 同名 | 直接映射（前复权） |
| `pre_close` | `pre_close` | 直接映射 |
| `change` | `change` | 涨跌额（点） |
| `pct_chg` | `pct_chg` | 涨跌幅（%），Tushare 直接返回 |
| `vol` | `vol` | 成交量（手） |
| `amount` | `amount` | 成交额（元） |

### 关键确认

```python
# 单次调用返回 1 行（指定单日）：包含全部字段
pro.index_daily(ts_code='000001.SH', start_date='20260702', end_date='20260702',
                fields='ts_code,trade_date,close,pct_chg,vol,amount')
# → ts_code=000001.SH, trade_date=20260702, close=4028.90, pct_chg=-2.03, vol=656233612, amount=1.577e9
```

## 申万行业指数（801020.SI 等）不可用

```
pro.index_daily(ts_code='801020.SI', start_date='20260701', end_date='20260702')
# → 空 DataFrame
```

申万行业指数日线（801020.SI, 801030.SI 等）在 **5000 积分档次下不可用**。需要更高权限或使用 `index_classify` 仅获取分类元数据（无日线数据）。

**替代方案**：
- `index_classify(level='L1')` → 获取 28 个申万一级行业分类元数据（index_code, industry_name, level）
- 如需行业指数日线 → 升级 Tushare 账号或改用东方财富/同花顺行业指数

## 增量更新脚本设计

### 核心流程

```python
INDICES = [
    ('000001.SH', '上证指数'),
    ('399001.SZ', '深证成指'),
    ('399006.SZ', '创业板指'),
    ('000688.SH', '科创50'),
    ('000300.SH', '沪深300'),
]

def incremental_index_update(db_path, trade_date):
    pro = init_tushare()
    db_date = normalize_date(trade_date)  # YYYYMMDD → YYYY-MM-DD
    
    # 检查当日是否已有数据
    existing = db.execute("SELECT ts_code FROM index_daily WHERE trade_date=?", (db_date,)).fetchall()
    existing_codes = {r[0] for r in existing}
    
    rows = []
    for ts_code, name in INDICES:
        if ts_code in existing_codes:
            log(f'{name}({ts_code}) 已存在，跳过')
            continue
        
        df = pro.index_daily(ts_code=ts_code, start_date=trade_date, end_date=trade_date,
                             fields='ts_code,trade_date,close,pct_chg,vol,amount')
        time.sleep(0.5)  # 节流
        
        if df is not None and not df.empty:
            row = df.iloc[0]
            rows.append((ts_code, db_date,
                        safe_float(row.get('open')),
                        safe_float(row.get('high')),
                        safe_float(row.get('low')),
                        safe_float(row.get('close')),
                        safe_float(row.get('pre_close')),
                        safe_float(row.get('change')),
                        safe_float(row.get('pct_chg')),
                        safe_float(row.get('vol')),
                        safe_float(row.get('amount'))))
    
    if rows:
        db.executemany("""
            INSERT OR REPLACE INTO index_daily
            (ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        db.commit()
```

### 初始回补策略

首次运行需回补历史数据。每个指数回补一次全程即可（约 6000 行/指数 × 5 指数 = ~30,000 行），API 消耗 5 次：

```python
def backfill_all(db_path):
    """一次性回补 5 大指数全量历史"""
    pro = init_tushare()
    for ts_code, name in INDICES:
        df = pro.index_daily(ts_code=ts_code, start_date='20000101', end_date=today)
        time.sleep(0.5)
        # 批量写入 index_daily 表
        # 上证 2000→今约 6400 行，5 分钟可跑完
```

### Cron 配置

```bash
# 在日线管线（18:00）之后15分钟运行，避免API冲突
# Schedule: 15 18 * * 1-5
# Script: daily_index_tushare.sh
# Mode: no-agent
# Deliver: local
```

## 当前系统发现问题

### index_daily pct_chg 全为 NULL

现有 `index_daily` 表的 5216 行（000300.SH, 2005~今）**pct_chg 全部为 NULL**。原因：旧导入脚本没写此字段。

新管线需要在 INSERT 时确保 `pct_chg` 正确填充（Tushare 的 `index_daily` 直接返回此字段，不需要额外计算）。

### 仅沪深300有历史数据

虽然 `index_daily` 表有 5216 行，但只覆盖 `000300.SH` 一个指数。其他 4 个目标指数（上证/深证/创业板/科创50）一条记录都没有。

## 源码参考

- 同架构参考：`qfq_tushare_daily.py` — 同样的增量模式（增量+手动回补）、同样的 shell wrapper 模板
- 数据库：`~/my_quant_system/stock_data.db`，`index_daily` 表
- 日志目录：`~/.logs/`
- Token：`~/.hermes/.env.tushare`
- Token 可用性已验证（2026-07-03）：`tushare version 1.4.29`，5 大指数全部可用
