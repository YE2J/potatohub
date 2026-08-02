# 数据陷阱汇总（2026-07-02 踩坑记录）

这一轮因子工程 + 全A股扫描中发现的重大数据坑。

## 1. daily_kline 日期格式不统一

同一张表 `daily_kline` 存在两种日期格式：

| 格式 | 示例 | 覆盖范围 | 说明 |
|------|------|---------|------|
| 无横线 | `'20260626'` | ~147只（watchlist） | 旧 Coze 同步管道 |
| 有横线 | `'2026-06-26'` | ~5,510只（全A） | InnerCode 批量导入 |

**后果**：`WHERE date >= '2026-01-01'` 只匹配到有横线格式（5,510只全A），无横线格式的147只被遗漏。但反过来 `WHERE date = '20260626'` 也只匹配到watchlist。

**修复**：Python 层统一转为横线格式：
```python
def normalize_date(d: str) -> str:
    """统一为 YYYY-MM-DD 格式"""
    d = d.strip()
    if '-' in d:
        return d
    # '20260626' → '2026-06-26'
    return f'{d[:4]}-{d[4:6]}-{d[6:8]}'
```

### ⚠️ SQL 参数化查询仍然受害（2026-07-02 发现）

即使使用参数化查询（`date >= ?`），SQLite 的字符串比较规则仍然导致范围查询错误：

```python
# 仍然错的：SQL 太聪明了
# 参数化 WHERE date >= '2026-06-23' 还是用了字符串比较
# '20260624' 的 ASCII 比较中第5位 '0'(48) > '-' (45)
# 所以 '20260624' > '2026-06-23' → True
# 但 '20260624' <= '2026-07-05' 呢？
# 比较到第4位 '0'(48) vs '-' (45) → '20260624' > '2026-07-05' → True!
# 所以 '20260624' 不满足 <= '2026-07-05'，被排除！
```

**结论**：对 mixed-format 的日期列，**不要在 SQL 中做任何范围过滤**。全量加载后，在 pandas 中统一 `pd.to_datetime(..., format="mixed")` 再用 datetime 比较过滤。

## 2. amount=0（最近交易日缺失）

`daily_kline` InnerCode 批次的 `amount` 列在**最新2个交易日=0**。

**后果**：传给 `calc_zhuli_holdings` 时，DDX 公式中 `amount` 为0，除以 `max(amount, 1e-6)` → DDX 变成天文数字 → 主力持仓瞬间钳制到 2.08%（下限），数据完全失真。

**修复**：调用 `calc_zhuli_holdings` 前用 `close × volume` 回退：
```python
dk_fixed = dk.copy()
zero_amt = dk_fixed['amount'].fillna(0) == 0
if zero_amt.any():
    dk_fixed.loc[zero_amt, 'amount'] = (
        dk_fixed.loc[zero_amt, 'close'] * dk_fixed.loc[zero_amt, 'volume']
    )
```

## 3. MONEY=0 导致暗盘资金崩溃

`MoneyflowAdapter._map_to_ths_columns()` 设置 `MONEY=0`（因为 THS 数据没有成交额列）。这导致 `calc_dark_pool` 中的 `小单买入初 = MONEY - 大单 - 特大单 - 中单` 为负数，整个暗盘资金公式产生假信号。

**症状**：全A股4条件扫描结果=0只 vs 同花顺选出多只。修复后 0→26只，同花顺匹配率 0/11→10/11。

**修复**：将 daily_kline 的 amount 按日期对齐后填入 mf_mapped：
```python
mf_mapped = adapter._map_to_ths_columns(mf)
amt_map = dict(zip(dk_fixed['date'], dk_fixed['amount']))
mf_mapped['MONEY'] = mf_mapped['date'].map(amt_map).fillna(0).values
```

## 4. InnerCode ↔ SecuCode 双编码

- `daily_kline` 的 `stock_code` = InnerCode（5位纯数字，如 `'605'`）
- `moneyflow_daily` 的 `stock_code` = SecuCode（6位，如 `'000988'`）
- 映射文件：`all_ashare_stocks.csv`，键=InnerCode，值=SecuCode

**后果**：SQL JOIN 需要先映射编码，否则交集=0。

**修复**：每次批量加载时，全量加载两个表，只保留映射中存在的交集股票。不要在 SQL 层面 JOIN，在 Python 层面用 dict 映射。

## 5. 指标输出列名与预期不一致

| 函数 | 预期列名 | 实际列名 |
|------|---------|---------|
| `calc_zhuli_holdings` | `zhuli_holdings` | **`zhuli_holding`**（单数） |
| `calc_zhuli_holdings` | — | `zhuli_ddx_daily` |
| `calc_dark_pool` | `dark_pool_flow` | **`dark_pool_1d`**（金额），**`dark_pool_inflow_signal`**（布尔） |
| `calc_zhuli_radar` | `radar_maisell` | ✅ 一致 |
| `calc_ai_activity` | `ai_score` | ✅ 一致 |

## 6. `except: continue` 静默吞错误

裸的 `try: ... except: continue` 会静默吞掉所有异常，导致：
- 某只股票计算失败时**完全看不到错误信息**
- 调试极其困难
- 无法统计失败率

**修复**：全局加 `logging.warning` 或异常计数器，记录失败股票代码和异常堆栈。

## 7. CSV DictReader 迭代器耗尽

```python
# ❌ 错误
with open("file.csv") as f:
    reader = csv.DictReader(f)
    dict1 = {r['key']: r['val'] for r in reader}  # reader exhausted
    dict2 = {r['val2']: r['val3'] for r in reader}  # EMPTY!

# ✅ 正确
with open("file.csv") as f:
    rows = list(csv.DictReader(f))
dict1 = {r['key']: r['val'] for r in rows}
dict2 = {r['val2']: r['val3'] for r in rows}
```

后果：screen_v4.py 中 `secu_to_name` 和 `secu_to_inner` 一直为空字典，所有扫描结果股票名称为空。
