# Tushare 日线 QFQ 管线 — 代码审查检查清单

本文件记录 `qfq_tushare_daily.py`（以及同类 Tushare 日线增量管线）的常见代码级问题。用于下次审查或重写同类管线时参考。

## 1. 日期格式一致性

### 问题
- 表 `daily_kline.date` 存在 **两种格式**：`YYYYMMDD`（旧）和 `YYYY-MM-DD`（新）
- `MAX(date)` 因 ASCII `'0'`（48）> `'-'`（45），返回旧格式的最新日期，而非实际最新数据
- `daily_factors.trade_date` 注释明确写 "YYYY-MM-DD (标准化格式)"，说明新格式是标准

### 检查要点
- [ ] 检查脚本写入 `daily_kline.date` 时是否统一为 `YYYY-MM-DD`
- [ ] 下游查询是否使用了正确的格式匹配（`WHERE pct_change IS NOT NULL` 或按 `length(date)` 过滤）
- [ ] 回补模式（传入指定日期）的格式转换是否一致

### 修复模式
```python
# 统一转换为 YYYY-MM-DD
trade_date = target_date.replace("-", "")  # 输入归一化
db_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"  # DB 写入
```

## 2. 增量逻辑

### 已检查的陷阱

| 陷阱 | 表现 | 检查方式 |
|------|------|---------|
| 日志阈值与代码不符 | 日志写 `>=1000行`，代码实际 check `>=4800` | `grep -n '1000\|4800\|STOCK_MIN_COUNT'` |
| 无缺失日检测 | 只检查当前交易日，不会发现中间遗漏 | `def get_existing_dates()` 死代码存在但未调用 |
| `get_latest_trade_date()` 依赖 API，不走本地 trade_cal | 本地 trade_cal 周更会滞后 | 检查 trade_cal 同步频度 vs 查询策略 |
| 非交易日空转 | cron 触发后立即退出，浪费 1 次 API 调用 | 可在 cron 层面预处理 |

### 建议的缺失日检测逻辑
```python
def find_missing_dates(db, pro, max_days=5):
    """检测最近的缺失交易日"""
    latest_have = db.execute(
        "SELECT date FROM daily_kline WHERE pct_change IS NOT NULL ORDER BY date DESC LIMIT 1"
    ).fetchone()
    latest_api = get_latest_trade_date(pro)
    # 比较差值，回填中间缺失的交易日
```

## 3. 分批处理 & 批量 API 调用

### 常见问题

| 问题 | 严重性 | 说明 |
|------|--------|------|
| 分批失败无重试 | 🔴 高 | 单个 `except` 只能 log + continue，整批 50 只永久丢失 |
| 无指数退避 | 🟡 中 | 失败后仅 sleep 1.2s，不会增加间隔 |
| `daily_basic` 重复调用 | 🟡 中 | 每批调一次 `daily_basic()` 只取 `turnover_rate`，应改为全市场一次查询 |
| 无重试次数限制 | 🟢 低 | 持续失败时无限重试浪费 API 额度 |

### 建议的重试模式
```python
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        df = pro.daily(ts_code=ts_codes_str, start_date=trade_date, end_date=trade_date, adj='qfq')
        time.sleep(API_SLEEP)
        break
    except Exception as e:
        if attempt < MAX_RETRIES - 1:
            wait = API_SLEEP * (2 ** attempt)  # 指数退避: 1.2s → 2.4s → 4.8s
            log(f"重试 {attempt+1}/{MAX_RETRIES}: {e}, 等待 {wait:.1f}s")
            time.sleep(wait)
        else:
            log_error(f"批失败，{len(ts_codes_list)} 只跳过: {e}")
```

### daily_basic 优化
```python
# 全市场一次查询（不在每批中重复）
trade_date_basic_cache = {}
def get_turnover_cache(pro, trade_date):
    if trade_date not in trade_date_basic_cache:
        df_basic = pro.daily_basic(trade_date=trade_date)  # 不加 ts_code = 全市场
        time.sleep(API_SLEEP)
        cache = {}
        if df_basic is not None:
            for _, r in df_basic.iterrows():
                bare = r['ts_code'].replace('.SH','').replace('.SZ','').replace('.BJ','')
                cache[bare] = r.get('turnover_rate')
        trade_date_basic_cache[trade_date] = cache
    return trade_date_basic_cache[trade_date]
```

## 4. 股票代码过滤

### 检查要点
- [ ] `STOCK_CODE_PATTERN` 是 `r'^\d{6}$'` 还是 `r'^[03684]\d{5}$'`？
- [ ] `has_data_for_date()` 的 GLOB 模式（`0[0-9][0-9][0-9][0-9][0-9]`, `3...`, `6...`, `8...`, `4...`）是否与写入过滤一致？
- [ ] 9 开头代码的交易所后缀映射：`.SH` vs `.BJ`？

### 已知问题
- `^\d{6}$` 过于宽松，会通过 1xxxxx/2xxxxx/5xxxxx/7xxxxx/9xxxxx 等非标准代码
- **06-29/06-30 数据膨胀**：因 stock_basic 返回了大量非标准代码，导致 `daily_kline` 该日期含 ~10,360 行（正常 ~5,200）
- `has_data_for_date()` 用 GLOB 严格过滤（0/3/6/8/4 开头），所以防重跑检查仍正常工作，但非标准代码造成数据污染

```python
# 推荐的统一过滤
STANDARD_PREFIXES = ('0', '3', '6', '8', '4')
STOCK_CODE_PATTERN = re.compile(r'^[03684]\d{5}$')  # 与 GLOB 一致
```

## 5. 日志问题

| 问题 | 原因 | 修复 |
|------|------|------|
| 日志双重写入 | Python 内 `f.write()` + shell wrapper `tee -a` 各写一次 | Python 去掉 `f.write()`，shell 统一处理 |
| 日志阈值文字误导 | 写死 `>=1000行` 实际 check `>=4800` | 用 f-string 引用常量 `STOCK_MIN_COUNT` |

## 6. 其他常见陷阱

- **vol 单位**：Tushare `pro.daily()` 返回的 `vol` 单位是 **手**，需要 `* 100` 转股 ✅（已验证正确）
- **振幅公式**：`(high - low) / pre_close * 100` ✅（A 股标准）
- **死代码**：函数定义了但未调用是最常见的 code review 发现
- **两层 DB 连接**：`main()` 和 `transform_and_write()` 各开一个连接，虽不影响功能但冗余

## 参考

- 原始文件：`~/.hermes/scripts/qfq_tushare_daily.py`
- shell wrapper：`~/.hermes/scripts/qfq_tushare_daily.sh`
- 数据管道新鲜度检查：见本文档同目录的 `a-share-data-pipeline-check` 主 SKILL.md
