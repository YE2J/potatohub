---
name: ths-stock-monitor
description: "通过cua-driver操作Mac版同花顺，截图分析自选股数据，判断买卖信号并推送到微信"
version: 1.0.0
platforms: [macos]
author: Hermes Agent
tags: [同花顺, stock, monitoring, computer-use, wechat]
---

# 同花顺自选股监控

## 触发条件

当用户说"检查自选股"、"看看股票"、"监控一下"或类似指令时，执行本流程。

## 步骤

### 1. 确保同花顺在运行

```bash
CUADRIVER=/Applications/CuaDriver.app/Contents/MacOS/cua-driver
PID=$(python3 -c "
import json, subprocess
r = subprocess.run('$CUADRIVER call list_apps', shell=True, capture_output=True, text=True)
apps = json.loads(r.stdout)
for a in apps:
    if '同花' in a.get('app_name','') or 'IHexin' in a.get('bundle_id',''):
        print(a['pid'])
        break
")
if [ -z "$PID" ]; then
  PID=$(python3 -c "
import json, subprocess
r = subprocess.run(\"$CUADRIVER call launch_app '{\\\"bundle_id\\\": \\\"cn.com.10jqka.IHexin\\\"}'\", shell=True, capture_output=True, text=True)
print(json.loads(r.stdout)['pid'])
")
  sleep 8
fi
echo "PID=$PID"
```

### 2. 找到主窗口

```bash
WID=$(python3 -c "
import json, subprocess
r = subprocess.run('$CUADRIVER call list_windows', shell=True, capture_output=True, text=True)
windows = json.loads(r.stdout).get('windows', [])
for w in windows:
    if w.get('app_name','').strip() == '同花顺' and w.get('is_on_screen', False) and w.get('bounds',{}).get('width',0) > 800:
        print(w['window_id'])
        break
")
echo "WindowID=$WID"
```

### 3. 截图分析

```bash
# 截图当前 view
$CUADRIVER call get_window_state "{\"pid\": $PID, \"window_id\": $WID}" 2>&1 | python3 -c "
import sys, json, base64
data = json.load(sys.stdin)
b64 = data.get('screenshot_png_b64', '')
if b64 and len(b64) > 10000:
    with open('/tmp/ths_monitor.png', 'wb') as f:
        f.write(base64.b64decode(b64))
    print('SCREENSHOT_OK')
else:
    print('SCREENSHOT_FAILED')
"
```

### 4. 滚动查看更多股票

```bash
for i in 1 2 3; do
  $CUADRIVER call scroll "{\"pid\": $PID, \"direction\": \"down\", \"amount\": 5}"
  sleep 1
  $CUADRIVER call get_window_state "{\"pid\": $PID, \"window_id\": $WID}" 2>&1 | python3 -c "
import sys, json, base64
data = json.load(sys.stdin)
b64 = data.get('screenshot_png_b64', '')
if b64 and len(b64) > 10000:
    with open(f'/tmp/ths_scroll_$i.png', 'wb') as f:
        f.write(base64.b64decode(b64))
    print(f'SCROLL_$i_OK')
  "
done
```

### 5. Vision 分析自选股

用 `vision_analyze` 分析截图，找以下4只自选股：

- **凯格精机 (301338)**
- **华工科技 (000988)**
- **国际复材 (301526)**
- **华润三九 (000999)**

每只提取：
- 最新价
- 涨跌幅
- GS信号（G区间=买入信号, S区间=卖出信号）
- 主力资金（净流入/流出金额）
- 机构活跃度（强势线上/下）

### 6. 买卖信号判断

| GS信号 | 主力资金 | 机构活跃度 | 综合判断 |
|--------|---------|-----------|---------|
| G区间/G信号 | 净流入 | 强势线上或大牛线上 | **买入信号 🔥** |
| G区间 | 净流出 | 强势线下 | 谨慎关注 |
| S区间/S信号 | 净流出 | 强势线下 | **卖出信号 ⚠️** |
| S区间 | 净流入 | 强势线上 | 观望 |

### 7. 推送到微信

```python
from hermes_tools import terminal  # use send_message tool directly
```

用 `send_message(target="weixin", message=...)` 推送格式化的报告到微信。

### 报告格式

```
📊 自选股盘中监测

🟢 买入信号
【华润三九】24.85 +0.61%
  GS:G区间 | 主力+628.85万 | 强势线下
  理由：GS发出买入信号，主力小幅净流入

⚠️ 卖出信号
【凯格精机】142.05 -4.43%
  GS:S区间 | 主力-1.19亿 | 强势线上
  理由：GS卖出信号，主力大幅流出

💤 无信号
【华工科技】151.01 +0.51%
  GS:S区间 | 主力+1.44亿 | 强势线上
  理由：GS为S区间但主力流入，观望
```

## 已知限制与优化

1. **自选股太长时可能不在同一屏** → 需要多屏截图+滚动
2. **同花顺可能有关联弹窗** → 截图前检查是否有遮挡
3. **WeChat 有频率限制** → 消息不要太频繁
4. **GS信号仅作为参考** → 需要在报告中说明
