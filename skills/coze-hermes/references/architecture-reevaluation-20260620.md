# Coze 角色重新评估（2026-06-20）

## 背景

三 Agent（量化架构师 + Coze平台专家 + SRE）并行评审了 Hermes + Coze 架构。

## 核心结论

### Coze 从「对等协作者」降级为「数据补充源 + 兜底守护」

**旧定位（v1，已废弃）：**
- Coze 和 Hermes 互相对等
- 双方各自出日报，互读互评
- 双向守护（互相救对方）

**实际运行状态（2026-06-20 勘验）：**
- Coze 侧文件同步 **从未双工运行**（共享目录中 Coze 侧 0 输出）
- 日报 cron (`00b779e99fdf`) 因等不到 Coze 信号文件而 error 降级
- 双向守护理论存在但未部署完成

### 硬约束

| 约束 | 影响 |
|------|------|
| Coze 定时任务最小间隔 10 分钟 | 不能做实时守护，只能做兜底 |
| Coze V3 Chat API 输出上限 16K tokens | 不适合批量数据传输 |
| Coze bash 执行依赖桌面端存活 | 桌面端挂了 bash 也挂 |

### 新定位

```
Coze（保留）:
  ├─ 恒生聚源 5 类独有数据（机构预测/舆情穿透/ETF申赎/招投标/产业链）
  ├─ 10min 深度健康检查（curl /health + 心跳新鲜度）
  ├─ 主人口令救火（"救Hermes" → bash rescue.sh）
  └─ 用户多端交互（手机/网页/桌面）

Coze（砍掉）:
  ├─ 不做 30s/60s 心跳（由 Hermes cron selfcheck 替代）
  ├─ 不出独立日报（由 Hermes 统一出）
  └─ 不被 Hermes 救（云端 Agent 永不依赖 Mac Mini）
```

### 守护三层架构（v2）

```
L1: launchd KeepAlive（治本，秒级拉起）
L2: Hermes selfcheck cron（60s 心跳 + HTTP 自检）
L3: Coze 10min 兜底检查 + 主人口令救火
```

### 文件同步现状

`~/quant_shared/daily_reports/` 中仅 Hermes 单侧产出。Coze 侧信号文件（`_ready_coze_*`）从未出现。文件同步方案未经过真实双工验证。

### 后续计划

- Phase 1: 问财 OpenAPI 替代 Tushare/akshare 不稳定接口
- Phase 2: 激活 launchd + 修 cron Python 路径 (P0 完成)
- Phase 3: Coze 仅保留恒生聚源查询 + 10min 兜底 + 救火口令
