# Tushare 财务数据获取最佳实践

本文件记录从 Tushare 获取 A 股财务数据时已验证的模式和坑点。

## 限频退避

Tushare 免费账户每分钟 500 次请求，但持续高频调用仍可能触发 429。**每只股票每次 Tushare API 调用后**应插入 `time.sleep(1.1)`。

```python
df = pro.fina_indicator(ts_code=ts_code, ...)
time.sleep(1.1)  # 限频退避，防止429
df = pro.income(ts_code=ts_code, ...)
time.sleep(1.1)
df = pro.balancesheet(ts_code=ts_code, ...)
time.sleep(1.1)
```

批量查询时，**每只股票之间**加 1.1s 间隔：

```python
for code in stock_codes:
    data = fetch_single(code)
    time.sleep(1.1)  # 股票间限频
```

## 动态 end_date

不要硬编码 `end_date='20261231'` — 年份会过期。使用 `datetime.now()` 动态生成：

```python
from datetime import datetime
end_date = datetime.now().strftime('%Y1231')
pro.fina_indicator(ts_code=ts_code, start_date='20100101', end_date=end_date)
```

这样每年自动使用当前年度。

## 北交所股票代码后缀

北交所代码以 `8` 或 `4` 开头，Tushare 要求 `.BJ` 后缀（不是 `.SH` 也不是 `.SZ`）。

**判断顺序很重要** — 必须在 SH/SZ 逻辑之前检查 BJ：

```python
def _ts_code(code: str) -> str:
    if code.endswith(('.SH', '.SZ', '.BJ')):
        return code
    # 北交所优先
    if code.startswith(('8', '4')):
        return f"{code}.BJ"
    suffix = 'SH' if code.startswith(('6', '9')) else 'SZ'
    return f"{code}.{suffix}"
```

常见失误：先判断 `6`→SH、`0`/`3`→SZ，然后 `8`→SH（错误）。`8xxx` 不可能是上交所。

## 年报过滤

`income` / `balancesheet` / `cashflow` 接口一次性返回**所有类型**的报告期（季报 / 中报 / 年报），混在一起。提取年报时用 `end_date` 结尾标记过滤：

```python
df = df[df['end_date'].astype(str).str.endswith('1231')]  # 仅保留年报
```

如果不加过滤，`tail(5)` 可能取到 5 个季报而非 5 年年报，导致 CAGR 计算和 ROE 取值完全错误。

## ROE 优先级

Tushare `fina_indicator` 的 `roe` 字段是精确值（基于加权平均净资产计算），优先使用。

**不要无条件覆盖**为派生值（`net_profit / total_equity`）。只有在 API 返回的 ROE 为 `None` / `NaN` / `0` 时才使用派生值回退：

```python
# ✅ 正确：优先保留 API 值
if result.get('roe') is None or \
   (isinstance(result.get('roe'), float) and (result['roe'] != result['roe'] or result['roe'] == 0)):
    result['roe'] = result['net_profit'] / result['total_equity']

# ❌ 错误：无条件覆盖
result['roe'] = result['net_profit'] / result['total_equity']  # 丢失精确值
```

## 财务三表与指标的最佳顺序

单只股票全量财务数据的最佳获取顺序（已验证 5000 积分可用）：

1. `fina_indicator(ts_code, fields)` → ROE/ROA/毛利率/净利率/EPS/BPS/OCFPS（所有指标一次返回）
2. `income(ts_code, fields)` → 营收/净利润/营业利润/研发费用
3. `balancesheet(ts_code, fields)` → 总资产/总负债/归母股东权益
4. `cashflow(ts_code, fields)` → 经营活动现金流/资本支出/自由现金流

每个 API 调用之间加 1.1s 退避。4 次调用 ≈ 4.4s，对单只股票可接受。

## fina_indicator 100 条限制

`fina_indicator` 单次最多返回 100 条记录。历史超过 25 年的股票（季度数据 ≈ 100 条）可能被截断。如需更多，通过设置 `start_date`/`end_date` 范围分片拉取。
