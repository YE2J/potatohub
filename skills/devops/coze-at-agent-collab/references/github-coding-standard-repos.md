# GitHub 代码/脚本规范项目核实清单（2026-08-26 实测）

> 用途：为「软件开发规范」类调研任务提供已验证的候选项目池。所有数据通过 GitHub REST API
> `https://api.github.com/repos/<owner>/<repo>` 实时查询 stars/pushed_at/archived 核实，
> 非搜索摘要。下次复用时重新拉 API 刷新数字，不要照抄本文的星数。

## 活跃度门槛

用户标准：最近一年内有更新（pushed_at 距今 <12 个月）。本次被剔除的例子：
- standard/standard（JS 规范+linter）：pushed 2025-07-11 → 剔除
- editorconfig/editorconfig（.editorconfig 主仓库）：pushed 2025-04-21 → 剔除
  （替代：editorconfig-checker/editorconfig-checker 活跃）

## 已核实的 15 个项目（按方向分组）

### 风格指南
| 项目 | Stars | pushed | 用途 |
|---|---|---|---|
| airbnb/javascript | 148,135 | 2026-04-16 | 最广采用的 JS 风格指南 |
| google/styleguide | 39,531 | 2026-06-03 | Google 多语言风格指南集 |

### Lint/格式化（按语言）
| 项目 | Stars | pushed | 用途 |
|---|---|---|---|
| eslint/eslint | 27,487 | 2026-08-25 | JS/TS 标准 linter |
| prettier/prettier | 52,217 | 2026-08-26 | 多语言格式化 |
| astral-sh/ruff | 49,326 | 2026-08-26 | Python 快速 linter+formatter（Rust） |
| psf/black | 41,814 | 2026-08-20 | Python 格式化 |
| koalaman/shellcheck | 39,930 | 2026-08-04 | Shell 静态分析 |
| mvdan/sh (shfmt) | 9,008 | 2026-08-23 | Shell 格式化 |
| golangci/golangci-lint | 19,318 | 2026-08-25 | Go 聚合 linter |

### 提交与版本规范
| 项目 | Stars | pushed | 用途 |
|---|---|---|---|
| conventional-changelog/commitlint | 18,701 | 2026-08-24 | 提交信息校验 |
| conventional-commits/conventionalcommits.org | 9,184 | 2026-03-11 | Conventional Commits 官方文档仓库 |
| semantic-release/semantic-release | 24,005 | 2026-08-22 | 自动版本发布 |

### 编辑器一致性与提交工作流
| 项目 | Stars | pushed | 用途 |
|---|---|---|---|
| editorconfig-checker/editorconfig-checker | 634 | 2026-08-26 | CI 校验 .editorconfig 合规 |
| pre-commit/pre-commit | 15,537 | 2026-08-17 | 多语言 pre-commit hook 框架 |
| typicode/husky | 35,286 | 2026-03-19 | Git hooks 工具（JS 生态） |

## 推荐落地链路

.editorconfig → ESLint / Ruff / ShellCheck / golangci-lint（静态检查）
→ Prettier / Black / shfmt（自动格式化）
→ commitlint + husky 或 pre-commit（提交强制执行）
→ semantic-release（自动化版本发布）

## 本地 Hermes 环境适配结论（Py3.9/M4 16GB）

首选组合：Ruff（兼容 Py3.9 且极快、一顶多）+ Black + ShellCheck（大量 bash cron 脚本）
+ pre-commit（挂成提交门禁）+ commitlint/husky（规范提交史）。
