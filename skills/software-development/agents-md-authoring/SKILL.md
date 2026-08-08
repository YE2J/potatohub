---
name: agents-md-authoring
description: "生成/更新项目 AGENTS.md（等价 /init 流程）。用户要求 /init 或生成项目上下文文件时使用。"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [agents-md, project-context, init, onboarding]
    related_skills: [hermes-agent-skill-authoring, three-layer-quant-architecture]
---

# AGENTS.md Authoring（等价 /init）

生成/更新项目的 `AGENTS.md` 项目指令文件。AGENTS.md 是编码 agent（含 Hermes 自己）每次会话自动加载的项目上下文：这个项目是什么、怎么搭、**精确**的构建/测试/运行命令、代码实际遵循的约定、浪费时间点。

## 为什么需要这个 skill

`/init` 是 **CLI 专属**斜杠命令——它的机制是把一个提示词注入 agent 输入队列，agent 用只读工具扫描项目后 `write_file` 写 AGENTS.md。**桌面 app / 网关会话无法直接执行斜杠命令**，但机制完全等价：自己用只读工具扫描 → `write_file` 写文件。

源码参考：`hermes_cli/init_command.py`（`build_init_prompt_for_cwd` / `_QUALITY_BAR`），升级后可复查质量标准的权威定义。

## 执行步骤

1. **扫描项目**（只读工具，先 manifests 后布局）：
   - 根目录完整清单 `ls -1`
   - manifests/toolchain：requirements.txt / pyproject.toml / Makefile / package.json
   - README、docs/ 设计文档、`.git` 是否存在
   - 关键入口文件头部（docstring 里的用法、argparse 定义）→ **这是命令的唯一真实来源**
   - 数据/存储层：`sqlite_master` 查真实表名、config 常量、公共模块
2. **提炼真实约定**：目录职责、公共模块、配置常量、运行命令（从源码验证，绝不猜）
3. **按质量标准写**（见下），写入 `<项目根>/AGENTS.md`
4. **验证**：`wc -l` 确认 <100 行；向用户报告精确路径 + 1-2 行覆盖内容摘要
5. **已有 AGENTS.md 时走合并纪律**：保留用户原内容/措辞/章节，只合并缺失或可验证过时的部分，最小外科手术式编辑，不整体重写

## 质量标准（官方 _QUALITY_BAR 要点）

- **简洁**：目标 <100 行。agent 每会话都加载，每行都耗 context。无散文、无营销腔、无填充
- **命令精确**：必须是从仓库验证过的精确调用（docstring/argparse/Makefile/CI），写 `python engines/market_temperature.py --date 2026-07-09`，绝不写"运行测试"。**没见过的命令绝不编**
- **无泛泛建议**："为新代码写测试""遵循最佳实践"这类对任何仓库都成立的话禁止
- **约定必须观察**：命名模式、模块布局、错误处理风格——只写代码实际展示的
- **真实坑点节**：能绊倒新人/agent 的（必需 env、勿手改生成文件、慢测试、端口占用、跨表格式不一致）；没发现就跳过该节
- **结构**：短标题 + 一段概述，然后聚焦小节（如"运行命令""数据约定""易踩坑"）。平铺可扫读，不深嵌套

## Pitfalls

- 命令必须从源码/docstring 验证——引用 `--date YYYY-MM-DD` 这类 CLI 参数前先看 argparse 定义，照抄 docstring 用法
- 数据约定不一致（日期格式双轨、单位换算、API 限频）正是 AGENTS.md 最该写进"易踩坑"的素材——从历史教训+观察提炼，不要只写目录结构
- 非 git 仓库也能写 AGENTS.md（它对 agent 有效，与 git 无关），照写并在概述注明
- 架构/数据源变更后要主动提出更新 AGENTS.md——过时的文件比没有更误导

## 参考

- `references/my-quant-system-agents-md.md` — 实测样例：A股三层决策量化系统 AGENTS.md 的生成过程（扫描项 / 提炼约定 / 坑点节素材）
