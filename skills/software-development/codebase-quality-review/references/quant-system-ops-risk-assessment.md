# 量化系统运维风险评估框架 (System Operations Risk Assessment)

## 适用场景

对一套正在运行的量化交易系统做全面的**运行可靠性与风险控制评估**，覆盖从数据管线、数据库、备份策略到调度器容灾等全部运维维度。

## 评估清单 (10 项)

### 1️⃣ Cron 作业健康度 — 区分真/假阳性错误

```bash
# 列出所有 cron 状态
hermes cron list

# 对标记为 error 的作业，检查是否为 cron_log_helper 假阳性
# （macOS date +%s%3N 兼容 bug，详见 hermes-cron-pipelines Pitfall #7）
# 真阴性测试：手动触发 cron 检查数据实际写入情况
```

**检查要点：**
- 总作业数 vs 显示 error 的作业数
- 每个 error 的实际管线是否成功（查 cron_push_log 表的 log_tail）
- 失败是持续性的还是偶发的

### 2️⃣ SQLite 数据库性能分析

```sql
PRAGMA journal_mode;        -- 应为 wal（写不阻塞读）
PRAGMA synchronous;         -- 建议 1 (FULL) 或 2 (NORMAL)
PRAGMA page_size;           -- 默认 4096，大型 DB 可考虑 8192
PRAGMA cache_size;          -- 对 6.9GB DB，8MB 偏小，建议 -81920 (80MB)
```

**评估指标：**
| 指标 | 健康值 |
|------|--------|
| DB 文件大小 | 应 < 可用磁盘空间的 50% |
| WAL/SHM 文件 | SHM 应为 32KB，WAL 不应持续增长 |
| 日增量行数 | 应评估每条管线的 INSERT OR REPLACE 量 |
| 索引效率 | 检查 `EXPLAIN QUERY PLAN` |

### 3️⃣ 数据管线链式依赖分析

绘制依赖图，识别单点故障：

```
日线(18:00) → 资金流(18:30) → 因子(19:00) → 回填(20:00)
                                                        ↘ 晨报(07:02)
```

**风险检查点：**
- 下游是否检查上游数据新鲜度？还是假设上游已完成？
- 链上某环节失败，下游是继续用旧数据还是报错？
- 是否有"补执行"机制？（Hermes 重启后不会自动补）
- 依赖深度：链越长，单点故障放大效应越强

### 4️⃣ 新闻/新数据管线写入压力预估

| 新管线 | 预计规模 | 写入策略 | 压力 |
|--------|---------|---------|------|
| 财务指标 | ~5000 行/季度 | UPSERT | 极低 |
| 估值信号 | ~5000 行/日 | INSERT OR REPLACE | 低 |
| 融合评分 | ~5000 行/日 | INSERT OR REPLACE | 低 |
| 新闻情绪 | 100~500 条/日 | INSERT | 极低 |

**判断标准：** 如果日增量 < SQLite 日交易量的 10%，且 WAL 模式下无并发写入冲突，则无需担心。

### 5️⃣ Cron 重试/幂等/告警评估

| 机制 | 状态 | 评估 |
|------|------|------|
| 幂等写入 | ✅ INSERT OR REPLACE | 标准做法 |
| 自动跳过已存在数据 | ✅ 检查行数/数据新鲜度 | 好的 |
| 自动回补 | ⚠️ 部分有 --backfill | 建议全部管线实现 |
| 失败重试 | ❌ 无自动重试 | 建议 +3 次重试 |
| 超时检测 | ❌ 无 | 建议配置 |
| 失败告警 | ❌ 无主动推送 | 建议 +webhook/微信 |

### 6️⃣ SQLite 高并发写锁风险

**分析所有 cron 的时间窗口：**

```
18:00 日线（无竞争）
18:30 资金流（无竞争）
19:00 因子（无竞争）
20:00 回填（无竞争）
[新管线] 20:30~22:30（4 个可能排队）
```

WAL 模式下：写者互斥（同一时间只有一个写事务），读者不阻塞写者。只要 cron 间隔 > 15 分钟，风险极低。若新增管线拥挤在 20:00~21:30，需确保每步 < 15 分钟。

**缓解：**
- 合并估值信号和融合评分为一个事务
- 使用 `PRAGMA busy_timeout=5000` 避免 SQLITE_BUSY
- 所有新管线用 INSERT OR REPLACE 保证幂等

### 7️⃣ 硬件稳定性评估

```
Mac Mini M4 (16GB, 10核, Apple SSD)
基准指标：
- 运行时间        → 建议 < 30 天
- 负载均值        → < 70% CPU 核数
- 内存压力        → free pages > 5000
- Swap 使用       → < 100 次换入换出
- 磁盘使用率      → < 80%

评估命令：
  uptime                                          # 运行时间 + 负载
  sysctl hw.memsize hw.ncpu                       # 硬件规格
  memory_pressure | head -5                       # 内存压力
  df -h /System/Volumes/Data                      # 磁盘可用
  vm_stat | grep -E "pageouts|pageins|swapouts"   # 交换
```

### 8️⃣ 因子数据一致性 (Checksum 验证)

```sql
-- 检查 checksum 覆盖率
SELECT trade_date, COUNT(*) as total,
       SUM(CASE WHEN checksum IS NOT NULL AND checksum != '' THEN 1 ELSE 0 END) as has_checksum,
       ROUND(SUM(...)*100.0/COUNT(*),1) as pct
FROM daily_factors GROUP BY trade_date ORDER BY trade_date DESC LIMIT 10;

-- 验证两条计算路径是否一致
-- 路径 A: factor_pipeline.py (有 checksum)
-- 路径 B: import_daily_factors.py (部分无 checksum)
```

**风险等级：**
- < 50% 覆盖率 → 🔴 严重
- 50~90% → 🟡 中等
- > 90% → 🟢 良好

### 9️⃣ 备份策略完整性检查

```bash
# 检查备份是否按预期运行
sqlite3 stock_data.db "SELECT * FROM cron_push_log WHERE job_name LIKE '%备份%' ORDER BY id DESC LIMIT 10;"

# 列出所有备份文件
ls -la backups/db_daily/

# 验证备份完整性
sqlite3 backup.db "PRAGMA integrity_check;"
```

**备份检查清单：**
| 检查项 | 通过标准 |
|--------|---------|
| 备份频率 | 每日 1 次 |
| 前置检查 | PRAGMA integrity_check |
| 大小校验 | 备份 > 原始 50% |
| 保留策略 | 30 天自动清理 |
| 异盘备份 | 至少一周一次到不同磁盘 |
| 最近备份 | 不超过 48 小时 |

### 1️⃣0️⃣ Hermes Cron 的进程内调度器容灾

**Hermes cron 的本质：** 运行在 Hermes 进程内的守护线程 + `jobs.json` 持久化。重启后从 json 恢复配置，但**错过窗口的任务不会自动补执行**。

| 场景 | 行为 | 影响 |
|------|------|------|
| Hermes GUI 关闭后重开 | 进程终止，cron 停止 | 错过所有停机期间的任务 |
| macOS 重启 | 同上 | 同上 |
| Hermes 更新 | 进程重启 | 错过更新期间的定时任务 |
| Hermes 崩溃 | 进程退出 | cron 停止运行直到手动恢复 |

**缓解方案（按可靠性从高到低）：**
1. Hermes 配置为 macOS LaunchAgent 随系统自启
2. 关键管线在系统 crontab 中注册兜底（双触发）
3. 每天 01:00 增加巡检 cron，检查当天所有管线是否成功，对失败做补执行
4. 所有数据写入用 INSERT OR REPLACE 保证幂等（重放安全）

## 优先级矩阵

| 优先级 | 发现类型 | 示例 |
|--------|---------|------|
| 🔴 高 | 备份中断、数据丢失风险 | 无活跃每日备份 > 48h |
| 🟡 中 | 假阳性告警、数据一致性缺口 | cron_log_helper macOS bug |
| 🟢 低 | 性能优化、运维完善 | cache_size 调优 |

## 报告产出格式

评估结果应写为结构化文档，每项评估包含：
1. **现状**（命令/web_extract 的实际输出）
2. **诊断**（根源分析）
3. **风险等级**（🔴/🟡/🟢）
4. **修复建议**（具体命令、SQL、配置更改）

---

*本框架源于 2026-07-07 对 ~/my_quant_system 的全维度风险审计。*
