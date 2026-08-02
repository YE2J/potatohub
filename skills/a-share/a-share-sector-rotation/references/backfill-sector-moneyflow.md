# 板块资金流历史回填策略

> 用于补充 sector_moneyflow_ths / industry_moneyflow_ths 表中缺失的历史交易日数据

## 适用场景

- 初次搭建数据管线时回填全年数据
- 数据管线切换（如从同花顺切Tushare）后补历史
- 因异常中断导致的某段时间数据缺失

## 回填流程

```
1. 查 trade_cal 获取全年交易日列表
2. 查目标表 DISTINCT trade_date 获取已有日期
3. 取差集得到缺失日期列表
4. 对每个缺失日期：
   a. moneyflow_cnt_ths(trade_date) → sector_moneyflow_ths
   b. time.sleep(1.5) ← 限频
   c. moneyflow_ind_ths(trade_date) → industry_moneyflow_ths
   d. time.sleep(1.5) ← 限频
5. 最终验证：MIN/MAX/COUNT(DISTINCT trade_date)
```

## 回填脚本

文件: `scripts/backfill_sector_moneyflow_2026.py` (229行)

核心逻辑复用 `daily_sector_moneyflow.py` 的列映射和事务模式。

## ⚠️ Python Lambda 闭包坑（Tushare API 回调）

这是最容易踩的坑，已踩过并修复：

```python
# ❌ 错误写法 — 会报 unexpected keyword argument 'trade_date'
def fetch_and_save(pro, trade_date, table, pro_func, columns):
    df = pro_func(trade_date=trade_date)  # 这里传 keyword arg

# 调用时：
fetch_and_save(..., lambda td: pro.moneyflow_cnt_ths(trade_date=td), ...)
#                   ^^^^^^  lambda 参数名是 td
# 但 fetch_and_save 调用：pro_func(trade_date=value)
# → keyword 'trade_date' 不匹配 lambda 参数名 'td'
# → 抛出 TypeError: got an unexpected keyword argument 'trade_date'

# ✅ 正确写法 — lambda 参数名与调用方的 keyword 匹配
fetch_and_save(..., lambda trade_date: pro.moneyflow_cnt_ths(trade_date=trade_date), ...)
#                   ^^^^^^^^^^^^^^^^^ lambda 参数名是 trade_date
# pro_func(trade_date=value) → 匹配 → 正常工作
```

**原理**：Python lambda 会捕获传入的关键字参数名。调用方传 `trade_date=val`，lambda 必须有一个名为 `trade_date` 的参数来接收它。

## 限频策略

| 数据源 | 推荐间隔 | 理由 |
|--------|:--------:|------|
| Tushare Pro (5000积分) | 1.5s/请求 | 约40次/分钟，低于120次/分钟限制，留有充足余量 |
| 同花顺 API | 2s/请求 | 更严格的频率限制 |

## 行数验证阈值

| 表 | 正常行数 | 警告阈值 | 说明 |
|:---|:--------:|:--------:|:-----|
| sector_moneyflow_ths | ~382行 | < 300 | 概念板块数量年初至今可能有变化 |
| industry_moneyflow_ths | ~90行 | < 60 | 行业板块较稳定 |

## 幂等性

使用 `INSERT OR REPLACE` + 先 `DELETE WHERE trade_date=?`：
- 同一天运行多次 → 最后写入覆盖之前的数据
- 中途崩溃 → 当天数据丢失（DELETE 已完成但 INSERT 未完成），需重新回填该日

### 改进方向（当前脚本未实现）

1. **断点续传**：在回填途中记录已完成日期到文件或状态表，中断后跳过已完成的
2. **交叉验证**：回填完成后随机抽样3-5天，对比 CSV 导出值和 DB 值一致性
3. **重试机制**：单个API失败时有指数退避重试（3次），避免因临时网络波动跳过某天
4. **连接复用**：当前每交易关闭/开连接，可改为一次性连接降低开销
