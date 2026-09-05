---
name: kanban-worker-fleet
description: Set up and manage a fleet of Hermes worker profiles with different LLM backends, connected through the Kanban system for automatic task decomposition and distribution.
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [kanban, multi-agent, orchestration, profiles, workers]
    related_skills: [hermes-agent]
---

# Kanban Worker Fleet

Set up multiple Hermes worker profiles — each backed by a different LLM provider/model with a distinct identity and specialization — wired through the Kanban system so complex tasks are automatically decomposed and distributed across your model fleet.

## When to Use

- You have API keys for 3+ LLM providers (DeepSeek, GLM, Kimi, Qwen, NVIDIA, etc.) and want them all to participate in tasks
- You want complex tasks automatically split by domain (research → Kimi, reasoning → GLM, coding → NVIDIA, etc.)
- You want a "fire and forget" workflow: send a task, have it auto-distributed, get results back

## Architecture

```
User (default profile)
  │
  ▼
Orchestrator (deepseek-v4-flash)
  │  Decomposes task → creates Kanban cards
  ▼
Kanban Board
  │  ready tasks picked up by dispatcher
  ▼
Workers (parallel execution)
  ├── worker-kimi     (Kimi K2.6)              — 研究员：搜索、分析、长文档、逻辑验证
  ├── worker-glm      (GLM-5.1)                — 工匠：代码实现、架构评审、结构化输出
  ├── worker-minimax  (MiniMax M2.7)           — 审计师：深度审计、交叉验证、性能安全
  ├── worker-xiaomi   (MiMo v2.5)              — 实现者：代码验证、可行性与边界条件
  └── worker-qwen     (Qwen3.7-Plus)            — 智囊：方案论证、综合分析、行业研究（2026-08-22加入）
```

### 4-Agent Code Review / Multi-Model Evaluation Pattern

This is a **verified workflow** (2026-07-09, expanded 2026-07-12) for multi-model parallel evaluation:

1. **Default profile** (you) drafts code or defines a task
2. **Create 4 Kanban cards** — one per worker profile, all with **no parents**
3. **Wait** for all workers to reach `done` status (check via `hermes kanban list`)
4. **Create synthesis card** — `assignee=orchestrator` with **NO `--parent` flag**. Body says `kanban show` each worker's results
5. Orchestrator runs → reads worker handoffs via `kanban show` → synthesizes → `kanban_complete`
6. **You read the result** via `kanban_show(<synthesis_task_id>)` — results are NOT auto-pushed

**CRITICAL: Do NOT use `parents=[t1,t2,t3]` on the synthesis card.**
Any worker crash → synthesis card deadlocks forever. The parent-free pattern above avoids this entirely.

**Typical latency:**
- GLM-5.1: ~68s (code tasks)
- Kimi K2.6: ~172s (research tasks)
- MiniMax M2.7: ~80-118s (audit tasks)
- MiMo v2.5: ~30-60s (lightning fast, code tasks)
- Dispatch cycle: up to 60s before gateway picks up new cards
- Total code review roundtrip: ~3-6 minutes (4 workers + synthesis)

### 手动 5 卡评审 + 主会话合成变体（2026-08-30 实测，用户实际使用方式）

不建 orchestrator 合成卡，主会话（Hermes）直接读卡汇总，流程：

1. **建 5 张无 parents 卡**（每 worker 一张，各评各的维度），`--max-runtime 15m`
2. **后台等待**：`python3 ~/.hermes/scripts/kanban_await.py <id1> ... <id5> --timeout 900`（background + notify，实测 5 卡 356s 全部 done，输出自动带各卡 summary）
3. **读完整报告**：`~/.hermes/kanban/attachments/<id>/REVIEW_REPORT.md`（不是 summary——summary 只有一两行结论）
4. **主会话汇总**：合并 P0/P1/P2 清单，标出多家命中项（命中次数 = 置信度），据此修正方案后自己执行
5. **归档**：`hermes kanban archive <id>`。**⚠ 实测 kanban_await 不自动归档**（2026-09-03：6 张 done 卡在 await 退出后仍全部滞留 done，须手动逐张 archive；用户问「已完成的是不是还未释放」触发修正）——每波 await 完成后主动 `hermes kanban list` 确认板清空，勿依赖自动归档。

**评审卡 body 三段式**（已验证 5/5 worker 产出完整 REVIEW_REPORT.md）：
1. **公共背景**：问题根因（带实测证据）+ 拟定方案（含文件路径+行号）+ 数据库/环境关键事实
2. **各自维度**：每卡一个视角（架构/逻辑/审计/实现/方案论证），写清要审的具体问题
3. **输出要求**：真实读文件再评论、证据带文件:行号、按 P0/P1/P2 分级、完整报告写 REVIEW_REPORT.md 附件而非 summary、诚实铁律（无命令输出=未验证）

**建卡引号坑**：`hermes kanban create --body` 的多行 body 用 python subprocess 传参最稳；body 字符串内含 ASCII 双引号会破坏外层字符串——用三引号包裹或把内部引号换成中文引号「」。

### 执行卡门禁式派发变体（2026-09-03 实测：P3.5 全市场扫描管线）

多阶段执行管线（非评审）有用户门禁时，**不要一次 fan-out 全部卡**，按波次放行：

1. **G0 侦察硬门槛先行**：第一张卡 = 只读侦察卡（行数/格式/主键可行性等确定性事实，body 里 `PRAGMA query_only=ON` + `.timeout 120000` + 「不接受据估计」）。worker done 后**主会话独立复核**（亲自重跑关键 SQL 比对数字），复核通过才请用户确认放行下一波。侦察结论直接是后续卡（如转换/覆盖率）的验收分母——错了全链报废。
2. **建卡实操**：多行 body 先 write_file 到 `<项目>/.xxx_body.md`，再 `hermes kanban create "<标题>" --body "$(cat ...)"`；加 `--idempotency-key <卡名>-<日期>` 防重派；`--workspace dir:<项目绝对路径>` 让 worker 落在项目目录；建完立即 `rm` 临时 body。body 要求 worker 交付物写**绝对路径**（workspace 可能被 GC）。
3. **等待**：`python3 ~/.hermes/scripts/kanban_await.py <id1>... --timeout 1800`（background + notify），完成自动带 summary；不需轮询。
4. **独立复核铁律（worker 自报可能事实错误）**：本会话 K1b 报「THS 止于 06-26、两源无重叠」，主会话复跑发现 THS MAX=07-03——worker 用纯 6 位代码查 000001，**漏掉了 07 段带 .SZ/.SH 后缀的行**（代码格式突变）。凡 worker 交付数字结论先重跑 SQL 再采信；发现错误由聚合器直接修正交付文档并记录根因（不退回重跑，省轮次），同时修正分工文件里被它影响的基线行。
5. **侦察卡必带预检（防静默漏行/错数）**：①数据源存在代码格式突变日（某月起带后缀）→ 统计前先跑 `SELECT substr(date,1,7) ym, SUM(code LIKE '%.%') ... GROUP BY ym` 看格式分布；②SQLite 日期比较防 `YYYY-MM-DD` vs `YYYYMMDD` 字典序坑（统一格式再比较，否则 WHERE/COUNT 静默错）；③一股一日多行检查（GROUP BY code,date HAVING COUNT(*)>1）在建 PK 前必做；④单位未知的金额/量字段用 `vol×close≈amt` 手算判定单位（偏差 <1% 即证——本会话 0.47% 证 THS=元/股、0.11% 证 tushare=万元/手），入库前统一单位并在 body 写死换算系数（如 /10000、/100），遗漏即单位灾难。
6. **派发节奏**：G0 通过 → 可并行的执行卡同批（建表+字典）→ 有依赖的（采集→计算→转换→审计）顺序放行 → 每波用户确认。审计卡 assignee ≠ 执行卡 assignee（审计员不自行修复，只出偏离报告）。
7. **空洞验收防伪（2026-09-03 实测 K4）**：worker 会用「可验的代理量」冒充「不可验的验收量」——K4 验收要求「抽 3 股手算 ratio 与库值一致」，但当时仅 1 个交易日、ratio_5d/10d/20d 全 NULL 根本无值可算；worker 实际手算的是 net_elg_lg_amt（当日有值的中间量），却声称「ratio 手算通过」，|ratio|>100 异常 0 只也是 ratio 全 NULL 下的空洞通过。复核时先问「声称验证的那个量现在有没有值」：冷启动期窗口指标必为 NULL → 该项验收**标记挂起并显式移交后续审计卡必查项**（本次移交 K7：数据满 ≥6 日后重跑计算器 + 抽样手算 ≤1e-6 补验），不采信代理量冒充、不当作已通过、不阻塞后续依赖卡派发。
8. **执行卡复核清单（聚合器对每张 done 卡逐项重跑）**：行数（== 上卡基线）、source/格式隔离（无混写）、逐字段换算对照（源表原值 ÷系数 == 目标值）、公式手算抽查（net/ratio 精确 match）、幂等（重跑 COUNT 不变）、交付物绝对路径存在。每项贴真实命令输出；worker 自报「全过」不作数。
9. **审计卡自身也会漏 P0——审计 body 必须含日期覆盖检查（2026-09-03 K7 实测）**：K7 审计员只重跑「最新日」+ 单日手算，全链路通过，却漏了 `scan_ratio_daily` 只有 1 个 trade_date（历史 262 天 ratio 从未回填）——审计「最新日 OK」≠「全链覆盖 OK」。聚合器补查 `SELECT COUNT(DISTINCT trade_date), MIN, MAX` 才发现。审计卡验收清单固定加三项范围断言：`COUNT(DISTINCT date/trade_date)` 是否 == 期望交易日数、`MIN/MAX` 是否 == 期望区间、两段 source 是否都实际进入计算（不只看最新日样例）。审计员与执行员同犯此病：都倾向验「单点正确」而非「全域覆盖」。
10. **worker 因卡 body 内嵌的数据源假设 block 时，先查项目既有已验证路径再选补救（2026-09-03 K8 实测）**：K8 卡 body 写死「必须用 daily_kline.pct_change」，worker 实测该列扫描窗口 99.7% NULL + 早期 InnerCode 短码 → 正确 kanban_block 并给 A/B/C 三方案（截短段/补拉历史/冻结）。聚合器复核发现**用户 P2 框架从不用 pct_change 列**——`p2_backtest.py` 用 `factor_cross_section.close`（全 6 位、close 0 NULL、2020 起）自算 `fwd_close/close-1`，这才是项目已验证的收益路径。正确方案是换源（factor.close 自算 + 尾段补缺），而非 worker 建议的回填历史。教训：**卡 body 不要把「某一列/某一表」写成唯一可行源**——项目里同一指标常有已验证的等价计算路径（close 自算 vs 现成 pct 列）；worker block 的偏离报告只代表「卡前提不成立」，不代表「数据缺失」，聚合器须先盘点项目既有回测/计算框架再裁决。偏离报告结论可能与聚合器实测相左（K8 报「需回填」，实为「换源即可」）。
11. **管线脚本早期为子集场景写的硬编码过滤器，在数据扩源后成为静默 bug（2026-09-03 K4 v2 实测）**：K4 计算器在 K3 单源期写成 `SOURCE_FILTER = "source='tushare_api'"` + `write_results` 只写 target_date 单日——K5/K6 扩到两源 263 日后，THS 段被过滤器排除、历史 262 天从不回填，而脚本 docstring 还写着「K5 并入 THS 后自然含两源」（注释与代码不符）。修复 = 移除 source 过滤 + 新增 `--backfill` 全量清空重写模式 + denom=0 时 warmup=1。教训：凡脚本在子集期（单日/单源）验收过、后被喂全量数据，复核清单必加「**数据扩源后的行为验证**」：`COUNT(DISTINCT date)` 是否随扩源增长、新增源段是否真参与计算（抽新增源段日期验证输出非 NULL）、脚本内硬编码过滤是否与 docstring 宣称一致。
12. **blocked 卡 = 偏离冻结待裁决，恢复流程是 comment 注入裁决 + unblock，不是 complete + archive（2026-09-03 K8 实测）**：worker 因卡 body 内嵌前提不成立（如收益源列全 NULL）主动 `kanban_block`（kind=needs_input）后，聚合器应先读 block 原因/偏离报告 → **聚合器亲自补查**（worker 结论可能与聚合器实测相左，如 K8 报「需回填历史数据」实为「换既有已验证源即可」）→ 交用户裁决 → 用 `hermes kanban comment <id> "【裁决·<方案>】…执行指令…"` 注入修订后的执行路径（含新事实/新验证项）→ `hermes kanban unblock <id> --reason "…"` → worker 继续跑同一张卡（不重开新卡，保留偏离审计链）。skill 旧文「blocked 直接 complete + archive」只适用于 worker 已产出完整结论的情况；偏离冻结场景必须 unblock 续跑。
13. **统计验证卡（IC/分组/胜率）诚实不达标交付模式（2026-09-03 K9 实测）**：信号统计验证卡的结果可能是「不达标」——处理范式：①卡 body 预先写死达标判定表（如 IC>0 且 ICIR>0.3、十分位单调、Top-Bottom 扣成本后年化>0），worker 必须照表逐项打勾并如实写入未通过项；②不达标时 **worker 禁调参硬凑、禁反转符号凑达标**（P2 数据窥探教训），只允许在报告「负 IC 解读」节给出假设（如大单流入=反向信号/拉高出货）并建议「另开任务验证反转方向」——反转是独立探索，不是本卡调参；③聚合器复核统计数字必须**用独立方法重算**（如 worker 用 pandas 算 IC，聚合器用 scipy spearmanr 逐日复算 IC/ICIR，SQLite 无 CORR 需脚本算），一致才采信；④门禁失败即按纪律不挂 cron、不降级「先用用看」，把判定表和止损/反转/加过滤三选项交用户裁决。诚实的不达标是有效结果（负 IC 本身就是强信息），不是失败。
14. **批量卡全 done 后聚合器统一做数据层总复核（防链式假绿）**：逐卡复核之外，在「全链完成、交用户确认」前补一次跨表断言——上游表行数 == 下游表行数（本会话 scan_mf_daily == scan_ratio_daily == 1,368,204）、`COUNT(DISTINCT date)` 等于期望交易日数（263）、`MIN/MAX` 等于期望区间、source 分布与分段衔接正确（ths 止 07-03、tushare_api 自 07-06 无交叉）。链式管线中每张卡都「看着绿」，聚合器总复核仍可能抓到最后一层表只有 1 天数据这种链尾缺口。

## Setup Steps

### 1. Verify API keys are recognized

```bash
hermes auth list
# Each provider should show as active (← marker, not "auth failed")
```

### 2. Create worker profiles

```bash
# Clone from an existing profile to inherit config and .env
hermes profile create worker-glm --clone-from default
hermes profile create worker-kimi --clone-from default
hermes profile create worker-qwen --clone-from default
hermes profile create worker-nvidia --clone-from default
```

### 3. Configure each worker's model

```bash
# GLM (智谱) — current: glm-5.1
# Confirmed working via z.ai provider. Clear base_url (cloned profiles may inherit wrong endpoint).
hermes config set model.provider z.ai --profile worker-glm
hermes config set model.default glm-5.1 --profile worker-glm
hermes config set model.base_url '' --profile worker-glm

# Kimi (Moonshot) — current: kimi-k2.6
# Available: kimi-k2.6 (general multimodal), kimi-k2.7-code (newest coding), kimi-k2.7-code-highspeed
# ⚠ Provider name must be 'kimi-custom' (NOT 'kimi-coding-cn'). The latter fails with HTTP 401
# even with a valid API key. 'kimi-custom' reads inline api_key from providers.kimi-custom.api_key.
hermes config set model.provider kimi-custom --profile worker-kimi
hermes config set model.default kimi-k2.6 --profile worker-kimi
hermes config set model.base_url https://api.moonshot.cn/v1 --profile worker-kimi
hermes config set providers.kimi-custom.base_url https://api.moonshot.cn/v1 --profile worker-kimi

# MiniMax Auditor — minimax-m2.7
hermes profile create worker-minimax --clone-from default
hermes config set model.provider minimax --profile worker-minimax
hermes config set model.default minimax-m2.7 --profile worker-minimax
# Optionally write SOUL.md: cp ~/.hermes/skills/autonomous-ai-agents/minimax-auditor/SKILL.md ~/.hermes/profiles/worker-minimax/SOUL.md

# Xiaomi MiMo — mimo-v2.5
# Plugin: hermes-agent/plugins/model-providers/xiaomi (built-in)
# ⚠ supports_health_check=False → hermes status does NOT show this provider even when key is valid
hermes profile create worker-xiaomi --clone-from default
hermes config set model.provider xiaomi --profile worker-xiaomi
hermes config set model.default mimo-v2.5 --profile worker-xiaomi
hermes config set model.base_url '' --profile worker-xiaomi
# Write SOUL.md for reviewer identity

# worker-nvidia was removed 2026-06-16 (per user request).
# worker-qwen: removed 2026-06-16, RE-ADDED 2026-08-22 (Qwen3.7-Plus @ alibaba-coding-plan, 国内端点).
# 配置: provider=alibaba-coding-plan, model=qwen3.7-plus, key 在 profile .env 的 ALIBABA_CODING_PLAN_API_KEY/BASE_URL
```

### 4. Write SOUL.md for each worker

Each worker needs a distinct identity with clear specialization. Write `~/.hermes/profiles/<worker>/SOUL.md` with:
- Name and model identity
- Specialized domain
- Communication style
- Language preference

See `references/worker-souls.md` for the full templates used in this setup.

### 5. Configure the orchestrator

```bash
hermes profile create orchestrator --clone-from default
hermes config set model.provider deepseek --profile orchestrator
hermes config set model.default deepseek-v4-flash --profile orchestrator
```

Write `~/.hermes/profiles/orchestrator/SOUL.md` describing its role as task decomposer and distributor.

### 6. Enable Kanban in the default profile

```yaml
# In ~/.hermes/config.yaml:
kanban:
  orchestrator_profile: orchestrator
  auto_decompose: true
  dispatch_in_gateway: true
  dispatch_interval_seconds: 60
```

### 7. Initialize Kanban

```bash
hermes kanban init
# Discovers all profiles automatically
```

### 8. Ensure gateway is running

```bash
hermes gateway status
# If stopped: hermes gateway start
# The gateway hosts the kanban dispatcher
```

## Verification

### Quick connectivity test per worker

```bash
# Test each worker individually (parallel loops on macOS are unreliable — no `timeout` command, and shell backgrounding can cause timeouts)
for p in worker-glm worker-kimi worker-minimax worker-xiaomi; do
  echo "=== $p ===\n$(hermes -p "$p" chat -q "只回OK" 2>&1 | tail -3)"
  echo ""
done
# If 1 message or error text: check provider/key/model.

### End-to-end test

```bash
# Trigger the orchestrator with a complex task
hermes -p orchestrator chat -q "将以下任务分解并分配给合适的worker：分析A股最近一周走势并给出投资建议"
```

Then check the board:

```bash
hermes kanban list
# Should show tasks with status: ready → running → done
```

## Pitfalls

### delegate_task ignores delegation config (Hermes bug)

`delegate_task` does NOT read from the `delegation.model` / `delegation.provider` config section. It appears to hardcode the subagent model to whatever was active at session start, ignoring later config changes and the explicit delegation settings.

**Symptoms:**
- `delegate_task` uses `qwen-plus` even when `delegation.model: deepseek-v4-pro`
- Error 401 if the hardcoded model's key is invalid
- `/reset` does NOT fix it — the bug persists across sessions

**Workaround A** — Use `terminal` to spawn worker profiles directly:
```bash
# Parallel execution with individual model control
hermes -p worker-glm chat -q "analyze financial data" 2>&1 &
hermes -p worker-kimi chat -q "research company history" 2>&1 &
wait
```

In Python via execute_code:
```python
from hermes_tools import terminal
terminal("hermes -p worker-glm chat -q '...' ", background=True, notify_on_complete=True)
terminal("hermes -p worker-kimi chat -q '...' ", background=True, notify_on_complete=True)
```

**Workaround B** — Use the Kanban system (gateway dispatcher spawns profiles directly):
```bash
hermes -p orchestrator chat -q "decompose and distribute this task..."
```

The Kanban dispatcher bypasses `delegate_task` entirely — it spawns worker profiles natively, so this bug doesn't affect it.

### Wrong base_url in cloned profiles

When cloning a profile, the `model.base_url` may point to the source profile's provider API. **Always clear or correct base_url** for each worker:

```bash
hermes config set model.base_url '' --profile worker-glm
```

Symptom: API calls fail with authentication errors even though the key is valid, because requests are sent to the wrong endpoint.

### DashScope China endpoint: env var vs direct api_key

The `alibaba` provider may not resolve `DASHSCOPE_API_KEY` from `.env` correctly when using a China-endpoint key. If 401 persists even with correct base_url and valid key:

```bash
# Set the key directly in model config (not env)
hermes config set model.api_key "sk-..." --profile worker-qwen
```

Alternatively use `execute_code` to inject the key into config.yaml because `hermes config set` may redact long secret values. See `references/dashscope-china-endpoint.md` for full diagnostic steps.

### API key not inherited

Cloned profiles get their own `.env` copy at clone time. If you add new API keys to the default `.env` later, they won't propagate to existing profiles. **Re-clone or manually sync** the `.env` file.

### Expired/invalid API keys

Run `hermes auth list` to check credential health. A `(re-auth may be required)` note or `auth failed` status means the key needs renewal.

### Qwen/DashScope account arrears

If ALL DashScope models (including previously-working ones like `qwen-plus`) suddenly return HTTP 400 "Arrearage — Access denied, account not in good standing": the account has overdue payment. Even models that were free-tier may be blocked. Top up at https://dashscope.aliyun.com/. After recharge, `qwen3.7-max` should work immediately.

### Kimi provider name must be `kimi-custom`

The provider name `kimi-coding-cn` is NOT recognized by Hermes for API key resolution. Even with a valid inline key in `providers.kimi-coding-cn.api_key`, calls return HTTP 401.

**Fix:** Use `kimi-custom` as the provider name instead:
```bash
hermes config set model.provider kimi-custom --profile worker-kimi
hermes config set providers.kimi-custom.api_key 'sk-...' --profile worker-kimi
hermes config set providers.kimi-custom.base_url https://api.moonshot.cn/v1 --profile worker-kimi
```

**Available Kimi models (verified 2026-07-12):**
- `kimi-k2.6` — general multimodal with reasoning, 262K context
- `kimi-k2.5` — previous generation
- `kimi-k2.7-code` — latest coding-specific model
- `kimi-k2.7-code-highspeed` — high-speed variant of k2.7-code
- Various `moonshot-v1-*` legacy models

`kimi-k2.6` is still fully operational (confirmed working).

### Dispatcher not picking up tasks

Check:
1. Gateway is running: `hermes gateway status`
2. Kanban is initialized: `hermes kanban list` should work
3. Tasks are in `ready` state (not `todo` with unmet dependencies)
4. The worker profile's model actually works (test with `hermes -p <worker> chat -q "test"`)

### Worker crashes silently (protocol violation)

Kimi K2.7-code has been observed to exit without calling `kanban_complete` or `kanban_block` (protocol violation), leaving the task `running` until the claim TTL expires. The dispatcher then retries (up to `failure_limit`). If the second retry also crashes, the task is marked `failed`.

**Symptom:** `kanban show <task_id>` shows run outcome "worker exited cleanly (rc=0) without calling kanban_complete or kanban_block — protocol violation"

**Impact:** If the synthesis card has `parents` dependency on the failed card, it stays `todo` forever. The parent task is NOT auto-promoted.

**Fix (proactive — prevent the crash):** Add `fallback_providers` to `~/.hermes/profiles/worker-kimi/config.yaml`:
```yaml
fallback_providers:
  - provider: deepseek
    model: deepseek-v4-flash
  - provider: deepseek
    model: deepseek-v4-pro
```
When Kimi crashes, the dispatcher auto-falls back to DeepSeek for that card. Output quality differs but the review completes instead of deadlocking.

**Fix (reactive — after crash):** `kanban_reclaim <failed_task_id>` to retry, or create a new synthesis card without parents using completed results only.

### `hermes status` misses some providers

Some providers have `supports_health_check=False` in their plugin definition, meaning `hermes status` (or `hermes auth list`) will NOT detect them even with a valid API key. This does NOT mean the provider is broken — the health check endpoint simply returns 401 even with a valid key.

**Affected providers:**
- **Xiaomi MiMo** (`xiaomi` provider, `XIAOMI_API_KEY`) — `/v1/models` returns 401 with valid key
- **Kimi CN** (`kimi-custom` provider, `KIMI_CN_API_KEY`) — uses `api.moonshot.cn`, doesn't show in default status check which only looks at `KIMI_API_KEY`. Old provider name `kimi-coding-cn` is broken for auth — do NOT use it.

**Diagnostic:** Test directly via curl:
```bash
# Xiaomi MiMo
curl -s https://api.xiaomimimo.com/v1/chat/completions \
  -H "Authorization: Bearer $XIAOMI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"mimo-v2.5","messages":[{"role":"user","content":"OK"}],"max_tokens":5}'

# Kimi CN
curl -s https://api.moonshot.cn/v1/chat/completions \
  -H "Authorization: Bearer $KIMI_CN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"kimi-k2.7-code","messages":[{"role":"user","content":"OK"}],"max_tokens":5}'
```
A valid response (non-401) confirms the key works.

### Profile 删除被桌面端 scheduler 复活（2026-08-27 实测 P0）

`hermes profile delete <name>` 输出 "✓ Removed" 后，**桌面端（Electron）主进程持有启动时固化的 profile 列表**（`hermes_cli/profiles.py` 的 `profiles_to_serve` 在 web_server 启动时做一次目录扫描），之后每 tick（约 1 分钟）自动重建缺失 profile 目录（SOUL.md/sessions/memories/cron/executions.db 完整骨架）。实测删除后 ~40s 目录复活，`hermes profile list` 重新显示该 profile。**gateway restart 无效**（重建源是桌面 web_server 的 Desktop cron scheduler，不是 gateway）。

**止血方案（占位文件）**：
```bash
rm -rf ~/.hermes/profiles/worker-auditor/ && touch ~/.hermes/profiles/worker-auditor && chmod 600 ~/.hermes/profiles/worker-auditor
```
同名 0 字节文件会骗过 `profiles_to_serve` 的 `if not entry.is_dir(): continue`（文件被跳过），scheduler 不再 tick、不再重建。90s 实测稳定。

**终解**：重启桌面 app（重扫 profile 列表）后删除占位文件。占位文件在桌面端重启前都有效；重启后必须手动清理。

**纪律（铁律）**：删除类操作后必须等 **1-2 个 scheduler tick 周期（~90s）复查**目录是否复活，不能只看即时状态（`profile list`/`ls` 即时通过≠删除成功）。

### Profile 废弃/重命名时的 kanban.db 全量迁移清单

只改 `tasks.assignee` 不够——worker 评审卡的历史事件散落在多个表，漏一处就留下新旧混用：

| 对象 | 操作 | 坑 |
|---|---|---|
| `tasks.assignee` | `UPDATE ... WHERE assignee='旧名'` | 主迁移，最简单 |
| `task_events.payload` | `UPDATE SET payload=REPLACE(payload,'旧名','新名')` | **JSON 内嵌 assignee，本会话实测 41 条漏迁** |
| `tasks.body/title/result` | `REPLACE(...)` 文本替换 | 历史卡正文可留作背景（评审卡 body 属预期引用），但 assignee 字段必须干净 |
| 备份 | 迁移**前** `cp kanban.db backups/` | 本次教训：备份落在 assignee 迁移后、文本替换前，归属不可回滚 |

### Worker 行为两个易误判状态（2026-08-28 实测）

1. **Worker 完成但详细报告未落盘**：status=done、summary 有结论，但 `result` 为空、无附件（本次 worker-qwen 全丢只剩一句话）。读取顺序：`kanban show <id>` 看 summary → result 空则查 `~/.hermes/kanban/attachments/<id>/`（**2026-08-30 实测 5 张卡 5 份 REVIEW_REPORT.md 全部落在 attachments/，workspaces/ 为空**；早期报告也都在 attachments/ 下）→ 都没有只能靠 summary 或重跑。**预防**：评审卡 body 明确要求"完整报告写入附件（REVIEW_REPORT.md）或 result，不要只写 summary"。
2. **status=blocked 有两种情形，处理不同（2026-08-28/09-03 实测）**：①worker 主动 `kanban_block`（kind=needs_input）因发现 P0/偏离需人工裁决——**不是故障**。读 `kanban show` 的 summary 与 block reason/偏离报告后，若结论已完整可 complete+archive；若是「偏离冻结待续跑」场景则 **comment 注入用户裁决 + unblock 续跑同一张卡**（见上文「执行卡门禁式派发变体」第 12 条，勿直接 complete 丢弃未完成工作）；②超过 `--timeout` 被调度器置 blocked——同上读卡，worker 结论常已完整，`kanban complete <id> --summary "已读取结论"` 补完成 + archive，别当死卡丢弃。

### 60s dispatch interval latency

The gateway dispatcher runs on a `dispatch_interval_seconds` cycle (default 60s). New `ready` cards are not picked up immediately — they wait for the next tick. Combined with worker execution time (~1-3min), total round-trip for a 3-worker + synthesis workflow is ~3-5 minutes. Not suitable for quick iteration.

**Speed-up: change to 15s:**
```yaml
# ~/.hermes/config.yaml
kanban:
  dispatch_interval_seconds: 15
```
**⚠ Requires gateway restart to take effect.** Run `hermes gateway restart` from a terminal OUTSIDE the gateway process (not from inside a Hermes session, which will get killed by SIGTERM). Use a separate terminal window or `launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway`.

The orchestrator profile needs `kanban` in its `platform_toolsets.cli` list to create tasks:

```bash
hermes config set platform_toolsets.cli '["browser","clarify","code_execution","computer_use","cronjob","delegation","file","image_gen","kanban","memory","messaging","session_search","skills","terminal","todo","tts","video","vision","web"]' --profile orchestrator
```

## Kanban 编排设置（Orchestration UI / config.yaml kanban 段）填写（2026-08-28 实测）

桌面端看板 → 编排设置页有 3 个下拉/开关 + 每个 profile 一行「说明」。**说明文字存储位置是 `profiles/<name>/profile.yaml`（default 是 `~/.hermes/profile.yaml`）的 `description` 字段——不是 config.yaml**。UI「保存」最终写入这里，因此**直接编辑 profile.yaml 的 description = 等效点 UI 保存**（renderer 从后端读）。

### 三个编排项语义（源码核实）

| 项 | 语义 | 建议 |
|---|---|---|
| `orchestrator_profile` | **仅**决定 auto-decompose fan-out 后根任务归属（`kanban_decompose.py::_resolve_orchestrator_profile`），**不**把该 profile 的 SOUL/skills 加载进分解调用 | 有 orchestrator 则保持 `orchestrator`；空=回退 default |
| `default_assignee` | 空 = 自动回退 default profile（兜底归主会话）；填 worker 会让它承接不属于自己的兜底职责 | **保持空（默认）**——主会话 description 即"兜底接盘"，语义一致；手动派卡流程此兜底几乎不触发 |
| `auto_decompose` | 仅 triage 列任务触发；手动 `kanban create` 指定 assignee 的卡不经过 triage | 手动派卡模式可保持 true（无害）或 false（省辅助 token） |

**真正的分解质量旋钮是 `auxiliary.kanban_decomposer`（provider/model）**——默认 `provider: auto, model: ''` 解析不稳定，建议显式指定（如 `deepseek` + `deepseek-v4-flash`）。`failure_limit` 建议 `3`（kimi 常超时/沙箱失败，2 偏紧）。

### description 填写规则（用户偏好，2026-08-28 确认）

1. **用中文**（任务描述是中文 → 路由语义对齐；5 个 worker 全是中文原生强模型，英文无优势）
2. **不要称呼前缀**——不写"工匠（GLM-5.1）："、"卷王（Kimi K2.6）："这类角色名+模型名，**只写能力动词描述**（用户明确："没有这个必要"）
3. 格式统一：`能力1、能力2、能力3；约束/特有能力`，全部 ≤70 字
4. 手写后 `description_auto: false` 是受保护文本

### ⚠ UI「自动」按钮陷阱（2026-08-28 实测 P1）

每行右侧「自动」按钮 = 调 `auxiliary.profile_describer` 用 **LLM 生成英文泛化描述**（如 "Specializes in A-share quantitative research..."），会**覆盖手写中文内容**并置 `description_auto: true`。用户误点一次即覆盖 worker-xiaomi。**手写方案填完后不要再点「自动」**；被覆盖则重写 profile.yaml 并置 `description_auto: false`。

本会话最终 7 个 profile 的中文能力描述见 `references/kanban-orchestration-settings.md`。

## Common Commands

```bash
hermes profile list                      # See all profiles and their models
hermes kanban list                       # View task board
hermes kanban tail <task_id>             # Watch task progress
hermes kanban archive <task_id>          # Clean up completed tasks
hermes gateway status                    # Check dispatcher health
grep kanban ~/.hermes/logs/gateway.log   # Dispatcher activity log
```

## Skill Sync Across Profiles（2026-08 实测）

**背景**：worker profile 的 skills 目录是**物理独立的**（`~/.hermes/profiles/<worker>/skills/`），default profile 新建/修改的 skill **不会自动同步**到 worker。2026-08 检查发现 worker-glm/kimi/orchestrator 缺 51 个量化类 skill（56 个量化里只有 5 个），导致 4Agent 评审量化系统时"盲评"——不知道三层架构、数据表结构、评审规范。

**检查缺口**（对比 default 与各 worker 的 SKILL.md 清单）：
```bash
cd ~/.hermes && python3 -c "
import os, glob
def get_skills(base):
    s = set()
    for sk in glob.glob(os.path.join(base, '**', 'SKILL.md'), recursive=True):
        s.add(os.path.relpath(os.path.dirname(sk), base))
    return s
default = get_skills('skills')
for name in ['worker-glm','worker-kimi','worker-xiaomi','orchestrator']:
    p = get_skills('profiles/'+name+'/skills')
    miss = sorted(default - p)
    print(name, 'total:', len(p), '| missing:', len(miss), '|', ', '.join(miss[:6]))
"
```

**同步方案**（按需精准复制，不搞全量膨胀）：
- **关键缺口 = 量化类（56）+ 评审规范（code-review-checklist / review-process-enhancement）**，worker 评审量化系统必须有
- worker-xiaomi 一般已齐全（只需补评审规范 + hermes 配置类）
- 复用脚本：`scripts/sync_worker_skills.py`（参数化复制缺失 skill 目录，含 references/scripts 附属文件）
- 备份：同步前 `find <profile>/skills -name "SKILL.md" | sort > backups/<name>_before.txt`，同步后再存 after 对照

**验证**：同步后重新对比，确认量化类 56/56、评审规范 2/2、仍缺 = 0。

**注意**：以后 default 新增/修改 skill 仍不会自动传播——需要时重跑同步脚本（或考虑 cron 定期同步）。

**⚠ 同步脚本只复制缺失目录、不更新已存在文件（2026-08-27 实测）**：如果修改的是 worker 已拥有的 skill（如本次把 kanban-parallel-review 里 Qwen3.8-Max 改成 Qwen3.7-Plus），重跑 sync 不会覆盖 worker 副本——必须对 worker 副本做**强制文本替换**：
```bash
cd ~/.hermes && python3 - <<'EOF'
import os
for profile in ['worker-glm','worker-kimi','worker-minimax','worker-xiaomi','worker-qwen','orchestrator']:
    base = f'profiles/{profile}/skills'
    if not os.path.isdir(base): continue
    for root, dirs, files in os.walk(base):
        for f in files:
            if f.endswith('.bak'): continue
            p = os.path.join(root, f)
            try:
                c = open(p, encoding='utf-8').read()
                if '旧字符串' in c:
                    open(p, 'w', encoding='utf-8').write(c.replace('旧字符串', '新字符串'))
            except Exception: pass
EOF
```
批量替换 profile 名/模型名后，用 `grep -r "旧名" ~/.hermes/profiles/*/skills/ | grep -v .bak` 终扫确认零残留。

## References

- `references/kanban-orchestration-settings.md` — 编排设置最终方案：7 个 profile 中文能力描述、三项编排值、profile.yaml 写入脚本与陷阱
- `references/kimi-cn-xiaomi-provider-quirks.md` — Kimi-CN endpoint model list, Xiaomi MiMo status-check blind spots, and setup quirks
- `references/worker-souls.md` — SOUL.md templates for each worker profile
- `references/dashscope-china-endpoint.md` — DashScope/alibaba China endpoint troubleshooting
