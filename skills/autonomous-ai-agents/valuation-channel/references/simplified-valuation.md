# Simplified Valuation Subprocess (快速估值替代方案)

## 问题

`ValuationAssessor.evaluate()` 因调用 5 个估值模型（DCF/PB-ROE/格雷厄姆/PEG/DDM）+ 多次 akshare 网络请求，单只股票耗时约 **460 秒**。不适合批量处理或 Web 在线调用。

## 快速替代方案

直接从本地 SQLite 数据库读取已缓存的日线数据，只做 PE 通道图计算 + 简单安全边际评级，**单只耗时约 1 秒**。

## 实现要点

### 数据源
- K 线从已缓存的 `stock_data.db`（`daily_kline` 表）读取，**不经过 akshare**
- EPS 仍从 akshare `stock_financial_abstract_ths` 获取（这个接口在国外可访问，约 0.4s/只）
- 估值图保存到 `reports/valuation/{code}.png`

### 评级简化
只用 PE 通道位置 + 安全边际，不做多模型融合：

| 安全边际 | 通道位置 | 评级 |
|---------|---------|------|
| > 20% | — | ⭐⭐⭐⭐⭐ 强烈推荐 |
| > 5% | — | ⭐⭐⭐⭐ 推荐 |
| — | < 30% | ⭐⭐⭐ 中性(通道低位) |
| — | < 70% | ⭐⭐⭐ 中性 |
| — | 其他 | ⭐⭐ 谨慎 |

### 子进程隔离

```python
import subprocess, json

def run_valuation(codes: list) -> list:
    """通过子进程运行估值，返回结果列表"""
    result = subprocess.run(
        [sys.executable, 'run_valuation_subprocess.py', json.dumps(codes, ensure_ascii=False)],
        capture_output=True, text=True, timeout=300
    )
    output = result.stdout
    marker = "---RESULT_JSON---"
    if marker in output:
        json_str = output.split(marker)[1].split("---END---")[0].strip()
        return json.loads(json_str)
    return []
```

### 数据库存储
结果存入 `valuation_results` 表：

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | 自增 |
| stock_code | TEXT | 股票代码 |
| stock_name | TEXT | 股票名称 |
| current_price | REAL | 当前价 |
| pe_ttm | REAL | PE-TTM |
| channel_position | REAL | 通道位置(0~1) |
| min_pe / median_pe | REAL | 通道统计 |
| consensus_fair / low / high | REAL | 估值区间 |
| safety_margin | REAL | 安全边际 |
| rating / stars | TEXT | 评级 |
| report_text | TEXT | 报告文本 |
| chart_path | TEXT | PE通道图路径 |
| run_date / timestamp | DATETIME | 运行时间 |

### 性能对比

| 方案 | 单只耗时 | 104只耗时 | 适用场景 |
|------|---------|-----------|---------|
| `ValuationAssessor.evaluate()` | ~460s | ~13h | ❌ 不推荐 |
| 简化版(SQLite+快速PE) | ~1s | ~30s | ✅ 批量/Web |
