# 晨报大盘温度模块

## 函数: `report_market_temperature(conn=None)`

位置: `~/.hermes/scripts/daily_morning_report_v6.py`

### 逻辑

1. 取昨日日期（`now - 1d`），查 `trade_cal` 判断是否为交易日
2. **非交易日**: 取 market_temperature 最新记录，提示"无更新"+展示温度
3. **交易日**: 查 YYYY-MM-DD 格式，展示:
   - 温度标签 + 仓位建议 + 趋势方向
   - 三维分解表格（指数趋势/资金面/市场情绪）
   - 规则分析原因 + 操作建议

### 温度标签与建议

| 温度 | 标签 | 建议 |
|:---:|:----|:-----|
| ≥70 | 🔥过热 | 减仓防守，注意回调风险 |
| ≥50 | 🌤️温和 | 持股为主，跟踪热点轮动 |
| ≥30 | ☁️偏冷 | 轻仓观望，等待右侧信号 |
| <30 | ❄️低温 | 严格控仓，多看少动 |

### 关键坑

1. **conn复用**: 接收 `build_report` 传入的 `conn`，不新建连接。新建时 `close_conn` 守卫
2. **north_net_amount**: 大盘温度引擎已转亿元，晨报**不再除以10000**
3. **日期格式**: market_temperature 用 YYYY-MM-DD，直查不回退
4. **None保护**: temperature_score 可能为 None，需先 check
