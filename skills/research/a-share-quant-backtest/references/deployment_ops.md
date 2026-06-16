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

## Git Push 代理降级

**问题**：git 全局配置了代理（`http.proxy=http://127.0.0.1:18789` → Karing），定时任务运行时代理可能不在线，导致 `git push` 失败：`Proxy CONNECT aborted`。

**修复**：push 命令加降级链：
```bash
git push origin main 2>&1 || \
git -c http.proxy= -c https.proxy= push origin main 2>&1 || true
```

## 日常巡检

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
