# 量化系统 Web 服务运维

## FastAPI 服务管理

服务入口：`~/my_quant_system/app/main.py`，端口 8001。

### 启动

```bash
cd ~/my_quant_system
PYTHONDONTWRITEBYTECODE=1 ~/my_quant_system/.venv/bin/python3 -c "
import uvicorn
uvicorn.run('app.main:app', host='127.0.0.1', port=8001, reload=False)
"
```

### ⚠️ 关键坑点：旧进程占端口

**症状**：修改代码后重启服务，页面仍然显示旧数据，curl 测试正常但修改不生效。

**根因**：`kill -9 $(lsof -ti:8001)` 未杀干净（lsof 可能返回不同 PID），旧进程仍然占有端口，新进程静默失败。

**正确重启流程**：

```bash
# 1. 确认并杀死所有占用端口的进程
lsof -i:8001                    # 看实际 PID
kill -9 $(lsof -ti:8001)        # 杀进程
sleep 2
lsof -i:8001 2>/dev/null || echo "端口已释放"  # 确认干净

# 2. 清 Python 缓存
find ~/my_quant_system -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find ~/my_quant_system -name "*.pyc" -delete 2>/dev/null

# 3. 启动（设置 PYTHONDONTWRITEBYTECODE）
cd ~/my_quant_system && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -c "
import uvicorn
uvicorn.run('app.main:app', host='127.0.0.1', port=8001, reload=False)
"
```

### 健康检查

```bash
curl -s http://127.0.0.1:8001/ -o /dev/null -w "%{http_code}"  # 主页
curl -s http://127.0.0.1:8001/watchlist -o /dev/null -w "%{http_code}"  # 自选股
```

### 常见 500 错误

1. **模板 `NoneType` 错误**：`_get_latest_kline()` 返回的字段为 None，模板 `%.2f|format(None)` 抛异常。修复：返回值加 `or 0` 兜底。
2. **JSON 与 SQLite 不同步**：Web 从 `web_data/watchlist.json` 读数据，增删股票后需调用 `_wl_export_db_to_json()` 重新生成 JSON。
3. **GBK 乱码**：腾讯 API 的 ETF 名称是 GBK 编码，写入 SQLite 后用 Python 读取会报 `Could not decode to UTF-8`。ETF 名称用问财 API 获取或手动赋值。

### CDN 加速

Bootstrap 默认用 jsdelivr（中国大陆慢），已切为 bootcdn：

```html
<link href="https://cdn.bootcdn.net/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.bootcdn.net/ajax/libs/bootstrap/5.3.0/js/bootstrap.bundle.min.js"></script>
```

模板文件：`~/my_quant_system/app/templates/base.html`
