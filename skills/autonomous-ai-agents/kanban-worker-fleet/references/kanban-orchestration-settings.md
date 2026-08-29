# Kanban 编排设置 — 最终确认方案（2026-08-28）

用户确认的 kanban 编排设置（保留 orchestrator 方案）与 7 个 profile 的中文能力描述。
写作/更新 profile.yaml 时直接复用下方内容（已去掉称呼前缀，纯能力动词）。

## 存储位置

- 各 worker/orchestrator：`~/.hermes/profiles/<name>/profile.yaml` 的 `description` 字段
- default：`~/.hermes/profile.yaml`（主 home，不是 profiles/default/ 下！）
- 每次写入同时置 `description_auto: false`（受保护的手写文本，防「自动」按钮覆盖）
- 保留文件原有 `ui_meta` 等其他字段（yaml.safe_load → 改 description → safe_dump）

## 三个编排项最终值（config.yaml kanban: 段）

| 项 | 值 | 说明 |
|---|---|---|
| `orchestrator_profile` | `orchestrator` | 保留；仅控制 auto-decompose 根任务归属 |
| `default_assignee` | `''`（默认） | 空 = 回退 default 主会话兜底，语义与主会话 description 一致 |
| `auto_decompose` | `true`（保持） | 手动派卡不受影响 |
| `failure_limit` | `3`（建议） | kimi 常超时/沙箱失败，2 偏紧 |
| `auxiliary.kanban_decomposer` | `provider: deepseek, model: deepseek-v4-flash`（建议显式） | 真正的分解质量旋钮，默认 auto/'' 不稳定 |

## 7 个 profile 最终 description（中文、无称呼前缀、≤70 字）

| profile | description |
|---|---|
| default | 日常对话、数据查询、代码执行、MOA 多模型聚合；单步任务直接处理；无合适 worker 时兜底接盘；图/截图视觉任务归此 |
| orchestrator | 任务拆解与分发、汇总各 worker 评审结果（收集/去重/质检/出报告）、自动分解后根任务归属 |
| worker-glm | 代码实现与重构、架构评审、结构化输出（JSON/表格）；纯文本模型，不接收图片/截图 |
| worker-kimi | 逻辑审查（边界条件/推理链）、网络搜索与多源交叉验证、长文档分析 |
| worker-minimax | 深度审计、交叉验证、性能/安全/运维（SQL 性能/索引/内存/部署风险）；支持 1M 超长上下文+思考模式 |
| worker-qwen | 方案论证、综合分析、行业/策略研究；分析性整合（矛盾检测/共识提取/方案收敛） |
| worker-xiaomi | 运行验证（跑脚本/查库核对数值/可行性验证）、数据完整性、漏检/边界补充 |

## 写入脚本（幂等，保留 ui_meta）

```python
import yaml, os
DESC = { 'default': '...', 'orchestrator': '...', ... }  # 上表内容
for name, text in DESC.items():
    p = '/Users/yellow/.hermes/profile.yaml' if name == 'default' else f'/Users/yellow/.hermes/profiles/{name}/profile.yaml'
    d = {}
    if os.path.exists(p):
        with open(p) as f: d = yaml.safe_load(f) or {}
    d['description'] = text
    d['description_auto'] = False
    with open(p, 'w') as f: yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False)
```

## 陷阱

1. **「自动」按钮覆盖**：每行右侧「自动」= LLM 生成英文泛化描述（description_auto=true），会覆盖手写中文。误点后重写 profile.yaml 并置 false。
2. **default 位置**：default 的 profile.yaml 在 `~/.hermes/profile.yaml`（34KB，含大量配置），不在 `profiles/default/`——该目录不存在。
3. **UI 显示**：renderer 从后端读 profile.yaml，改文件后 UI 刷新/重开即可看到新内容，无需重启。
4. **中文 vs 英文**：用户确认中文更合适（任务描述是中文、模型全中文原生、信息密度高）。
