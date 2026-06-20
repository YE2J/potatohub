# Web 应用自选股页面排障

## 架构

Web 前端（FastAPI + Jinja2）通过 `web_data/watchlist.json` 读取自选股，**非直接读 SQLite**。
JSON 通过 `_wl_export_db_to_json()` 从 SQLite 导出生成。

## ⚠️ 头号陷阱：JavaScript 覆盖服务端渲染数据

**症状**：页面加载瞬间闪现正确数据（0.01 秒），然后全部变成「暂无行情」。

**根因**：`watchlist.html` 的 `DOMContentLoaded` 事件中调用 `loadStocks(currentGroup)`，该函数 fetch `/api/watchlist/export` API（不含行情 quote 数据），然后用 `innerHTML` 覆盖掉服务端 Jinja2 渲染好的完整行情数据。

**识别方法**：
```bash
curl -s http://127.0.0.1:8001/watchlist | python3 -c "
import sys,re; h=sys.stdin.read()
print(f'服务端渲染: {len(re.findall(r\"data-close\", h))} 只有 data-close')
print(f'暂无行情: {h.count(\"暂无行情\")} 处')
"
```

**修复**：
1. 移除 `DOMContentLoaded` 中的 `loadStocks(currentGroup)` 调用
2. 分组切换、增删股票改用 `location.reload()` / `location.href`
3. 后端 `?group=` 参数控制内容区，侧边栏始终传全量 `all_groups`

---

## 常见 500 错误

### 1. 行情字段 NULL

`_get_latest_kline()` 返回值加 `or 0` 兜底。查询优先 `close > 0 ORDER BY date DESC`（日期优先），非完整性优先。

### 2. JSON 不同步

调 `_wl_export_db_to_json()` 重新生成。

### 3. ETF 名称 GBK 乱码

用 sqlite3 CLI 直接 UPDATE，或问财 API 获取 UTF-8 名称。

### 4. 旧进程占端口

```bash
kill -9 $(lsof -ti:8001) && sleep 2
lsof -i:8001 || echo "端口干净"
find ~/my_quant_system -name __pycache__ -exec rm -rf {} +
```

### 5. __pycache__ 残留

`PYTHONDONTWRITEBYTECODE=1` 启动 + 清缓存。

---

## 分组切换正确实现

- 侧边栏：迭代 `groups`（全量）
- 内容区：迭代 `display_groups[0].stocks`
- 切换：`window.location.href = '/watchlist?group=' + encodeURIComponent(gid)`
- **禁止** `DOMContentLoaded` 中调 `loadStocks()`

## 行情补齐 SOP

1. **名称**：问财 → `{code} 股票简称`
2. **OHLCV**：问财 → `{codes} 开盘价 最高价 最低价 收盘价 成交量 涨跌幅`（≤15只/批，成交量单位股需/100）
3. **涨跌幅兜底**：SQL `(今日close-昨日close)/昨日close*100`
