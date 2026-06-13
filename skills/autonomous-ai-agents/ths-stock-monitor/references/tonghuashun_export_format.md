# 同花顺 Table.xls 导出格式解析

同花顺的"数据导出"功能生成的是 `.xls` 后缀文件，但**实际是 tab 分隔的文本文件**（ISO-8859 text with CRLF/CR line terminators），不是真正的 Excel 二进制格式。

## 文件结构

| 特征 | 值 |
|------|-----|
| 扩展名 | `.xls` |
| 真实格式 | tab-separated text |
| 编码 | GBK (中文) |
| 行分隔 | `\r` (CR, 0x0d) |
| 列分隔 | `\t` (Tab, 0x09) |
| 第一行 | 表头（中文列名） |

## 股票代码格式

每行第一个字段格式：`SHxxxxxx` 或 `SZxxxxxx`（前面有一个 `\r` 分隔符）

```
\rSH600519\t贵州茅台\t...
\rSZ000001\t平安银行\t...
```

- `SH` = 上海交易所
- `SZ` = 深圳交易所
- `xxxxxx` = 6位股票代码

## Python 解析代码

```python
import re, json

with open('Table.xls', 'rb') as f:
    raw = f.read()

stocks = []
seen_codes = set()

for m in re.finditer(b'\r(SH|SZ)(\d{6})\t(.+?)\t', raw):
    prefix = m.group(1).decode()  # "SH" or "SZ"
    code = m.group(2).decode()    # 6-digit code
    name_bytes = m.group(3)
    name = name_bytes.decode('gbk').strip()
    name = re.sub(r'[\x00-\x1f]', '', name)  # remove control chars
    
    if code in seen_codes:
        continue
    seen_codes.add(code)
    
    # 过滤掉指数（不可交易）
    if code in ('000001', '399001', '399006', '000688'):
        continue
    
    stocks.append({'code': code, 'name': name})

print(f'Extracted {len(stocks)} stocks')
```

## 注意点

1. **编码问题**：文件是 GBK 编码，读取后解码需指定 `gbk`。如果用 UTF-8 读取会出现乱码。
2. **行分隔符**：`\r` (0x0d) 不是 `\n`。如果用 `split('\n')` 解析会错误地将一整行视为一个长字符串。
3. **指数过滤**：`000001`(上证指数)、`399001`(深证成指)、`399006`(创业板指)、`000688`(科创50) 是指数，不可交易，应排除。
4. **非股票品种**：文件中可能包含外汇(`USDCNY`)、商品(`Au99.99`)、海外指数(`DJI`)等，这些以 `^M` 开头，正则 `\r(SH|SZ)\d{6}\t` 会自动跳过。
5. **ETF/LOF**：代码如 `159XXX`、`513XXX`、`501018` 等是 ETF/LOF，属于可交易品种，应保留。
