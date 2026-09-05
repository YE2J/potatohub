---
name: moa-multi-model-review
title: "MOA 多模型协作评审"
description: "使用 Hermes 原生 MOA（Mixture of Agents）进行多模型交叉验证、代码评审、方案讨论。5个参考模型并行输出，聚合模型仲裁矛盾。含 MOA 故障诊断与调试指南。"
tags: [moa, multi-model, review, cross-validation, troubleshooting]
---

# MOA 多模型协作评审

## 什么时候用 MOA

| 场景 | 用 Kanban | 用 MOA |
|:-----|:---------:|:------:|
| 4 个独立维度分别审查 | ✅ | — |
| 需要交叉验证和矛盾仲裁 | — | ✅ |
| 不同模型共同讨论一个主题 | — | ✅ |
| 每个模型要执行不同的操作（查库/改文件） | ✅ | — |
| 需要多轮辩论（先发言→回应→反驳） | ⚠️ 需手动编排 | — |
| 一轮出结论，各模型各自输出+聚合仲裁 | — | ✅ |

**核心区别**：MOA 的 5 个参考模型回答同一问题，聚合模型读全部后做交叉验证。Kanban 每个 worker 独立。**MOA 解决了"4 份报告无人仲裁"的问题。**

## 当前配置

```
hermes moa list

Reference models:
  1. deepseek:deepseek-v4-flash
  2. zai:glm-5.1
  3. kimi-coding-cn:kimi-k2.6
  4. minimax:minimax-m2.7
  5. xiaomi:mimo-v2.5
Aggregator: deepseek:deepseek-v4-flash
Active in config: default
```

> ⚠️ Provider 名称必须与 Hermes 注册名完全一致。常见错误映射：`z.ai`(✗)→`zai`(✓), `moonshot`(✗)→`kimi-coding-cn`(✓)。完整映射表见 `references/provider-naming.md`。

## 如何使用

### 触发 MOA

在对话中直接输入：

```
/moa <问题>
```

Hermes 会自动派发 5 个参考模型并行输出，然后聚合模型综合仲裁。

### 配置 MOA

```bash
# 查看当前配置
hermes moa list

# 交互式配置（输入 provider:model 格式，选 Done 结束）
hermes moa configure
```

**注意**：`hermes moa configure` 不接受 piped 输入。`printf '...' | hermes moa configure` 不生效。

如需非交互式配置，用 Python regex 直接替换 config.yaml 的 moa 段。

### 如何调优

```yaml
reference_temperature: 0.6    # 参考模型：稍高温度保证多样性
aggregator_temperature: 0.4    # 聚合模型：较低温度保证一致性
max_tokens: 4096               # 每模型最大输出
fanout: per_iteration          # 派发模式
```

## 配置陷阱（重要）

| 陷阱 | 现象 | 解决方法 |
|:-----|:-----|:---------|
| `yaml.dump()` 会**破坏 config.yaml** | 用 Python yaml.dump 回写后 `hermes moa list` 报 YAML 解析错误 | 用纯文本 `sed` 或 Python regex 只替换 moa 段，不要用 `yaml.dump` 回写整个文件 |
| **API Key 不在全局 .env** | Kanban 正常但 MOA 报错 `Provider API key not found` | MOA 读全局认证池，worker profile 的 `.env` 不被 MOA 识别。需把 key 映射到全局 |
| **变量名不匹配** | 配 `moonshot:kimi-k2.6` 但系统找不到 `MOONSHOT_API_KEY` | 查 `worker-kimi/.env` 实际变量名（如 `KIMI_CN_API_KEY`），映射到 MOA 期望的变量名 |
| **config.yaml 边界错位** | moa 段后缺换行导致 `fanout: per_iterationskills:` 拼在一起 | 用 `sed -i ''` 修复断行 |
| **sed 按模型名插入误伤** | 模型名在配置其他段重复出现（如 `mimo-v2.5` 同时是 `auxiliary.vision.model` 和 moa 参考模型），`sed -i '' '/model: mimo-v2.5/a\...'` 会插入 2 处，破坏 YAML（报 `mapping values are not allowed in this context`） | 插入前 `grep -c <模型名> config.yaml` 确认唯一；不唯一时用 `sed -n '170,190p'` 查看行号后按行号定位（`sed -i '' 'N,Md'` 删除误插行）。Hermes 解析失败会自动存 `config.yaml.corrupt.<时间戳>.bak` 副本 |
| **provider 名称写错（最常见）** | `hermes moa list` 显示正确，但实际调用时 provider 报错 | 用 `hermes doctor` 或查 `auth.json` 确认真实 provider 名，逐项比对 |

## MOA 故障诊断（当参考模型不工作时）

如果 `/moa` 调用后部分模型不工作（如仅 DeepSeek 正常，其他 4 个失败），按以下步骤排查：

### 步骤 1：查认证池确认真实 provider 名

```bash
cat ~/.hermes/state-snapshots/latest/auth.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
pool = d.get('credential_pool', {})
for p, creds in sorted(pool.items()):
    labels = [c.get('label','?') for c in creds]
    print(f'{p}: {labels}')
"
```

输出示例：
```
deepseek: ['DEEPSEEK_API_KEY']
kimi-coding-cn: ['KIMI_CN_API_KEY']
minimax: ['MINIMAX_API_KEY']
xiaomi: ['XIAOMI_API_KEY']
zai: ['GLM_API_KEY', 'ZAI_API_KEY']
```

左侧就是 Hermes 真实接受的 provider 名称。MOA 配置中的 `provider:` 必须 **完全一致**。

### 步骤 2：查提供商可用模型

```bash
python3 -c "
import json
with open('/Users/yellow/.hermes/provider_models_cache.json') as f:
    d = json.load(f)
for p in ['zai','kimi-coding-cn','minimax','xiaomi']:
    models = d.get(p,{}).get('models',[])
    print(f'{p}: {models}')
"
```

确认 MOA 配置的 `model:` 名称也在列表中。

### 步骤 2a：缓存可能不完整——直接查 API

如果 `provider_models_cache.json` 中没有你要的模型，不要直接断定它不存在。缓存可能漏了。用 API 直查：

```bash
# 从 .env 读取对应 API key
ZAI_KEY=$(grep '^ZAI_API_KEY=' ~/.hermes/.env | head -1 | cut -d= -f2- | tr -d "'")
curl -s "https://api.z.ai/api/paas/v4/models" \
  -H "Authorization: Bearer $ZAI_KEY"
```

如果 API 返回了你想用的模型，更新缓存即可：

```bash
python3 -c "
import json
with open('/Users/yellow/.hermes/provider_models_cache.json') as f:
    d = json.load(f)
# 示例：补全 zai 的模型列表
d['zai']['models'] = ['glm-5.2','glm-5.1','glm-5-turbo','glm-5','glm-4.7','glm-4.6','glm-4.5-air','glm-4.5']
with open('/Users/yellow/.hermes/provider_models_cache.json','w') as f:
    json.dump(d, f, indent=2)
"
```

不同提供商的模型查询 endpoint 不同：
| Provider | 查询 URL |
|:---------|:---------|
| zai | `https://api.z.ai/api/paas/v4/models` |
| deepseek | `https://api.deepseek.com/v1/models` |
| kimi-coding-cn | `https://api.moonshot.cn/v1/models` |

### 步骤 3：比对两表

将 `hermes moa list` 输出的每行 `provider:model` 与步骤 1 的 provider 列表、步骤 2 的 model 列表逐项比对。

### 常见错误映射

| 错误名称（MOA 配置中） | 正确名称（认证池中） | 说明 |
|:-----------------------|:--------------------|:-----|
| `z.ai` | `zai` | 点号 vs 纯字母 |
| `moonshot` | `kimi-coding-cn` | 模型商名 vs Hermes 注册名 |
| `glm-5.1`（缓存中缺失） | `glm-5.1`（API 实际存在） | 缓存可能不完整，见下文「步骤 2a」直接查询 API |

### 修复方法

```bash
cd ~/.hermes
sed -i '' 's/provider: z\.ai/provider: zai/' config.yaml
sed -i '' 's/provider: moonshot/provider: kimi-coding-cn/' config.yaml
# 当前标准为 glm-5.1；若需从旧版本回退：
sed -i '' 's/model: glm-5.2/model: glm-5.1/' config.yaml
```

修复后验证：
```bash
hermes moa list     # 确认显示正确
```

### 步骤 4：更新 key 后刷新凭证池

如果只更新了 `.env` 中的 API key，MOA 可能仍使用旧凭证。重启 Hermes 或执行：

```bash
# 方式一：重启 Hermes Desktop（缓存刷新）
# 方式二：删除凭证池缓存让系统重建
rm ~/.hermes/state-snapshots/latest/auth.json
# 下次 MOA 调用时会自动重建凭证池
```

然后对话中 `/moa <测试问题>` 验证。如果仍有模型不响应，重复步骤 1~3 逐项排除。

## 适用场景

1. **代码评审** — 5 个模型各找出不同维度的问题，聚合模型汇总矛盾点
   - 代码审查 prompt 模板见 `references/code-review-prompt-template.md`
   - 按 P0/P1/P2 三级分类输出，聚合模型自然收敛矛盾点
   - 常见 P0 陷阱：变量作用域逃逸、日期格式不兼容、定义未调用
2. **方案讨论** — 对同一个问题产出多方观点，聚合模型给出综合建议
3. **Bug 排查** — 各模型独立分析堆栈/日志，聚合模型判定根因
4. **数据验证** — 各模型检查不同表的完整性问题，聚合模型输出交叉验证报告

## 与 Kanban 的协同

```
第一轮（MOA一轮制）：5个模型各自输出 → 聚合仲裁 → 输出疑点清单
第二轮（Kanban执行修复）：用 delegate_task 修 P0
第三轮（Kanban验证）：派 2 个 worker 验证修复质量
```

### Workflow: Draft → MOA Review → Batch Fix → Deploy

Session-proven workflow for code changes that need pre-implementation review:

```
Phase 1: Draft
  → Write the code/script (first cut)
  → May need DB schema checks, existing code audits

Phase 2: MOA Review (this skill)
  → /moa 请评审以下文件，从四个维度交叉验证...
  → Provide draft code + 10-point checklist
  → Each model outputs P0/P1/P2 findings
  → Aggregator produces consolidated list

Phase 3: Batch Fix (by primary agent)
  → Fix all P0 items first (critical bugs)
  → Fix all P1 items (edge cases)
  → Fix P2 items (style, guardrails)
  → Use patch(), verify with grep/search_files

Phase 4: Verify
  → Re-run or single-agent check of fixed lines
  → Update cron/scripts to point to new version
```

Key lesson: Do NOT fix in random order. A P0 fix may touch the same lines as a P2 fix, creating issues. Batch by severity: P0 → P1 → P2.

10-point review checklist that fits in a /moa prompt:

1. 关键模块中累计/聚合计算的边界条件
2. 不同模块间的日期格式兼容性（YYYYMMDD vs YYYY-MM-DD）
3. 各分支路径的参数传递是否正确
4. 正则/字符串匹配的可靠性（特殊字符、空格、表头行干扰）
5. 截断/优先级设置是否合理
6. [SILENT]/错误处理机制是否完善
7. SQL注入风险（f-string拼接表名列名）
8. 降级/异常路径是否合理
9. 字数/资源限制下是否可能溢出
10. None/NULL 值传入时的降级行为

## ⚠️ MOA 输出判别器（2026-09-01 实测教训，防存档伪造）

用户执行 `/moa` 后，**用户消息里出现的提示词回显 ≠ MOA 结果**。真实结果以系统注入的 `[Mixture of Agents reference context]` 块到达（含 Reference 1..N 编号的模型输出 + aggregator 指令），且出现在提示词之后**独立的轮次**，不会与提示词同轮出现。

**铁律：未看到该注入块之前，禁止写任何 moa_raw/aggregated 存档**。存档内容必须能在注入原文中逐条溯源；把聚合器工作（评分/仲裁/A-F 综合）安到参考模型头上 = 伪造；虚构参考模型身份（对照 `hermes moa list` 实测即识破） = 伪造。参考模型无工具权限，其"已写盘/已实测"声明一律为幻觉。
**等待期硬约束（Case #5，2026-09-05）：未看到 `[Mixture of Agents reference context]` 注入块前，禁止输出任何含参考模型归属/编号（"6家一致""Reference N 建议"等）的聚合内容；等待期间回复仅限「MOA 已触发，等待参考块到达」。声称参考块已到达而上下文无注入块 = 虚构，即使随后自我更正仍属违规。**

## ⚠️ 重要约束

- **参考模型之间互相不可见**（与多轮辩论不同），只有聚合模型看到全部
- **参考模型可能编造"实查结果"（2026-08-25 实测）**：参考模型声称的文件/数据事实（如"某文件含 30+ git 冲突标记""某目录有碎片"）可能是幻觉，**必须由执行代理亲自验证**（grep/read_file/数据库查询）后才可采信或转述。本次 MOA 评审中 Minimax 声称 wiki 文件损坏，实查为 0 处冲突标记、文件干净。发现虚构 → 在汇总中明确标注不实，并在 `运维避坑` 记录，后续降级该模型的事实类发言权重。聚合器的核心职责不是"综合"，是**验证后综合**。
- **全票共识 ≠ 前提正确（2026-09-02 实测；比个别幻觉更危险）**：审计中 6/6 参考模型把 `moneyflow_tushare_main_daily`（实测自选股表，每日 2~4 行）当"全市场表（数千行/日）"，一致把"整日 DELETE"定级 P0 数据灾难；聚合器 `SELECT trade_date, COUNT(*), COUNT(DISTINCT ts_code) ... GROUP BY trade_date` 实测后降级 P1（实际数据损失 = 0）。**影响定级的前提事实（表规模、cron 实际调用文件、受影响行数）必须由聚合器独立实测，不得因"6/6 都这么说"采信——投票一致 ≠ 事实正确。** 详见 `references/aggregator-premise-verification.md`。
- 如果需要多轮辩论（A反驳B），需要手动编排多轮 MOA 或改 Kanban parents
- **Token 消耗**：5 次参考模型调用 + 1 次聚合 = 约 17,000~22,000 tokens
- MOA 的参考模型 `provider:model` 必须已在 config 中配置了 API key
- 判别器细节（含同花顺 GB18030 文件编码坑）见 `references/moa-output-discriminator-20260901.md`
