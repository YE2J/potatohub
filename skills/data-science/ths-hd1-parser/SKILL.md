---
name: ths-hd1-parser
description: >-
  解析同花顺 hd1.0 格式的二进制数据文件(.day日线 / .min1分钟 / .mn5分钟)，
  批量转CSV并导入量化回测系统的SQLite数据库。
triggers:
  - 同花顺 .day / .min / .mn5 文件打不开或乱码
  - 需要把同花顺本地数据导入量化回测系统
  - 转换同花顺二进制数据到CSV或数据库
  - hd1.0 格式解析
---

# 同花顺 hd1.0 数据解析管线

## 文件位置

脚本路径: `~/Documents/同花顺指标/`
量化回测系统: `~/my_quant_system/`
数据库: `~/my_quant_system/stock_data.db`

## hd1.0 二进制格式

所有文件以魔数 `hd1.0\0` (6字节) 开头，随后4字节LE int32记录数。

### 日线文件 (.day)

| 文件类型 | 记录大小 | 数据起始偏移 |
|---------|---------|------------|
| 指数 (1A/1B/1C开头) | 164字节 | 0xB4 (180) |
| 个股 (6/0/3/68开头) | 176字节 | 0xC0 (192) |

**每条记录结构：**
- 0-3: 日期 (int32 LE, YYYYMMDD)
- 4-6: **开盘价** (int24 LE ÷ 10000)
- 7: 分隔符 0xc0
- 8-10: **最高价** (int24 LE ÷ 10000)
- 11: 分隔符 0xc0
- 12-14: **最低价** (int24 LE ÷ 10000)
- 15: 分隔符 0xc0
- 16-18: **收盘价** (int24 LE ÷ 10000)
- 19: 分隔符 0xc0
- 20-23: 成交额 (int32 LE)
- 24-27: 成交量 (int32 LE)

### 财务数据文件 (.财经)

**复合数据库格式**，单文件容纳所有品种的全量财务数据。

**文件结构（5部分）：**

| 部分 | 说明 |
|------|------|
| 文件头 (16B) | `hd1.0\0`(6) + rec_count(4) + content_off(2) + rec_len(2) + col_count(2) |
| 列定义 | 每组4字节，第4字节=该列字节长度 |
| 填充区 | col_count × 2 字节 (全0x00) |
| 复合索引 | 2B总长 + 2B条数(&0x1FFF) + n×18B索引记录 |
| 内容区 | 固定宽度记录，起始由 content_off 指示 |

**索引记录 (18字节)：**
- 0x00: 品种类型 (0x10=国内证券, 0x48/0x50=港股)
- 0x01-0x09: 证券代码 (ASCII, 9字节)
- 0x0A-0x0B: 未使用记录数
- 0x0C-0x0F: 开始下标 (内容区起始 + 下标 × 记录长度)
- 0x10-0x11: 总记录数

**注意事项：**
- `content_offset` 字段可能需要 +0x10000 调整（营收/股本结构等大文件）
- 列长度决定了字段类型：4B=int32, 8B=double, 16B=两个double
- 通过索引中的股票代码与 `daily_kline` 表的 `stock_code` 自动关联

```bash
# 解析所有 .财经 文件
python ~/Documents/同花顺指标/ths_finance_parser.py /path/to/finance/

# 指定数据库
python ~/Documents/同花顺指标/ths_finance_parser.py /path/to/finance/ --db /path/to/stock_data.db

# 只转CSV
python ~/Documents/同花顺指标/ths_finance_parser.py /path/to/finance/ --csv-only
```

### 分钟文件 (.min / .mn5)

两种格式并存，自动检测：
- 记录大小: 48字节
- 步长: 152字节 (每152字节一个48字节数据段，其余为0xFF填充)
- 数据起始: 约偏移160-192 (自动探测)

**格式A (int24)**: 3字节 LE int / 10000 + 0xc0 分隔符(用于B指等小数值)
**格式B (int32)**: 4字节 LE int / 1000000 (用于上证指数等大数值)

**自动检测逻辑**：检查 bytes[7,11,15,19] 是否全为 0xc0 → int24；
否则检查4个OHLC值是否接近(差距<5%)且均在[1e6, 1e10]范围内 → int32。

### 价格格式 (通用)

所有文件都遵循同一价格编码体系：
- **日线**：统一 int24 ÷ 10000 + 0xc0 分隔
- **分钟线**：int24 ÷ 10000 (小数值) 或 int32 ÷ 1000000 (大数值)

## 管线脚本

### ths_batch_convert.py (.day批量转CSV)

```bash
python ths_batch_convert.py /path/to/day/               # 递归扫描所有.day
python ths_batch_convert.py /path/to/day/ -o /path/csv   # 指定输出目录
python ths_batch_convert.py /path/to/day/ -j 8           # 多进程加速
```

### ths_min_convert.py (.min/.mn5 转CSV+入库)

```bash
# 1分钟数据
python ths_min_convert.py /path/to/min/

# 5分钟数据
python ths_min_convert.py /path/to/min5/ --ext .mn5 --table minute5_kline

# 单独控制
python ths_min_convert.py ... --csv-only   # 只转CSV
python ths_min_convert.py ... --db-only    # 只导入已有CSV
```

### ths_import_to_db.py (CSV导入日线表)

```bash
python ths_import_to_db.py --csv-dir /path/csv --db /path/stock_data.db
```

## 数据库设计

分表管理，互不干扰：

| 表名 | 粒度 | 脚本参数 |
|-----|------|---------|
| `daily_kline` | 日线 | ths_import_to_db.py (or --table daily_kline) |
| `minute_kline` | 1分钟 | ths_min_convert.py (默认) |
| `minute5_kline` | 5分钟 | --table minute5_kline |

## 增量导入策略

核心原则：**内存级去重，不向SQLite发送重复数据**。

1. 一次性加载所有已存在的 (stock_code, date/seq) 到 Python set
2. 读取CSV时过滤掉已存在的记录
3. 只插入真正新的记录
4. 使用 INSERT OR IGNORE 作为兜底

⚠️ **旧的 `INSERT OR IGNORE` + 全部发送方式已被弃用**——对于大规模重复数据性能极差。

## 注意事项

- 日线和分钟线数据**必须分表管理**，不能混入同一张表
- 个股文件可能包含旧数据（通过akshare已导入），`.day`文件可能只覆盖最近一段
- 错误检测：int32格式检测必须校验**全部4个OHLC值的一致性**（差距<5%），否
  则索引区数据会被误判为价格
- seq 步长: .min 为 1, .mn5 为 5
