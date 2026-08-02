# v4 可视化报告模块（2026-06-30）

## 触发方式

```bash
cd ~/my_quant_system
python3 backtest_v4.py --report
python3 backtest_v4.py --report --codes 000988 301338
```

## 生成的图表（6 张，深色主题，纯 Python + SVG）

| # | 图表 | 数据来源 |
|---|------|---------|
| 1 | **累计收益曲线** vs 沪深300 | equity_curve / index_daily(000300.SH) |
| 2 | **回撤曲线** | drawdown = (peak - equity) / peak |
| 3 | **月度收益热力图** | 按月/年分组收益率，红绿渐变 |
| 4 | **年度收益汇总表** | 每年收益率 + 交易次数 + 胜率 |
| 5 | **单票盈亏分解柱状图** | per_stock 累计盈亏 |
| 6 | **近期每笔交易盈亏** | 最近20笔 PnL% 分布 |

## 依赖

- **零额外依赖** — 纯 Python + SVG 嵌入式 HTML，无需 plotly/matplotlib
- 生成 `.html` 文件，可离线打开
- SVG 渲染自动适配，无版本冲突风险

## 关键指标卡片

报告顶部 10 项关键指标，绿/红/黄色标注：

| 指标 | 来源 |
|------|------|
| 总收益率 / 年化收益率 | run_multi_backtest() |
| 夏普比率 / 最大回撤 | run_multi_backtest() |
| 卡玛比率 | 年化收益 / abs(最大回撤) |
| 胜率 / 盈亏比 | run_multi_backtest() |
| 交易次数 / 平均每笔收益 | trades 统计 |
| 最终权益 | run_multi_backtest() |

## 基准对齐（沪深300）

基准线采用**日期对齐**而非数组索引对齐：

```python
# 正确 ✅
bench_map = dict(zip(bench_dates, bench_values))
for d in equity_dates:
    v = bench_map.get(d[:10])
    if v is not None: aligned.append(v)
```

关键点：
- `result["dates"]` 是 `run_multi_backtest()` 新返回的字段（回测期间所有交易日的日期列表）
- 基准数据按 `YYYY-MM-DD` 格式匹配，日期没对齐时跳过（不等长也不报错）
- 两者独立归一化到各自起始日 0%，互不影响
- 切忌 `benchmark / benchmark[0]` 直接除——如果基准从2005年开始，曲线会拉到+400%平铺不开

## 沪深300 数据源

不要依赖 Tushare `index_daily`（限频 1次/小时，非常慢）。使用东方财富免费 API：

```python
url = (
    f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
    f"fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    f"&ut=7eea3edcaed734bea9cbd0c4f6e5a2b7"
    f"&klt=101&fqt=1"
    f"&secid=1.000300"
    f"&beg={year}0101&end={year}1231"
    f"&_={int(time.time()*1000)}"
)
```

字段 `parts[]` 索引：
- `parts[0]` = 日期（YYYY-MM-DD）
- `parts[1]` = 开盘
- `parts[2]` = 收盘
- `parts[3]` = 最高
- `parts[4]` = 最低
- `parts[6]` = 成交量
- `parts[7]` = 成交额

脚本：`scripts/import_hs300_v2.py`。按年分批，sleep 0.3s，全年 5,216 条约 30 秒拉完。

## 输出

- 保存：`results/backtest_report_{YYYYMMDD_HHMMSS}.html`
- 不破坏终端输出和 CSV 保存逻辑

## 实现文件

- `~/my_quant_system/backtest_report.py` — 报告生成模块（纯 Python + SVG，零额外依赖）
- `~/my_quant_system/backtest_v4.py` — 通过 `--report` 参数调用
- `~/my_quant_system/scripts/import_hs300_v2.py` — 沪深300数据拉取脚本（东方财富免费 API）
