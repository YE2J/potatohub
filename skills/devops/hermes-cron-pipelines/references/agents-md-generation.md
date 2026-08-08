# 生成/更新项目 AGENTS.md（/init 的等价实现）

`/init` 是 CLI 斜杠命令，但**不是魔法**——它只是构造一段提示词注入给 agent，让 agent 用只读工具扫描项目后 `write_file` 写出 AGENTS.md。在桌面会话 / gateway / 任何非 CLI 会话里，直接用工具做等价操作即可（源码：hermes_cli/init_command.py）。

## 标准流程（等价于 /init）

1. 扫描项目：先从 manifests 和工具链文件开始（requirements.txt / pyproject.toml / Makefile / CI 配置），再目录结构、README/docs、测试配置。
2. 验证命令真实性：命令必须是你从文件里看到的**精确调用**（如 `python engines/market_temperature.py --date 2026-07-09`），禁止编造。可实际跑一次 `python3 -c "sqlite..."` 之类验证。
3. 写入 `<project>/AGENTS.md`（用 write_file）。
4. 确认路径 + 一两行摘要。

## 质量标准（/init 官方 quality bar，实测有用）

- **简洁**：目标 <100 行。每个 agent 会话都会加载这个文件，每行都是 context 成本。
- **命令精确**：写 `python engines/x.py --date YYYY-MM-DD`，不写"跑引擎"。没在仓库里看到的命令一律不写。
- **无泛泛建议**：删掉任何"对任何仓库都成立"的话（如"写测试""遵循最佳实践"）。
- **约定必须观察到**：命名模式、模块布局、错误处理风格——只写代码里真实存在的。
- **含真实坑点**：必需 env vars、易混日期格式、单位换算、API 限频、慢测试等（找不到就跳过该节）。
- **结构**：标题 + 一段概述，然后分节（Dev environment / Build & test / Conventions / Pitfalls），平铺可扫读，不深嵌套。

## 对用户量化项目的实测模板（2026-08-05 生成 58 行）

实际生成 `~/my_quant_system/AGENTS.md` 的章节骨架（可直接套用同类项目）：

```
# <项目名> — 一句话定位（含运行环境：macOS/Python 版本/是否 git 仓库）

## 核心架构（表格：层|引擎|输入|输出表）    ← 对量化系统：L1温度/L2板块/L3融合
## 运行命令（代码块，从项目根）            ← 每个引擎的 --date/--backfill 用法原文摘录
## 数据源与存储                            ← 主源/辅源、DB 路径、关键表名（实查 sqlite_master 验证）
## 公共模块                                ← config.py、db_utils.py 等（文件存在性验证）
## 数据约定（易踩坑）                      ← 日期格式双轨、单位换算、API 限频 —— 最高价值节
## 其他目录                                ← 一次性的 backtest_*.py / screen_*.py 标注"一次性"
```

## 何时更新

架构变了（新增层级、换数据源、加引擎）就主动提出更新。**过时的 AGENTS.md 比没有更糟**——它会误导 agent。用户偏好：生成后先展示再让用户确认保留。

## 验证方式

- `wc -l` 确认 <100 行
- 对 agent 模式 cron 任务配 `workdir` 后手动触发，看 `~/.hermes/cron/output/<job_id>/` 输出确认上下文注入生效（见 cron-workdir-agents-md.md）
