# 日报协作故障排查手册

> 关联: `coze-hermes` Skill, 创建于 2026-06-19

## Cron 120s 超时

### 症状
`~/.hermes/cron/output/<job_id>/` 里输出: `Script timed out after 120s`

### 排查
```bash
# 1. 找到失败 job
hermes cron list | grep -A5 error

# 2. 看具体错误
cat ~/.hermes/cron/output/<job_id>/*.md
```

### 根因分析模板
直接读脚本，手算时间线：
```
启动 → sleep N1 → check → sleep N2 → check → ... → timeout → Python → cleanup
总耗时 = (轮询次数 × interval) + Python耗时 + cleanup耗时
```

如果 `轮询部分 > 60s`，就是瓶颈。

### 修复
```bash
# 在 hermes_daily_report.sh 里：
MAX_WAIT=30        # 从 90 改
POLL_INTERVAL=10   # 从 30 改
# cleanup 加 & 后台
```

## Python venv: macOS 26.2 dyld 兼容性

### 症状
```
ImportError: Symbol not found: _XML_SetAllocTrackerActivationThreshold
  Referenced from: .../pyexpat.cpython-311-darwin.so
  Expected in: /usr/lib/libexpat.1.dylib
```

### 根因
Homebrew Python 3.11.15_3 的 bottle 编译时链接了旧版 libexpat，与 macOS 26.2 的 `/usr/lib/libexpat.1.dylib` 不兼容。

### 修复（推荐：用系统 Python）
```bash
# 1. 保留坏 venv（避免 rm -rf 授权弹窗）
mv .venv .venv.broken.$(date +%Y%m%d)

# 2. 用系统 Python 重建
/usr/bin/python3 -m venv .venv

# 3. 升级 pip + 装依赖
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 4. 验证
.venv/bin/python3 -c "import pandas, akshare, sqlite3; print('venv OK')"
```

### 兼容性
系统 Python 3.9.6 对量化栈完全兼容：
- pandas ≥ 2.2.0 ✓ (实际装 2.3.3)
- akshare ≥ 1.16.0 ✓ (实际装 1.18.64)
- 唯一非致命警告：urllib3 的 LibreSSL vs OpenSSL 警告，不影响 akshare

### 备选方案（未验证）
等 Homebrew 出 macOS 26.2 兼容的 Python 3.11 bottle 后 `brew upgrade python@3.11`

## SIGTERM handler 模式

### 问题
Cron 超时发 SIGTERM 杀 Python 进程时，`etl_runs.status` 留在 `'running'`。

### 修复模板
```python
import signal

_CURRENT_RUN_ID = None

def _handle_sigterm(signum, frame):
    if _CURRENT_RUN_ID is not None:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute(
            "UPDATE etl_runs SET status='failed', finished_at=datetime('now'), "
            "error_message='killed by SIGTERM (cron timeout)' "
            "WHERE run_id=? AND status='running'",
            (_CURRENT_RUN_ID,)
        )
        conn.commit()
    sys.exit(1)

signal.signal(signal.SIGTERM, _handle_sigterm)

def main():
    global _CURRENT_RUN_ID
    with etl_run(...) as run:
        _CURRENT_RUN_ID = run.id
        # ... work ...
```

### 适用范围
所有被 cron job 以 `no_agent: true` + script 模式调用的 Python 脚本（coze_daily_report.sh → generate_daily_report.py 已加）。

## 协同排查工作流

当 Hermes x Coze 日报链路出问题时：

1. **Hermes 侧诊断** → 写 `hermes_timeout_diagnosis.md` 到共享目录
2. **双方各自读诊断报告** → 各自修改自己侧代码
3. **Hermes 侧修复** → 改脚本/venv/代码
4. **Hermes 侧补跑** → `bash scripts/coze_daily_report.sh`
5. **Hermes 侧反馈** → 写 `YYYY-MM-DD_hermes_feedback_coze.md`
6. **Coze 侧校验** → 读反馈，确认报告内容正确
