# hd1.0 二进制格式逆向工程笔记

## 发现过程

1. 直接用标准通达信32字节格式解析 `.day` 文件 → 数据乱码
2. 查看文件头发现 `hd1.0\0` 魔数 → 确认是同花顺自有格式
3. 发现 0xc0 重复出现在固定位置 → 推断为3字节int + 1字节分隔符
4. 验证价格: 3字节LE int / 10000 → 得到合理价格(上证B指~260)
5. 发现 `.min` 文件有0xc0(部分)和没有0xc0(另一部分)两种 → 双格式检测

## 格式规格

### 日线 .day

```
Offset  Size  Type     Field
0x00    4     int32 LE Date (YYYYMMDD)
0x04    3     int24 LE Open price (÷10000)
0x07    1     uint8    Separator (always 0xc0)
0x08    3     int24 LE High price (÷10000)
0x0B    1     uint8    Separator (always 0xc0)
0x0C    3     int24 LE Low price (÷10000)
0x0F    1     uint8    Separator (always 0xc0)
0x10    3     int24 LE Close price (÷10000)
0x13    1     uint8    Separator (always 0xc0)
0x14    4     int32 LE Amount (元)
0x18    4     int32 LE Volume (手? 股?)
```

记录大小: 指数 164B, 个股 176B, 步长 = 记录大小

### 分钟 .min / .mn5

```
Offset  Size  Type     Field
0x00    4     int32 LE Sequence number
0x04    4     see fmt  Open price
0x08    4     see fmt  High price
0x0C    4     see fmt  Low price
0x10    4     see fmt  Close price
0x14    4     int32 LE field_5 (unknown, 可能是总成交额)
0x18    4     int32 LE Volume
0x1C    4     int32 LE Amount
0x20    4     int32 LE field_8 (unknown)
0x24    4     int32 LE Trades count
0x28    4     int32 LE field_10 (unknown)
0x2C    4     int32 LE field_11 (unknown)
```

记录大小: 48字节, 步长: 152字节

### 格式A (int24)
价格字段为 3字节 LE int / 10000, byte[7,11,15,19] = 0xc0

### 格式B (int32)  
价格字段为 4字节 LE int / 1000000, byte[7,11,15,19] ≠ 0xc0

## 检测算法 (Python)

```python
def detect_format(buf, data_off):
    rec = buf[data_off:data_off+48]
    # int24: 4个0xc0分隔符
    if all(rec[i] == 0xc0 for i in [7, 11, 15, 19]):
        return "int24"
    # int32: 4个OHLC值接近且>1e6
    if all(rec[i] != 0xc0 for i in [7, 11, 15, 19]):
        v4 = int.from_bytes(rec[4:8], 'little')
        v8 = int.from_bytes(rec[8:12], 'little') 
        v12 = int.from_bytes(rec[12:16], 'little')
        v16 = int.from_bytes(rec[16:20], 'little')
        vals = [v4, v8, v12, v16]
        vmin, vmax = min(vals), max(vals)
        if (1000000 <= vmin and vmax <= 10000000000 
            and (vmax - vmin) / vmin < 0.05):
            return "int32"
    return None
```

## 文件头部结构

所有 hd1.0 文件共享同一头部:

```
Offset  Size  Content
0x00    6     Magic: b"hd1.0\0"
0x06    4     Count (int32 LE, 记录总数)
0x0A    variable  Index area (与 count 相关)
```

Index area 后的0xFF填充表示index结束，数据段从此之后的第一个非FF偏移开始(步长152B)。

## 关键发现

- 0xc0 分隔符在同花顺数据中作为"价格字段结束标记"，与通达信不同
- 价格编码使用24位或32位定点数而非IEEE 754浮点数
- 记录间有大量0xFF填充，有效数据仅占文件的一小部分
- 分钟文件的 seq 从 132,506,206 左右开始（与某一起始时间点对应）
