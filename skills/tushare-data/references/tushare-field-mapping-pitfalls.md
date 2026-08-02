# Tushare 增量数据管线：字段映射与坑点速查

本文档覆盖通过 Tushare Python SDK 构建每日增量数据管线时的常见陷阱。
适用于 cron 脚本（no_agent 模式）调用的 ETL Python 脚本。

## moneyflow_dc (个股资金流向)

### 字段语义陷阱

**buy_elg_amount / buy_lg_amount / buy_md_amount / buy_sm_amount 是净额，不是买入额！**

虽然字段名以 `buy_` 开头，但实际是**净额**（正=净流入，负=净流出）。

```python
# ❌ 错误：误以为是大单买入金额
row['elg_buy_amt'] = buy_elg_amount  # 错！这是净额

# ✅ 正确：映射到净额字段
row['elg_net_amt'] = buy_elg_amount * 10000  # 万元→元
row['lg_net_amt']  = buy_lg_amount * 10000
```

**验证公式：** `net_amount = buy_elg_amount + buy_lg_amount` (主力的定义)

### 单位
- Tushare 返回：万元（如 `461591.58` 表示 46.16亿元）
- DB 存储：元 → 乘以 10000

### 全市场拉取
`pro.moneyflow_dc(trade_date=YYYYMMDD)` 一次返回全市场（约6000只股票），**不需要逐股拉取**。

### 日期判断
```sql
-- 检查某日是否已有数据
SELECT COUNT(*) FROM moneyflow_daily 
WHERE date = 'YYYY-MM-DD' AND data_source = 'tushare_dc'
```
阈值：≥100行视为已有数据（停牌和北交所股无数据，一般达不到全量）。

---

## pro.daily (日线行情 + 前复权)

### 关键参数
- `adj='qfq'` — 前复权
- 返回单位：`vol` 是**手**（1手=100股），`amount` 是**元**

### 限频限制
`pro.daily` 无特殊限频（基础接口），按股票拉取即可。

**全市场增量策略：**
```python
# A股约5000只，5000积分限频500次/分钟
# 按股票逐只拉取最新1天，约10分钟跑完
for stock_code in all_stocks:
    df = pro.daily(ts_code=stock_code, start_date=today_str, end_date=today_str, adj='qfq')
    time.sleep(0.12)  # 保持≤500次/分钟
```

---

## pro.daily_basic (每日估值指标)

### ⚠️ 关键限频：1次/小时！
与大多数接口不同，`daily_basic` 的限频是 **1次/小时**（不是每分钟500次）。
`5000积分` 也不能解锁更高频次。

```python
# ❌ 不能逐股或逐天反复调用
# ✅ 只用 trade_date 参数一次拉全市场
df = pro.daily_basic(trade_date='20260630')  # 一次拉全市场，约6000条
```

### 字段说明
- `total_mv` / `circ_mv`：总市值/流通市值，单位**元**
- `turnover_rate` / `turnover_rate_f`：换手率（%）
- `pe` / `pe_ttm`：市盈率
- `pb`：市净率
- `dv_ratio` / `dv_ttm`：股息率（%）

---

## fina_indicator (财务指标)

### 限频
- `5000积分`：单次最多 **100条**，每分钟500次
- 多年数据需要分多次请求（按年）

### 单位特殊
- `roe` / `gross_margin` / `netprofit_margin` 等比例指标是**百分比值**
  - `15.2` = 15.2%，使用时需 `/100` → `0.152`
- 其他金额指标单位：**元**

### 字段验证
```python
# 常见字段（确认存在）
fields=['eps','dt_eps','roe','bps','gross_margin','netprofit_margin',
        'current_ratio','quick_ratio','assets_turn']
```

---

## income / balancesheet / cashflow (三大报表)

### 单位
- 全部为**元**（没有"万/亿"后缀）

### 年报筛选
```python
# 只保留年报数据
df = pro.income(ts_code='000988.SZ', ...)
df = df[df['end_date'].astype(str).str.endswith('1231')]
```

### 常用字段速查

| 接口 | 字段 | 含义 |
|------|------|------|
| income | `revenue` | 营业总收入 |
| income | `n_income_attr_p` | 归母净利润 |
| income | `operate_profit` | 营业利润 |
| income | `total_profit` | 利润总额 |
| income | `rd_exp` | 研发费用 |
| balancesheet | `total_assets` | 总资产 |
| balancesheet | `total_liab` | 总负债 |
| balancesheet | `total_hldr_eqy_exc_min_int` | 归母权益 |
| balancesheet | `money_cap` | 货币资金 |
| balancesheet | `accounts_receiv` | 应收账款 |
| cashflow | `n_cashflow_act` | 经营活动现金流净额 |
| cashflow | `free_cashflow` | 自由现金流 |

---

## stock_basic (股票列表 + 行业)

### 限频
1次/分钟（基础接口，较严格）

### 行业字段
`industry` 返回**申万一级行业中文名**（如"食品饮料"、"银行"）。

### 代码格式
```python
# 6位裸代码 → Tushare 格式
def _ts_code(code):
    code = code.strip()
    if code.startswith(('8','4')):   # 北交所
        return f"{code}.BJ"
    suffix = 'SH' if code.startswith(('6','9')) else 'SZ'
    return f"{code}.{suffix}"
```

---

## 通用限频策略

| 积分 | 频次 | 适用场景 |
|------|------|---------|
| 5000 | 500次/分钟 | 日常批量拉取（pro.daily, income等） |
| 5000 | 1次/小时 | `daily_basic` 特殊限频 |
| — | 1次/分钟 | `stock_basic` 基础接口 |

**推荐间隔：** `time.sleep(1.1)` 保证不超过500次/分钟安全线。
