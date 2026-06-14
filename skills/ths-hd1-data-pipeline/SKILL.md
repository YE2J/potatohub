---
name: ths-hd1-data-pipeline
description: "同花顺 hd1.0 格式数据批量转换+导入管线。处理日线.day、分钟.min/.mn5、财务.财经文件，自动导入量化回测系统SQLite数据库"
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [data-science, finance, stock, quant, A股, 量化回测]
    related_skills: [ths-stock-monitor, a-share-backtesting, a-share-valuation-analysis]
---

# 同花顺 hd1.0 数据管线

## Overview

同花顺软件本地数据使用 `hd1.0` 二进制格式存储日线、分钟线、财务数据。
本技能描述了从原始 `.day` / `.min` / `.mn5` / `.财经` 文件到量化回测系统 SQLite 数据库的完整管线。

**管线架构:**

```
.day 文件 → ths_batch_convert.py → CSV → ths_import_to_db.py → daily_kline 表
.min 文件 ─┐
.mn5 文件 ─┴→ ths_min_convert.py → CSV → minute_kline / minute5_kline 表
.财经 文件 → ths_finance_parser.py → CSV → 按表名导入独立表
```

## When to Use

- 需要解析同花顺本地 `.day` 日线数据文件
- 需要解析同花顺本地 `.min` 1分钟 / `.mn5` 5分钟数据文件
- 需要解析同花顺本地 `.财经` 财务数据文件（营收、股本、ROE、股东户数等）
- 需要将以上数据批量导入 `my_quant_system` 的 SQLite 数据库
- 有新数据需要增量导入（自动跳过已导入的日期/seq）

**不要用于：** 实时行情获取、网络数据爬取、非 hd1.0 格式文件。

---

## 文件位置

| 项目 | 路径 |
|---|---|
| 脚本目录 | `~/Documents/同花顺指标/` |
| 原始数据 | `~/Documents/同花顺指标/同花顺原数据/shase/{day,min,min5,finance}/` |
| 量化系统 | `~/my_quant_system/` |
| 数据库 | `~/my_quant_system/stock_data.db` |

---

## hd1.0 格式详解

### 通用文件头 (16 字节)

| 偏移 | 类型 | 说明 |
|------|------|------|
| 0x00 | byte[6] | 魔数 `hd1.0\0` |
| 0x06 | dword | 记录条数（或标识字段） |
| 0x0A | word | 内容区起始偏移 |
| 0x0C | word | 每条记录字节长度 |
| 0x0E | word | 列数（高字节需 &0xFF） |

对于 `finance` 目录下的文件，内容区偏移需检测是否需要 `+0x10000` 修正。

### 日线 .day 格式

- **指数文件**: 164 字节/条
- **个股文件**: 176 字节/条
- **价格格式**: 3 字节 LE int ÷ 10000，后面跟 0xc0 分隔符
- **记录间步长**: 与记录大小相同

| 偏移 | 字段 | 格式 |
|------|------|------|
| 0-3 | 日期 | int32 LE (YYYYMMDD) |
| 4-6 | 开盘价 | int24 LE ÷ 10000 + byte7=0xc0 |
| 8-10 | 最高价 | int24 LE ÷ 10000 + byte11=0xc0 |
| 12-14 | 最低价 | int24 LE ÷ 10000 + byte15=0xc0 |
| 16-18 | 收盘价 | int24 LE ÷ 10000 + byte19=0xc0 |
| 20-23 | 成交额 | int32 LE |
| 24-27 | 成交量 | int32 LE |

### 分钟线 .min / .mn5 格式

- **记录大小**: 48 字节
- **记录步长**: 152 字节
- **两种价格格式**（自动检测）:
  - `int24`: 3 字节 LE ÷ 10000 + 0xc0 分隔符（B指等小数值）
  - `int32`: 4 字节 LE ÷ 1000000（上证指数等大数值）
- **seq 步长**: `.min`=1（1分钟），`.mn5`=5（5分钟）

| 偏移 | 字段 | 格式 |
|------|------|------|
| 0-3 | seq | int32 LE (序列号) |
| 4-19 | OHLC | 见价格格式说明 |
| 24-27 | 成交量 | int32 LE |
| 28-31 | 成交额 | int32 LE |
| 36-39 | 成交笔数 | int32 LE |

### 财务 .财经 格式

复合格式，包含 5 部分:

1. **文件头** (16B)
2. **列定义** (4B/列) — 第4字节为该列字节长度
3. **填充区** (列数 × 2B)
4. **复合索引** — 每条 18 字节:
   - 1B: 证券类型（0x10=沪深, 0x48/0x50=港股, 0x4A=基金）
   - 9B: 证券代码 ASCII
   - 2B: 未使用记录数
   - 4B: 起始索引下标
   - 2B: 总记录数
5. **内容区** — 固定宽度记录

---

## 管线使用

### 全量一次性导入

```bash
cd ~/Documents/同花顺指标

# 1. 日线 → CSV + 导入 daily_kline
python3 ths_batch_convert.py "同花顺原数据/shase/day/"
python3 ths_import_to_db.py

# 2. 1分钟线 → CSV + 导入 minute_kline
python3 ths_min_convert.py "同花顺原数据/shase/min/"

# 3. 5分钟线 → CSV + 导入 minute5_kline
python3 ths_min_convert.py "同花顺原数据/shase/min5/" --ext .mn5 --table minute5_kline

# 4. 财务数据 → CSV + 导入独立表
python3 ths_finance_parser.py "同花顺原数据/finance/"
```

### 增量导入（新数据）

```bash
# 日线增量: 自动跳过已有日期
python3 ths_batch_convert.py /path/to/new_day/ -o csv_export
python3 ths_import_to_db.py --csv-dir csv_export

# 分钟线增量: 自动跳过已有 seq
python3 ths_min_convert.py /path/to/new_min/ --ext .min --table minute_kline
```

### 单文件处理

```bash
python3 ths_batch_convert.py "同花顺原数据/shase/day/600350.day" -o /tmp/
python3 ths_finance_parser.py "同花顺原数据/finance/净资产收益率.财经" --csv-only
```

---

## 关键脚本参数

### ths_batch_convert.py

| 参数 | 说明 |
|------|------|
| `<input>` | 文件或文件夹路径 |
| `-o` | 输出目录（默认: 输入目录旁 csv_export） |
| `--ext` | 文件扩展名过滤（默认 .day） |
| `-j` | 并行进程数（默认 CPU 核数） |
| `--flat` | 平铺输出，不保留目录结构 |

### ths_min_convert.py

| 参数 | 说明 |
|------|------|
| `<input>` | 输入目录（默认 min 目录） |
| `--ext` | 扩展名: `.min`(默认) / `.mn5` |
| `--table` | 表名: `minute_kline`(默认) / `minute5_kline` |
| `--db` | 数据库路径 |
| `--csv-only` | 只转 CSV 不导入 |
| `--db-only` | 只导入 CSV 不转换 |

### ths_import_to_db.py

| 参数 | 说明 |
|------|------|
| `--csv-dir` | CSV 目录（默认 csv_export） |
| `--db` | 数据库路径 |
| `--mode` | `ignore`(默认,跳过已有) / `replace`(覆盖) |
| `--parquet` | 同时导出 Parquet |

### ths_finance_parser.py

| 参数 | 说明 |
|------|------|
| `<input>` | 文件或文件夹路径 |
| `--db` | 数据库路径 |
| `--csv-only` | 只转 CSV |
| `--csv-dir` | CSV 输出目录 |

---

## 数据库表结构

### daily_kline（日线）

```sql
CREATE TABLE daily_kline (
    stock_code TEXT, date TEXT, open REAL, high REAL, low REAL,
    close REAL, volume REAL, amount REAL,
    amplitude REAL, pct_change REAL, change REAL, turnover REAL,
    PRIMARY KEY (stock_code, date)
);
```

### minute_kline / minute5_kline（分钟线）

```sql
CREATE TABLE minute_kline (
    stock_code TEXT, seq INTEGER, open REAL, high REAL,
    low REAL, close REAL, volume REAL, amount REAL, trades INTEGER,
    PRIMARY KEY (stock_code, seq)
);
```

### 财务表（按文件名动态创建）

每张财务表的列结构由 `.财经` 文件内的列定义决定，自动创建。包含 `stock_code` + 各数据列。

---

## 数据清理说明

1. **日线去重**: `INSERT OR IGNORE`，以 `(stock_code, date)` 为主键
2. **分钟线去重**: 先查 DB 已有日期集合 → 内存过滤 → 只插新记录
3. **分钟线重复保护**: 以 `(stock_code, seq)` 为主键
4. **价格格式自动检测**: int24（÷10000+0xc0）vs int32（÷1000000），通过 0xc0 分隔符 + OHLC 一致性校验
5. **财务数据内容偏移**: 自动检测是否需要 +0x10000 修正
6. **无效记录跳过**: 日期字段 ≤0 或不在 1990-2027 范围内则跳过

---

## 数据库现状

| 表 | 类型 | 记录数 | 证券数 |
|---|---|---|---|
| `daily_kline` | 日线 | 44,445 | 306 |
| `minute_kline` | 1分钟 | 243,435 | 202 |
| `minute5_kline` | 5分钟 | 58,176 | 202 |
| `A股营业总收入` | 营收 | 315,024 | - |
| `股本结构` | 股本 | 129,865 | - |
| `股东户数` | 股东 | 18,321 | - |
| `净资产收益率` | ROE | 94 | - |
| `可转债补充` | 可转债 | 276 | - |
| `REITs基金财务数据` | REITs | 182 | - |

---

## 脚本文件清单

| 文件 | 路径 | 功能 |
|---|---|---|
| `ths_batch_convert.py` | `~/Documents/同花顺指标/` | `.day` → CSV 批量转换 |
| `ths_import_to_db.py` | `~/Documents/同花顺指标/` | CSV → `daily_kline` 增量导入 |
| `ths_min_convert.py` | `~/Documents/同花顺指标/` | `.min`/`.mn5` → CSV → `minute_kline`/`minute5_kline` |
| `ths_finance_parser.py` | `~/Documents/同花顺指标/` | `.财经` → CSV → 独立财务表 |
| `stock_data.db` | `~/my_quant_system/` | SQLite 数据库 |

---

## Common Pitfalls

1. **价格格式误判**: int24 格式下，3B int + 0xc0 字节拼成 4B int 会得到超大值。检测器会同时检查 0xc0 分隔符位置和 OHLC 值一致性（差距<5%）。
2. **财务文件偏移**: `.财经` 文件的 content_offset 可能需 +0x10000 修正。脚本自动检测。
3. **分钟线误定位**: `find_data_start` 如果返回错误偏移，数据全是乱码。通过验证相邻记录的一致性来避免。
4. **大文件性能**: 股本结构文件 22MB、营收文件 17MB。脚本按 500 条一批插入，内存可控。
5. **日期格式不一致**: 旧 akshare 导入的日期是 `20221209`（无分隔符），同花顺 CSV 是 `2025-11-03`（有分隔符）。SQLite TEXT 排序两者都兼容。

## Verification Checklist

- [ ] `.day` 文件转换后 CSV 的 OHLC 值在合理范围（股票 1-1000，指数 100-10000）
- [ ] `.min`/`.mn5` 文件 seq 步长正确（1 分钟=1，5 分钟=5）
- [ ] `.财经` 文件每条记录都有有效的 `stock_code`（6 位数字）
- [ ] 增量导入时已存在的数据被正确跳过
- [ ] `minute_kline` 不与 `daily_kline` 混表
