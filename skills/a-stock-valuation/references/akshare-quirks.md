# akshare 财务数据获取注意事项（已废弃，仅供参考）

> **2026-07-02**：数据源已全面切换至 Tushare。此文件保留仅作历史参考。

## 数据源

`ak.stock_financial_abstract_ths(symbol='000988', indicator='按报告期')`

## 陷阱 1：排序方向

返回的 DataFrame **从旧到新排序**（1997 → 2026）。取最新数据必须用 `df.iloc[-1]`，不是 `df.iloc[0]`。

```python
# ❌ 错误：取到 1997 年数据
latest = df.iloc[0]

# ✅ 正确：取最新一期
latest = df.iloc[-1]
```

## 陷阱 2：季报 vs 年报

所有报告期混合（-03-31 Q1, -06-30 中报, -09-30 Q3, -12-31 年报）。
估值应优先取**年报**，因为季报数据不完整（单季度营收，不是年化）。

```python
# 过滤最新年报
annual = df[df['报告期'].astype(str).str.endswith('-12-31')]
if len(annual) > 0:
    latest = annual.iloc[-1]  # 最新年报
else:
    latest = df.iloc[-1]      # 降级到最新季报
```

## 陷阱 3：中文金额后缀

字段值带有中文后缀：

| 格式 | 示例 | 解析后 |
|------|------|--------|
| 万 | `1845.27万` | 18452700 |
| 亿 | `1.57亿` | 157000000 |
| 无后缀 | `1255.67` | 1255.67 |

```python
def _parse_cn_amount(val) -> float:
    if val is None or val is False or val == '':
        return 0.0
    s = str(val).replace(',', '').strip()
    if not s or s == 'False':
        return 0.0
    if '亿' in s:
        return float(s.replace('亿', '')) * 1e8
    elif '万' in s:
        return float(s.replace('万', '')) * 1e4
    return float(s)
```

## 陷阱 4：百分比后缀

```python
def _parse_pct(val) -> float:
    if val is None or val is False or val == '':
        return 0.0
    s = str(val).replace('%', '').strip()
    if not s or s == 'False':
        return 0.0
    return float(s) / 100.0
```

## 可用字段

| 列名 | 说明 | 格式 |
|------|------|------|
| 报告期 | YYYY-MM-DD | 日期字符串 |
| 营业总收入 | 单期营收 | 中文金额 |
| 净利润 | 单期净利润 | 中文金额 |
| 净资产收益率 | ROE | 百分比 |
| 资产负债率 | 负债率 | 百分比 |
| 销售毛利率 | 毛利率 | 百分比 |
| 基本每股收益 | EPS | 数字 |

## 行业获取

`ak.stock_individual_info_em(symbol='000988')` 可获取行业，但**不稳定**——可能 `RemoteDisconnected`。
当此接口失败时，行业字段返回 `"未知"`，估值引擎仍可运行（用 PE 通用模型兜底）。
