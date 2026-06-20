# 最终架构路线图：A股量化系统 v3.0

> 2026-06-20 综合审查生成。基于 Agent 1/2 纠正项 + 4 个 skill 完整交叉验证。

## 纠正项确认

| 纠正项 | 原始错误 | 正确结论 |
|--------|---------|---------|
| 数据源优先级 | akshare > Tushare > 问财 | **问财 > 腾讯 > akshare** |
| Tushare 增值接口 | 假设 moneyflow/fina_indicator 可用 | **40203 不可访问（需 2000 积分）** |
| 数据获取路径 | 从零探索 | **必须先用已有 skill** |

---

## 5 项数据需求最终覆盖方案

### 1. 实时/日线 OHLCV（行情数据）
- **主力**: 问财 OpenAPI `hithink-market-query`（cron `fda7975b8524` 每日 00:00）
- **备用**: 腾讯 `qt.gtimg.cn`（无频率限制，GBK 编码）
- **兜底**: akshare（本机 Connection aborted 频繁）
- ❌ Tushare `daily` 不推荐（限频）

### 2. 财务数据（三表 + 指标）
- **主力**: 问财 OpenAPI `hithink-finance-query`
- **备用**: akshare `stock_financial_abstract_ths()`（从旧到新排序，金额带中文后缀）
- **兜底**: 本地 JSON 缓存 + 默认值
- ❌ Tushare `fina_indicator` = 40203

### 3. 资金流向（主力/大单/中单/小单）
- **主力**: 东方财富 `push2his` → `web_extract` 中继（cron `209c43908019` 每日 18:30）
- **备用**: 问财 OpenAPI（含资金流字段）
- ❌ Tushare `moneyflow` = 40203
- ❌ 东财 `push2` 实时报价 = 持续 502

### 4. 机构研报 + 评级 + 盈利预测
- **主力**: 问财 OpenAPI `hithink-insresearch-query` + 社区技能 `report-search`
- **备用**: Tushare MCP 基础接口（`research_report`/`report_rc`）
- **增强**: Coze 恒生聚源数据（独占渠道）

### 5. 行业分类 + 估值参数
- **主力**: 申万行业分类（7 类→估值模型映射）
- **备用**: Tushare MCP `stock_basic` + 问财 API 行业字段
- ❌ 东财 push2 `f127/f128/f129` 不可靠

---

## Coze 角色重新定义（v2）

### v2 当前定位
- ✅ 每 10min：curl /health + 心跳新鲜度检查
- ✅ 触发式：主人说"救Hermes" → bash rescue.sh
- ✅ 每日日报协作（00:00 Coze → 00:10 Hermes）
- ✅ 恒生聚源机构数据（独占渠道）
- ❌ 不做 30s/60s 心跳（Coze 定时最小 10min）
- ❌ Hermes 不救 Coze.app（主人有多渠道访问）

### 守护架构（三层）
```
治本层: launchd KeepAlive — 进程死掉自动拉起
诊断层: Hermes cron selfcheck (每 60s) — 写心跳 + HTTP 自检
兜底层: Coze 深度检查 (每 10min) — 失败通知主人
救火层: 主人口令 → Coze 跑 rescue.sh (A||B)
```

---

## OpenClaw 引入判断

| 维度 | 结论 |
|------|------|
| 守护职责 | ❌ 不需要，当前三层已覆盖 |
| 技能执行 | 🟡 优选「翻译到 Hermes 原生格式」，不引入运行时 |
| 数据通道 | ✅ 问财 OpenAPI 不依赖 OpenClaw，直接 HTTP 调用 |
| 运维复杂度 | ❌ 增加故障面 |

**推荐策略**: 官方技能 HTTP 调用 / 社区技能翻译到 Hermes 原生 / 不引入 OpenClaw 运行时

---

## Phase 1/2/3 路线图

### Phase 1: 夯实数据底座（当前 → 2 周）
| # | 任务 | 优先级 |
|---|------|--------|
| 1.1 | 问财 API 覆盖验证：5 个 hithink 技能字段完整性 | 🔴 P0 |
| 1.2 | 资金流 cron 稳定性：连续 7 天检查 moneyflow_daily | 🔴 P0 |
| 1.3 | 财务数据链路切换：get_financials.py 优先走问财 | 🟡 P1 |
| 1.4 | Tushare 接口审计：列出可用基础接口+积分门槛 | 🟡 P1 |
| 1.5 | 研报链路打通：验证 insresearch-query + report-search | 🟡 P1 |

### Phase 2: 守护体系 + Coze 降级（2-4 周）
| # | 任务 | 优先级 |
|---|------|--------|
| 2.1 | launchd 注册 gateway（需用户 Terminal.app 手动执行） | 🔴 P0 |
| 2.2 | Hermes 自检 cron 验证（已部署） | 🔴 P0 |
| 2.3 | rescue.sh 端到端测试 | 🔴 P0 |
| 2.4 | Coze 10min 健康检查 Agent 部署 | 🟡 P1 |
| 2.5 | Coze 救火口令 Agent 部署 | 🟡 P1 |
| 2.6 | 移除 coze-bridge 依赖 | 🟢 P2 |
| 2.7 | 日报协作稳定性连续 7 天 | 🟢 P2 |

### Phase 3: 策略智能化 + 覆盖扩展（4-8 周）
| # | 任务 | 优先级 |
|---|------|--------|
| 3.1 | 翻译剩余高价值问财技能到 Hermes 原生 | 🟡 P1 |
| 3.2 | 暗盘资金/主力持仓从降级切到完整模式 | 🟡 P1 |
| 3.3 | v4 回测策略参数优化（逐参数单独回测） | 🟡 P1 |
| 3.4 | 估值引擎升级（对接 DCF 社区技能脚本） | 🟢 P2 |
| 3.5 | 自选股扩容 99→200+ | 🟢 P2 |
| 3.6 | Web 仪表盘增强 | 🟢 P2 |

---

## 系统全景图

```
数据源层: 问财 OpenAPI (5 skills) │ 腾讯 API │ 东财 push2his │ akshare │ Tushare MCP
    ↓
存储层:   SQLite stock_data.db (daily_kline │ moneyflow_daily │ valuation_results │ watchlist)
    ↓
引擎层:   strategy_library (5 indicators) │ backtest_v4 │ bridge.py │ batch_valuation.py │ 估值引擎
    ↓
输出层:   Web 仪表盘 (:8001) │ 每日日报 (Coze+Hermes) │ 守护体系 │ 微信推送
```
