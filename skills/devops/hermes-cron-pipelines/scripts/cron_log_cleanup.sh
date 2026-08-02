#!/bin/bash
# cron_log_cleanup.sh — cron_push_log 表定期清理
# 每周日凌晨 03:00 执行
set -u

DB="$HOME/my_quant_system/stock_data.db"
PYTHON="$HOME/.hermes/venv_cron/bin/python3"

echo "📋 cron_push_log 清理 — $(date '+%Y-%m-%d %H:%M')"

# 清理超 60 天的成功记录
"$PYTHON" -c "
import sqlite3
db = sqlite3.connect('$DB')
cur = db.execute(\"\"\"
    DELETE FROM cron_push_log
    WHERE created_at < datetime('now', '-60 days')
      AND status IN ('success', 'skipped')
\"\"\")
db.commit()
print(f'  清理成功/跳过记录: {cur.rowcount} 条')
db.close()
"

# 清理超 180 天的失败记录
"$PYTHON" -c "
import sqlite3
db = sqlite3.connect('$DB')
cur = db.execute(\"\"\"
    DELETE FROM cron_push_log
    WHERE created_at < datetime('now', '-180 days')
      AND status = 'failed'
\"\"\")
db.commit()
print(f'  清理过期失败记录: {cur.rowcount} 条')
db.close()
"

# 清理超 7 天的 running 僵尸记录
"$PYTHON" -c "
import sqlite3
db = sqlite3.connect('$DB')
cur = db.execute(\"\"\"
    DELETE FROM cron_push_log
    WHERE status = 'running'
      AND created_at < datetime('now', '-7 days')
\"\"\")
db.commit()
if cur.rowcount:
    print(f'  ⚠️ 清理僵尸 running 记录: {cur.rowcount} 条')
db.close()
"

# 统计
"$PYTHON" -c "
import sqlite3
db = sqlite3.connect('$DB')
cur = db.execute('SELECT COUNT(*) FROM cron_push_log')
print(f'  cron_push_log 当前总记录数: {cur.fetchone()[0]}')
db.close()
"
echo "✅ 清理完成"
