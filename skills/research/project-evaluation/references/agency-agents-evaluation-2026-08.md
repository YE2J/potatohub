# agency-agents 评估结论 (2026-08)

## 项目身份
- msitarzewski/agency-agents — 智能体角色库（persona 合集），147K★，MIT，2025-10 创建，活跃维护
- 14 事业部 300+ 角色卡（.md 格式：name/description/color/emoji/vibe/身份记忆/核心使命/关键规则/交付物）
- 安装目标：Claude Code / Cursor / Codex / Gemini / OpenCode 等编码工具；有桌面 App（brew cask）
- Finance Division 仅 5 个角色：Bookkeeper/Financial Analyst/FP&A/Investment Researcher/Tax Strategist
- Investment Researcher 角色：14年买方研究员 persona，DCF/comps/SOTP、多因子筛选、Beta/VaR/Sharpe、SEC filings 引用 —— 美股/企业投研导向，非 A股量化

## 评估结论：不装，只借鉴
| 维度 | 结论 |
|---|---|
| 定位错位 | 通用编码/业务角色库，A股量化垂直场景零覆盖（无 T+1/涨跌停/北向/板块轮动/龙虎榜/两融） |
| 格式兼容 | .claude/agents/*.md 角色卡，Hermes SKILL.md 不通用 |
| 重复度 | 用户已有真多模型团队（4Agent+MOA+Kanban），角色库=单模型多 persona，踩"禁止模拟多角色"红线 |
| 借鉴价值 | ⭐ thesis breakers / bull-bear 双面对照 / 置信度披露 → 落地 L3 |

## 已落地：L3 decision_fusion.py v1.3
- decision_log 新增列：thesis_breakers TEXT, bear_case TEXT（migrations/006 + scripts/migrate_006_thesis_breakers.py 幂等加列：PRAGMA 检查 + ALTER ADD COLUMN）
- check_valuation 返回 thesis_breakers（3条：pos≥50 脱离低估区 / margin<-30% / 板块热度连续2日下降）+ bear_case（深度低估/低估边缘 + 价值陷阱风险提示）
- sell 信号带撤销条件（bull_case）：pos 回落 <68 且 margin 转正则撤销
- confidence 动态分档：buy 强 85(margin≥0)/70、buy 弱 55、sell 强 85(pos≥90|margin<-60)/70、sell 弱 55、hold 50；共振修正 L1温度≥70 或 leader_score≥60 → buy +5（上限95）
- 冒烟测试 5 例验证通过；migration 幂等验证（跑两次安全）
