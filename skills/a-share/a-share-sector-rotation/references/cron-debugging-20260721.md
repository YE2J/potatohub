# Cron管线调试记录（2026-07-21）

## 问题：数据停留在20260717，20260720未更新

表面现象：所有管线cron显示status=ok，但DB数据停在07-17。

## 根因排查

### 1. Shell脚本不可执行

```bash
ls -la ~/.hermes/scripts/daily_sector_moneyflow_dc.sh
# → -rw------- (无执行权限)
```

cron 尝试执行但 bash 拒绝（exit 126），Hermes 将 exit 126 误报为 `last_status: ok`。

**修复**: `chmod +x ~/.hermes/scripts/*.sh`

**检测**: 永远不只查 `last_status`，还要查 `ls -la` 确认 `-rwx`。

### 2. no_agent cron 脚本路径解析

对于 `no_agent=true` 的 cron，`script` 字段相对路径从 `~/.hermes/scripts/` 解析。

```json
// bad: 脚本在 ~/my_quant_system/engines/ 但在 ~/.hermes/scripts/ 找不到
{ "script": "engines/market_temperature.py", "no_agent": true }
```

**修复方案A — 桥接wrapper**: 在 `~/.hermes/scripts/` 创建 `.sh` wrapper，cd 到项目目录调用Python

```bash
# ~/.hermes/scripts/daily_margin_balance.sh
#!/bin/bash
set -euo pipefail
cd "$HOME/my_quant_system"
"$HOME/.pyenv/versions/3.11.11/bin/python3" scripts/daily_margin_balance.py
```

**修复方案B — 软链**:

```bash
mkdir -p ~/.hermes/scripts/engines
ln -sf ~/my_quant_system/engines/market_temperature.py ~/.hermes/scripts/engines/market_temperature.py
```

**注意**: `workdir` 只设 CWD，不改变脚本搜索路径。

### 3. Token 泄露预防

两融余额脚本 `daily_margin_balance.py` 之前：

```python
import tushare as ts          # 顶层import
pro = ts.pro_api(token)       # token 在内存
# ... 如果异常，token 出现在 traceback
```

修复后：

```python
try:
    import tushare as ts
except ImportError:
    print("❌ tushare 未安装"); sys.exit(1)
pro = ts.pro_api(token)
token = None                  # 用完即清
try:
    # 主逻辑
except Exception:
    print("❌ 两融余额采集异常")  # 不打印异常详情
    sys.exit(1)
```

### 4. _signal_handler 修复

`daily_margin_balance.py` 中 `_signal_handler(None, None)` 被用作清理退出函数。
但 `sys.exit(128 + None)` → TypeError：

```python
# 修复前
def _signal_handler(signum, frame):
    sys.exit(128 + signum)     # signum=None → crash

# 修复后
def _signal_handler(signum, frame):
    for c in _open_conns:
        try: c.close()
        except: pass
    if signum is not None:
        sys.exit(128 + signum)
```

### 5. 两融数据 T+1~2 延迟

Tushare margin API 当天（18:35）可能无数据。数据通常在 T+1 或 T+2 才可用。
cron 运行后写入0行，但这并非bug。

**处理**: 可接受延迟（晨报显示"无两融余额数据"），或改cron到20:00以后。

## 诊断命令汇总

```bash
# 1. 检查cron状态
cronjob action=list | grep -E "error|last_status"

# 2. 检查脚本权限
ls -la ~/.hermes/scripts/*.sh | grep -v '^-r.x'

# 3. 检查引擎脚本是否在正确路径
ls ~/.hermes/scripts/engines/*.py 2>/dev/null || echo "需要软链"

# 4. 检查数据最新日期
sqlite3 ~/my_quant_system/stock_data.db \
  "SELECT 'margin' as t, MAX(trade_date) FROM margin_balance
   UNION ALL SELECT 'dc_sector', MAX(trade_date) FROM sector_moneyflow_dc
   UNION ALL SELECT 'dc_industry', MAX(trade_date) FROM industry_moneyflow_dc"

# 5. 检查cron输出文件
ls -la ~/.hermes/cron/output/<job_id>_*.md 2>/dev/null | tail -3

# 6. 手动触发脚本测试
cd ~/my_quant_system && TUSHARE_TOKEN=$(grep TUSHARE_TOKEN ~/.hermes/.env.tushare | head -1 | sed 's/.*=//' | tr -d '"') python3 scripts/daily_sector_moneyflow_dc.py --date YYYYMMDD
```
