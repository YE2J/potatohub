# 记忆预算压缩实战记录（2026-08-23）

首次完整压缩执行的全记录，作为后续压缩的模板参照。

## 背景

- MEMORY 3,885/4,500（86%），USER PROFILE 2,033/3,000（67%）→ 用户："记忆预算很快就满了"
- 用户立铁律：压缩前必须先完整备份（本会话新增为 USER 条目）
- 用户要求：分析内容 → 备份 → 修改方案过目 → 确认后执行

## 分层方案模板

| 档位 | 适用 | 示例 |
|------|------|------|
| 保护清单（不动） | 行为红线/cron ID/踩坑/身份偏好/活跃状态 | MOA约束、备份铁律、cron核心时间表、L2b待拍板A/B/C |
| 压缩为指针 | 细节已落盘（报告/skill），留结论+红线+指针 | P2终局→docs/P2_E_attribution_report.md；L2b→docs/L2b_P2_layer_diagnosis.md；文档分析→skill office-to-markdown v2.5.1 |
| 删除 | 与另一处重复、信息已并入 | USER"代码审查5维"（与MEMORY重复）、faster-whisper（并入MEMORY HF下载） |

## 执行顺序（验证有效）

1. 备份：`~/.hermes/backups/memory/memory_20260823_011311.md`（基线）→ `memory_20260823_012137.md`（含铁律条目后刷新）→ `memory_20260823_post_compression.md`（压缩后）
2. 验证退路：4 份报告文件 `ls` 确认存在；6 个 skill `find` 确认；office-to-markdown SKILL.md `grep` 12 个关键规则词全部覆盖
3. hindsight_retain ×3：项目决策上下文(P2+L2b) / 用户文档处理约定 / 量化系统运维配置（第3条曾 daemon 失败，重试成功）
4. 批量 memory 操作：MEMORY 10 条 + USER 4 条，分两次调用（各带 target）
5. 结果核对：MEMORY 3,885→3,181（70%），USER 2,033→1,164（38%），合计省 1,573 字符

## 回滚案例（关键 Pitfall 实证）

MEMORY 批次首次提交：operations 第 6 项 old_text 用"评估第三方工具: 查重→重复不装"，
实际条目是"查重复→重复不装"（多一个"复"字）→ **整批回滚、无部分应用**。
修正 old_text 后重发成功。教训：提交前逐字核对；失败先读回 `current_entries`。

## 用户流程偏好确认

- 方案必须过目（"将修改方案给我过目"），未确认不执行
- 多方案并行（A中档/B激进），可合并执行（"方案a和方案b可以一起做吗"→是）
- 每项变更要标"省字符 + 退路"，保护清单与风险缓解同步列出

## 保护清单示例（本会话实际保留项）

USER：压缩铁律、MOA约束、身份/偏好/token意识；MEMORY：cron核心时间表、视觉配置（max_tokens坑）、晨报v8、Hindsight配置
