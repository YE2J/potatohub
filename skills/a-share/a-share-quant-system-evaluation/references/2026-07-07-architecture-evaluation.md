# 量化系统架构师评估报告 (2026-07-07)

> 评估对象: A股个人量化系统 (stock_data.db SQLite 6.94GB, Mac Mini M4)
> 评估日期: 2026-07-07

## 系统现状

### 数据层
- daily_kline: 267万行（前复权日线OHLCV）
- moneyflow_daily: 1429万行（Tushare个股资金流）
- daily_factors: 285万行（37个因子）
- 其他: minute_kline, index_daily, 涨停池/龙虎榜/异动/热榜

### cron自动化
- 15:30~17:00 打板数据 (异动/涨停/连板/龙虎榜)
- 18:00~18:30 日线/指数/资金流增量
- 19:00~20:00 因子计算/回填
- 22:00 市场热榜
- 07:02 晨报推送

## 核心发现

### SQLite性能
- 当前6.94GB, 年增长约2.5GB, 距50GB性能拐点还有多年
- **严重问题**: cache_size仅8MB（默认2000页），对6.9GB DB严重不足
- WAL模式已启用 ✅
- **零成本优化**: PRAGMA cache_size=-262144(256MB), mmap_size=2147483648(2GB), temp_store=MEMORY

### Mac Mini M4负载
- 因子计算增量模式: 15~30秒
- 全量回填: 3~8分钟
- cron高峰时段CPU不会过载 (脚本间隔≥15分钟)
- 峰值内存约800MB, 16GB RAM非常安全
- 新增模块预计: +15% CPU / +300MB内存 / +200MB/年磁盘

### 管线问题
1. **cron假错误**: cron_log_helper.sh第100行bug导致exit code 1但数据正常
2. **因子算法TODO**: factor_pipeline.py中compute_gs_signal标记为待实现
3. **环境混乱**: 3个venv残骸, .venv是py3.9但cron用3.11
4. **指数pct_chg NULL**: 沪深300早期数据pct_chg大量NULL

### 新增管线评估
- 新闻情绪: ✅ 可行, 仅需Tushare major_news API
- 财务指标: ⚠️ 全市场5000只×20季度需1000+ API调用, 建议只采自选股
- PE分位数: ✅ 可行, 依赖daily_kline + fina_indicator(eps)
- 6个短期因子中5个已有数据源, 无需新采集

## 推荐实施路线

### Phase 1 (立即, 1~2天)
1. 优化SQLite配置 (cache_size/mmap/temp_store)
2. 修复cron_log_helper.sh第100行bug
3. 清理Python环境
4. 审查并确认因子计算实际链路

### Phase 2 (本周, 3~5天)
1. 实现短期因子 (funding_surge, north_star, board_resonance)
2. 注册到factor_pipeline.py增量计算
3. IC评估新因子
4. 新增新闻情绪管线 (限自选股)

### Phase 3 (下周, 3~5天)
1. fina_indicator采集 (限自选股+watchlist)
2. PE分位数计算 (5年滚动窗口, 过滤亏损股)
3. 估值/财务因子周频计算
4. 决策融合层 (简单加权 + 回测标定)

## 最终结论
系统架构设计合理, SQLite远未到瓶颈, Mac Mini资源充裕。
最大风险: 因子管线核心算法实现状态不明确, 需优先审查。
