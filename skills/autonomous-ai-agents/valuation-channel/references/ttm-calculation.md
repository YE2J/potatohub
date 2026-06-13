# TTM 计算：累积财务数据 → 滚动TTM

## 问题背景

中国财务报表（同花顺 akshare `stock_financial_abstract_ths`）返回的是**累积值**，不是单季值。

| 报告期 | 返回的 EPS | 含义 |
|--------|-----------|------|
| 2025-03-31 | 0.67 | 仅 Q1 单季（年初至今累积） |
| 2025-06-30 | 1.18 | Q1 + Q2 累积 |
| 2025-09-30 | 1.87 | Q1 + Q2 + Q3 累积 |
| 2025-12-31 | 2.07 | 全年累积 |

如果直接用 `price / cum_eps` 计算 PE，会得到错误结果（Q1 的 PE 会被低估，Q3 的 PE 会被高估）。

## 转换算法

```python
prev_same_year = 0.0
for report_date, cum_value in data:
    month = report_date.month
    if month == 3:          # 一季报
        standalone = cum_value
        prev_same_year = cum_value
    elif month == 6:        # 中报
        standalone = cum_value - prev_same_year
        prev_same_year = cum_value
    elif month == 9:        # 三季报
        standalone = cum_value - prev_same_year
        prev_same_year = cum_value
    else:                   # 年报 (month == 12)
        standalone = cum_value - prev_same_year
        prev_same_year = 0.0  # 重置新年份
```

## TTM = 最近4个单季值之和

```python
# 对于每一天
TTM = sum(最近4个季度的单季值)
```

## 适用范围

| 指标 | 是否累积 | 处理方式 |
|------|----------|----------|
| 基本每股收益 | ✅ 累积 | 转单季 → TTM |
| 营业总收入 | ✅ 累积 | 转单季 → TTM |
| 每股经营现金流 | ✅ 累积 | 转单季 → TTM |
| 每股净资产 | ❌ 时点值 | 直接用最新值 |
| 净利润 | ✅ 累积 | 转单季 → TTM |
| ROE (%) | ❌ 非累积 | 直接用(需解析%字符串) |

## 特殊：每股销售额 (用于PS通道)

PS = 收盘价 ÷ 每股销售额
每股销售额 = TTM营收(亿元) ÷ 总股本(亿股)

**注意**：营收是总市值概念（"316.03亿"=316.03亿元），总股本从腾讯实时行情获取（市值÷股价）。两者单位都是"亿"，相除得元/股。

```python
# 从Tencent获取总股本
total_shares = market_cap_yi / price  # 亿股

# TTM营收(亿元) → 每股销售额(元)
sales_ps = ttm_revenue_yi / total_shares
ps = close_price / sales_ps
```

1. **营收带单位**："1466.95亿" → 需去除"亿"字转为纯数字
2. **EPS = False**：早期数据可能缺失，表现为 Python `False` 而非 float
3. **EPS = 0**：某些季度可能为0（尤其亏损股），需过滤
4. **新上市公司**：可能不足4个季度历史，需等比例处理
