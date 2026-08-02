#!/bin/bash
# cron_log_helper.sh — Cron 推送日志通用帮手
# 被所有 cron wrapper source，统一写入 cron_push_log 表
#
# 用法:
#   source "$HOME/.hermes/scripts/cron_log_helper.sh"
#   cron_log_init "任务名称" "job_id" "ScheduledTime" "delivery_channel"
#   ... 跑脚本 ...
#   cron_log_finish $? "status" ["content_path"]

set -u

CRON_DB="$HOME/my_quant_system/stock_data.db"
CRON_SQLITE="$HOME/.hermes/venv_cron/bin/python3"
CRON_TEMP_LOG="/tmp/cron_log_tail.$$.txt"

_CRON_LOG_ID=""
_CRON_START_EPOCH=""

cron_log_init() {
    local job_name="${1:-}"; local job_id="${2:-}"
    local scheduled="${3:-$(date '+%Y-%m-%d %H:%M:%S')}"
    local channel="${4:-local}"
    [ -z "$job_name" ] && { echo "[CRON_LOG] ERROR: job_name required" >&2; return 1; }

    _CRON_START_EPOCH=$(date +%s%3N)
    local now; now=$(date '+%Y-%m-%d %H:%M:%S')
    : > "$CRON_TEMP_LOG"

    local log_id
    log_id=$("$CRON_SQLITE" -c "
import sqlite3, sys
db = sqlite3.connect('$CRON_DB')
cur = db.execute('''
    INSERT INTO cron_push_log
        (job_name, job_id, scheduled_time, actual_time, status, delivery_channel, delivery_status)
    VALUES (?, ?, ?, ?, 'running', ?, 'pending')
''', ('$job_name', '$job_id', '$scheduled', '$now', '$channel'))
db.commit(); print(cur.lastrowid); db.close()
" 2>/dev/null)

    [ -z "$log_id" ] || [ "$log_id" = "None" ] && { _CRON_LOG_ID=""; return 0; }
    _CRON_LOG_ID="$log_id"
    echo "[CRON_LOG] log_id=$_CRON_LOG_ID job=$job_name" >&2
}

cron_log_finish() {
    local exit_code="${1:-0}"; local status="${2:-}"
    local content_path="${3:-}"

    [ -z "$status" ] && { [ "$exit_code" -eq 0 ] && status="success" || status="failed"; }
    [ "$exit_code" -eq 124 ] && status="timeout"

    local now; now=$(date '+%Y-%m-%d %H:%M:%S')
    local now_epoch; now_epoch=$(date +%s%3N)
    local duration_ms=0
    [ -n "$_CRON_START_EPOCH" ] && [ "$_CRON_START_EPOCH" -gt 0 ] && duration_ms=$((now_epoch - _CRON_START_EPOCH))

    local log_tail=""
    [ -f "$CRON_TEMP_LOG" ] && { log_tail=$(tail -20 "$CRON_TEMP_LOG"); rm -f "$CRON_TEMP_LOG"; }
    # 写入日志尾部到临时文件供 Python 安全读取（避免 shell 引号注入）
    local log_tail_file="/tmp/cron_log_tail_data.$$.txt"
    if [ -f "$CRON_TEMP_LOG" ]; then
        tail -20 "$CRON_TEMP_LOG" > "$log_tail_file" 2>/dev/null
        rm -f "$CRON_TEMP_LOG"
    fi

    local content_size="" content_hash=""
    [ -n "$content_path" ] && [ -f "$content_path" ] && {
        content_size=$(wc -c < "$content_path" | tr -d ' ')
        content_hash=$(shasum -a 256 "$content_path" 2>/dev/null | cut -d' ' -f1)
    }

    [ -z "$_CRON_LOG_ID" ] && { rm -f "$log_tail_file"; return 0; }

    # NOTE: log_tail 从临时文件读取而非 shell 变量展开，
    # 避免 ${log_tail:+'$log_tail'} 在 log_tail 含单引号时生成非法 Python 代码
    "$CRON_SQLITE" -c "
import sqlite3, os
db = sqlite3.connect(os.path.expanduser('$CRON_DB'))

log_tail = ''
lf = '$log_tail_file'
if os.path.exists(lf):
    with open(lf) as f:
        log_tail = f.read()
    os.unlink(lf)

db.execute('''
    UPDATE cron_push_log SET
        finished_time=?, status=?, duration_ms=?, exit_code=?,
        content_path=?, content_size=?, content_hash=?,
        log_tail=?, delivery_status=CASE WHEN ?='success' THEN 'n/a' ELSE delivery_status END
    WHERE log_id=?
''', ('$now','$status',$duration_ms,$exit_code,
      '${content_path:-}',${content_size:-0},'${content_hash:-}',
      log_tail,'$status',$_CRON_LOG_ID))
db.commit(); db.close()
" 2>/dev/null
    echo "[CRON_LOG] done log_id=$_CRON_LOG_ID status=$status duration=${duration_ms}ms" >&2
}

cron_log_tail() { tee -a "$CRON_TEMP_LOG"; }

cron_log_error() {
    local msg="${1:-unknown error}"; msg="${msg//\'/\'\'}"
    [ -z "$_CRON_LOG_ID" ] && return 0
    "$CRON_SQLITE" -c "
import sqlite3
db = sqlite3.connect('$CRON_DB')
db.execute(\"UPDATE cron_push_log SET error_message=? WHERE log_id=?\", (\"$msg\", $_CRON_LOG_ID))
db.commit(); db.close()
" 2>/dev/null
}
