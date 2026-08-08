# PotatoHub: Skills 自动备份到 GitHub

## 架构（2026-08 恢复后的现状）

| 组件 | 位置 |
|------|------|
| git 仓库 | `~/.hermes/potatohub`（remote origin → `https://github.com/YE2J/potatohub.git`，分支 main） |
| 脚本 | `~/.hermes/scripts/potatohub_backup.sh`（no_agent watchdog 模式） |
| cron | 每周日 00:00（`0 0 * * 0`），job 名 "PotatoHub-Skills备份到GitHub"，no_agent=true，script=potatohub_backup.sh，deliver=origin |
| 凭据 | `~/.git-credentials`（格式 `https://USER:ghp_TOKEN@github.com`，权限 600） |
| 日志 | `~/.hermes/potatohub/backup.log` |

## 脚本行为（potatohub_backup.sh）

1. `set -e`，cd 到 backup dir
2. `rm -rf skills && cp -R -L ~/.hermes/skills → backup/skills`（`-L` 解析 symlink，损坏链接 2>/dev/null 忽略）
3. `git add -A`；若 `git diff --cached --quiet` → 无变化：写日志、**stdout 静默**（watchdog：不打扰用户）
4. 有变化 → commit `📦 Skills 自动备份 YYYY-MM-DD HH:MM`
5. 推送：从 `~/.git-credentials` grep 出 `ghp_` token，`git -c http.proxy= -c https.proxy= push https://YE2J:TOKEN@github.com/YE2J/potatohub.git main`（显式去代理，绕过代理依赖）
6. stdout 输出「备份完成 + 仓库链接」→ cron 递送到微信
7. 日志追加到 `backup.log`

## 关键坑：jobs.json 重建会静默丢任务

- **2026-07-03 前后 jobs.json 被重建**（`~/.hermes/cron/` 留有 `jobs.json.bak.20260703` 等备份），PotatoHub cron 丢失且**无任何报错**——脚本和 git 仓库都还在，只是没人调度了。6 周无备份（仓库最后提交停在 2026-06-21）。
- **丢失检测信号**：
  - `cronjob list` 里找不到该任务，且 `grep -rl "potatohub" ~/.hermes/cron/` 无结果
  - 但 `~/.hermes/scripts/potatohub_backup.sh` 和 `~/.hermes/potatohub/.git` 仍然存在
  - 工作区有积压：`cd ~/.hermes/potatohub && git status -s` 显示未提交变更
- **恢复顺序**：
  1. **手动跑一次脚本**（`bash ~/.hermes/scripts/potatohub_backup.sh`）—— 一次 flush 积压 + 验证 token/推送/递送端到端链路
  2. 验证远程同步：`git ls-remote origin main` 与本地 HEAD 一致 + `git fetch origin main && git status -sb`
  3. 重新注册 cron（见下）
- **手动跑一次即验证全部**，比只看配置更可靠（token 可能失效、仓库可能改名、网络代理可能变化）。

## 重新注册 cron 模板

```
cronjob create:
  schedule: "0 0 * * 0"
  no_agent: true
  script: potatohub_backup.sh     # 相对路径默认解析到 ~/.hermes/scripts/
  deliver: origin                 # 有变更时微信通知；无变更 watchdog 静默
  name: "PotatoHub-Skills备份到GitHub"
```

## 备注

- 同类「配置/技能定时备份到 GitHub」的仓库都该注册为 **watchdog no_agent** 模式：stdout 空 = 静默，非零退出 = 错误告警。
- 曾因 jobs.json 重建丢任务 → 把任务 ID 和恢复要点写进 memory，方便下次直接恢复。
