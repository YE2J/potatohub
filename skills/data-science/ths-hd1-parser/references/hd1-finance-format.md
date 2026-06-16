# 同花顺 hd1.0 财务数据格式 (.财经)

## 来源

格式文档来源：[核新同花顺数据结构 - 博客园](https://www.cnblogs.com/shgq/p/4403010.html)

## 文件分类

| 目录 | 类型 | 说明 |
|------|------|------|
| `history/` | 行情数据 | 按市场代码、交易标的分类（.day, .min, .mn5） |
| `finance/` | 财务数据 | 单文件容纳所有品种（.财经） |

## 文件结构

### 1. 文件头 (16字节)

| 偏移 | 类型 | 长度 | 说明 |
|------|------|------|------|
| 0x00 | byte[6] | 6 | 固定 `{0x68, 0x64, 0x31, 0x2E, 0x30, 0x00}` ("hd1.0\0") |
| 0x06 | dword | 4 | "内容"区域记录条数（大文件可能编码异常，不可信） |
| 0x0A | word | 2 | "内容"区域开始位置（权息和股本结构需 +0x10000） |
| 0x0C | word | 2 | 每条记录字节长度 |
| 0x0E | word | 2 | 列个数（高字节可能非0x00，需 `& 0xFF` 去除） |

### 2. 列定义

固定 4字节一组，第4个字节表示该列内容的字节长度（最大255字节）。

常见列类型：
- 4字节: int32 LE (通常为日期 YYYYMMDD)
- 8字节: double LE
- 16字节: 两个 double LE

### 3. 填充区 (仅 finance 目录)

位于列定义与复合索引数据块之间，长度 = 列定义数量 × 2，全填充 0x00。

### 4. 复合索引数据块

由三部分组成：
1. **word (2字节)**: 本索引数据区域的字节长度
2. **word (2字节)**: 索引条数 (高字节需 `& 0x1FFF` 掩码)
3. **byte[]**: 不定长索引记录

每条索引记录 **18字节**：

| 偏移 | 类型 | 长度 | 说明 |
|------|------|------|------|
| 0x00 | byte | 1 | 证券品种类型：`0x10`=国内证券, `0x48/0x50`=港股, `0x4A`=基金 |
| 0x01 | byte[9] | 9 | 交易品种符号 (ASCII/GB2312编码) |
| 0x0A | word | 2 | 该品种记录区域中未使用的记录条数 |
| 0x0C | dword | 4 | 该品种记录的开始下标（内容区起始地址 + 下标 × 记录长度） |
| 0x10 | word | 2 | 该品种的记录总条数 |

**有效记录判定**：索引中通过 `(总条数 - 未使用条数)` 得到实际记录数。  
每条记录中，若第一个Int32时间字段值 ≤ 0，则该记录无效。

### 5. 内容区

起始地址由文件头 0x0A 处 word 指示（大文件需 +0x10000）。
有效长度 = 列长度 × 记录条数。

## 文件命名与字段对应

| 文件名 | 典型列 | 记录数/股 |
|--------|--------|----------|
| A股营业总收入.财经 | date, report_date, revenue(16B→两个double) | 每季/年多条 |
| 净资产收益率.财经 | date, report_date, roe | 每季1条 |
| 股东户数.财经 | date, total_shareholders, change | 不定期更新 |
| 股本结构.财经 | date, total_shares, float_a_shares, ...(16列) | 每季1条 |
| 可转债补充.财经 | date, conv_price, market_price, premium_ratio | 不定期 |
| REITs基金财务数据.财经 | date, nav, dividend, ...(8列) | 不定期 |

## Python 解析伪代码

```python
import struct

def parse_finance_file(filepath):
    with open(filepath, "rb") as f:
        buf = f.read()
    
    # 1. Header
    sig = buf[0:6]
    content_off_raw = struct.unpack('<H', buf[10:12])[0]
    rec_len = struct.unpack('<H', buf[12:14])[0]
    col_count = struct.unpack('<H', buf[14:16])[0] & 0xFF
    
    # content_offset may need +0x10000 for large files
    content_off = content_off_raw
    test = content_off_raw + 0x10000
    d = struct.unpack('<I', buf[test:test+4])[0]
    if 19900101 <= d <= 20270630:
        content_off = test
    
    # 2. Column definitions (4 bytes each, 4th byte = length)
    cols = []
    for i in range(col_count):
        col_def = buf[16+i*4:16+i*4+4]
        cols.append(col_def[3])
    
    # 3. Skip padding (col_count * 2 bytes)
    pad_end = 16 + col_count * 4 + col_count * 2
    
    # 4. Index
    idx_count = struct.unpack('<H', buf[pad_end+2:pad_end+4])[0] & 0x1FFF
    
    entries = []
    for i in range(idx_count):
        off = pad_end + 4 + i * 18
        entry = buf[off:off+18]
        code = entry[1:10].rstrip(b'\0').decode('ascii', errors='replace').strip()
        unused = struct.unpack('<H', entry[10:12])[0]
        start_idx = struct.unpack('<I', entry[12:16])[0]
        total = struct.unpack('<H', entry[16:18])[0]
        entries.append((code, start_idx, total - unused))
    
    # 5. Parse content
    for code, start_idx, valid in entries:
        base = content_off + start_idx * rec_len
        for j in range(total):  # total from index, not valid
            pos = base + j * rec_len
            rec = buf[pos:pos+rec_len]
            first_field = struct.unpack('<I', rec[0:4])[0]
            if not (19900101 <= first_field <= 20270630):
                continue  # skip unused records
            # Parse each column...
```
