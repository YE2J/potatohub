---
name: code-review-checklist
title: "代码审查检查清单"
description: "按场景分类的评审检查清单，每项含验证方法。4-Agent评审时自动加载。"
tags: [review, checklist, code-quality]
---

# 代码审查检查清单

## 用法
4-Agent 评审时，worker 必须先加载此 skill 获取对应场景的清单，
**逐项执行验证后再写评审报告**。

---

## 通用基线（所有评审必检）

| # | 检查项 | 验证方法 |
|:-:|:-------|:---------|
| 1 | 数据库列类型 vs Python 比较操作符兼容 | `PRAGMA table_info(xxx)` 确认类型，检查 `== '1'` / `== 1` / `is None` 混用 |
| 2 | 文件路径在运行时 CWD 下存在 | `ls <path>` 确认文件存在 |
| 3 | shell 脚本可执行 | `stat -f %A <file>` — 确认有执行位 |
| 4 | 数值单位转换链无重复 | 从源 API → DB → 引擎 → 输出，追踪 元/万元/亿元 |
| 5 | 日期格式跨表一致 | `SELECT typeof(trade_date), trade_date FROM xxx LIMIT 1` 对比 |
| 6 | SQL 参数化（无 f-string 拼接） | grep 搜索 `f"`+WHERE 中直接拼接变量 |
| 7 | 连接释放 | 每个 `conn` 必须有 `close` 或 `with`，try/finally 包裹 |
| 8 | 空结果集防御 | `fetchone()` 后 `is None`；`fetchall()` 后 `len()>0` |
| 9 | 异常无敏感信息泄漏 | except 中不 print 含 Token/密码/API Key 的变量 |
| 10 | API 重试机制 | Tushare 等外部调用需 sleep + 重试 |

---

## 引擎评审（L1/L2/L3）

| # | 检查项 | 验证方法 |
|:-:|:-------|:---------|
| 11 | 评分权重总和=100% | 累加 `weight_map` 值，确认归一正确 |
| 12 | 阈值不硬编码 | 温度标签应读引擎定义，不从晨报抄常数 |
| 13 | 缺失数据降级 | 模拟某表无数据时，评分是否回退+权重归一 |
| 14 | 跨表 trade_date 格式统一 | 引擎读的格式 vs 写的格式一致 |
| 15 | 依赖表时效性 | 输入表最新日期 ≥ 引擎运行日期 - 2 |

---

## 数据管线评审

| # | 检查项 | 验证方法 |
|:-:|:-------|:---------|
| 16 | cron script 路径解析 | no_agent: `~/.hermes/scripts/` 搜索；workdir 不影响搜索路径 |
| 17 | 脚本 +x 权限 | `ls -la` 确认 |
| 18 | trade_cal.is_open 类型 | INTEGER，Python 用 `int(...)==1` |
| 19 | 非交易日跳过双重确认 | cron 1-5 限定 + 脚本内 trade_cal 检查 |
| 20 | 并发写防冲突 | 同时段多个 cron 写同表？SQLite busy_timeout 设置？|
| 21 | 增量幂等 | INSERT OR REPLACE / 去重检查 |
| 22 | 信号处理器 | signum=None 边界处理 |

---

## 历史高频故障（Xiaomi 统计）

| 排名 | 故障模式 | 频次 | 典型表现 |
|:----:|:---------|:----:|:---------|
| 1 | 单位/量纲错误 | 5 | 引擎转亿元，下游再除10000 |
| 2 | 跨数据源不匹配 | 4 | THS/DC 代码体系不同但假设相同 |
| 3 | 类型/模式不匹配 | 3 | is_open int vs str；日期格式混用 |
| 4 | 运行时环境故障 | 3 | cron 无+x、路径不存在 |
| 5 | 连接泄漏 | 2 | try/finally 缺失 |
