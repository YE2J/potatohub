"""DC板块资金流历史回填 — 东方财富数据源

范围: 2026-01-05 ~ 2026-07-16 (128天)
API: pro.moneyflow_ind_dc(trade_date=, content_type='概念'/'行业')
表: sector_moneyflow_dc / industry_moneyflow_dc
单位: net_amount 为元（引擎内/1e4归一化为万元）

特点:
- 当天2次API调用(概念+行业)，各sleep 1.5s
- 双表独立缺失检测，避免重复API调用
- 3次重试 + socket timeout 30s
- 信号处理器(SIGINT/SIGTERM) + 连接追踪
- 行数阈值校验(概念≥200, 行业≥50)
- 最终覆盖率+行数统计验证

# 用法
python scripts/backfill_sector_moneyflow_dc.py
# 如需补未来日期，改get_trade_days()中的上限日期

# 常见坑
# 1. content_type参数必须用'概念'/'行业'（不要加"板块"后缀）
# 2. lambda传参：内部函数用位置参数pro_func(trade_date)而非pro_func(trade_date=trade_date)
"""
