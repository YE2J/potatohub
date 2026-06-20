# 部署与运维要点

## Cron 脚本 Python 环境陷阱

**问题**：Hermes cron job 的 `script` 模式运行 `.py` 文件时，使用系统 Python（Hermes 内置 venv 的 Python 3.11），**不是项目 venv**。系统 Python 缺少 pandas/numpy，导致 `ModuleNotFoundError`。

**错误日志示例**：
```
ModuleNotFoundError: No module named 'pandas'
```

**修复**：
1. 创建 shell wrapper（如 `daily_update_v2.sh`）：
   ```bash
   #!/bin/bash
   cd "$HOME/my_quant_system"
   exec "$HOME/my_quant_system/.venv/bin/python" "$HOME/.hermes/scripts/daily_update.py"
   ```
2. Cron job 的 `script` 字段指向 wrapper（`.sh`），不是 `.py`
3. `workdir` 仍需设为目标项目目录

**当前部署**：
- Wrapper: `~/.hermes/scripts/daily_update_v2.sh`
- Cron job: `fda7975b8524`
- `deliver=origin`（成功/失败都推送微信）

## Git Push 代理问题

**问题**：国内网络环境下 GitHub 直连可能超时。定时任务运行时如果依赖代理而上游代理不在线，`git push` 立即失败（connection refused）。`||` 降级链在 `set -e` + 子 shell 的环境下也可能提前退出，exit code 128。

**修复**：从 `~/.git-credentials` 提取 token，拼入 URL 直连推送（完全绕过代理和 credential helper 依赖）：
```bash
GIT_TOKEN=*** -o 'ghp_[^@]*' "$HOME/.git-credentials" 2>/dev/null | head -1)
if [ -n "$GIT_TOKEN" ]; then
    git -c http.proxy= -c https.proxy= push "https://YE2J:${GIT_TOKEN}@github.com/YE2J/potatohub.git" main
else
    git -c http.proxy= -c https.proxy= push origin main
fi
```

⚠️ `credential.helper=osxkeychain` 在 cron 非交互环境下通常无法访问 macOS Keychain，即使 `store` cache 了 token 也可能因为代理先拦截而失败。Token-in-URL 是最可靠的方案。

## 备份脚本：损坏 symlink 防护

**问题**：`cp -r` 遇到损坏的 symlink（目标已删除）直接报错退出，`set -e` 下整个脚本中断。

**修复**：
```bash
cp -R -L "$SKILLS_DIR" "$BACKUP_DIR/skills" 2>/dev/null || true
```
`-L` 选项跟随 symlink（损坏的不复制），`|| true` 容忍残余错误。

诊断：`file /path/to/symlink` → `broken symbolic link to ...` 可快速定位。`find ~/.hermes/skills -type l ! -exec test -e {} \; -print` 批量检测。

## Cron 故障诊断流程

当 `last_status: "error"` 时按此顺序排查：

1. **查输出** — `~/.hermes/cron/output/<job_id>/<timestamp>.md` 看 stdout 和 exit code
2. **区分原因**：
   - `exit code 128`（git）→ 代理/认证问题，检查 `git config --global --get http.proxy` 是否设置了死代理
   - `exit code 1`（Python）→ 依赖缺失/脚本语法错误，手动 `python script.py` 复现
   - `exit code 124`（timeout）→ 网络不通/API 挂了
3. **复现** — 用 `cronjob run <job_id>` 触发一次，等 30s 查状态
4. **如果修复涉及脚本** — 修完后手动 `bash script.sh` 跑一遍确认，再用 `cronjob run` 验证
5. **确认恢复** — `cronjob list` 看到 `last_status: "ok"` + `last_run_at` 是最新时间

- `cronjob list` 查看定时任务状态
- 两个 cron job：
  - `fda7975b8524`: 自选股日线更新（每天 00:00）→ `deliver=origin`（成功/失败推送微信）
  - `83a7d0a78cb1`: PotatoHub Skills 备份（周日 00:00）→ `deliver=local`
- 每个 job 的 `last_status` 为 `error` 时需要检查

### 快速健康检查

```bash
# 触发 cron 运行并观察
cronjob run fda7975b8524

# 等待30秒后手动验证数据
.venv/bin/python -c "
import sqlite3
db = sqlite3.connect('stock_data.db')
print(f'daily_kline: {db.execute(\"SELECT COUNT(*) FROM daily_kline\").fetchone()[0]} rows')
db.close()
"
```

⚠️ `cronjob run` 是通过 cron 系统异步运行的，不是同步执行。触发后等半分钟再检查结果。`last_status: "ok"` 表示最近一次运行成功。
