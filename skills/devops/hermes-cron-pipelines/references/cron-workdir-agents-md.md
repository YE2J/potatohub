# cron workdir 语义与 AGENTS.md 项目上下文（2026-08 验证）

## workdir 按任务类型的行为差异

`workdir` 参数（cronjob update 或 jobs.json 里的 `workdir`）的行为取决于 `no_agent` 标志：

| 任务类型 | `no_agent` | workdir 作用 | AGENTS.md 注入? |
|---------|-----------|--------------|-----------------|
| Agent | `false` | terminal/file/code_exec 起始 cwd = workdir；AGENTS.md/CLAUDE.md/.cursorrules 注入系统提示词 | ✅ 有 |
| Script | `true` | 仅作为脚本 subprocess 的 cwd（cron/scheduler.py `cwd=_script_cwd`，缺省回退为脚本目录 parent） | ❌ 无（无 LLM 参与） |

## 关键结论（实测验证，2026-08-05）

1. **no_agent 脚本任务加 workdir ≠ AGENTS.md 生效**。晨报 v7（daily_morning_report_v7.sh）是 no_agent 全绝对路径脚本（`$HOME/my_quant_system/stock_data.db`、`SCRIPT_DIR` 自定位），加 workdir 后 cwd 变化对执行零影响。想验证 AGENTS.md 效果别在 no_agent 任务上浪费时间。
2. **agent 模式任务才是 AGENTS.md 试金石**。给「交易日历-Tushare同步」（agent 模式）加 workdir 后手动触发，任务启动即带项目上下文；prompt 里原有的 `cd ~/my_quant_system` 保持幂等不冲突（workdir 只是 terminal 初始 cwd，不是强制重定位）。
3. workdir 目录不存在时 scheduler 静默回退：记 warning 后按无 workdir 跑（`Path(_job_workdir).is_dir()` 检查），不报错、不失败——排查"为什么 workdir 没生效"时先确认目录存在。
4. 带 workdir 的 agent 任务在单线程顺序池跑（`_terminal_cwd_lock` 写者锁，防 env 互相污染），不带 workdir 的任务并行。耗时任务别塞 workdir，否则会阻塞其他 workdir 任务排队。

## 验证 cron 真实运行的方法

`cronjob action='run'` 按下一个 tick 执行，返回 `executed: true / execution_success: true`。但**判断是否真的跑通**要看：

```
~/.hermes/cron/output/<job_id>/<timestamp>.md
```

该文件含完整 Prompt + Response 全文（含 `## Response` 段），是唯一可靠的方式——`last_status: ok` 只代表进程退出码为 0，不代表任务逻辑正确。

⚠️ 手动触发注意：
- no_agent 任务（如晨报）手动跑会**真的推送**到 deliver 目标（微信）——验证前先想好会不会打扰用户；想只测脚本可用，直接 `bash ~/.hermes/scripts/xxx.sh > /tmp/out.txt` 手动模拟（不触发 cron 推送）。
- agent 任务 `deliver: local` 则手动触发安全（无外部推送）。

## 相关源码位置（hermes-agent 仓库）

- cron/scheduler.py `_run_job_script()`：`_script_cwd = workdir or str(path.parent)` — no_agent 脚本 cwd 逻辑
- cron/scheduler.py 3047-3077：agent 模式 workdir 解析（先校验目录存在再传给 cwd=），以及 `_terminal_cwd_lock` 顺序池
- hermes_cli/init_command.py：`/init` 的提示词构造（见 agents-md-generation.md）
