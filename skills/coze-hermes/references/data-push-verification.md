# Coze 数据推送验证流程

当 Coze 完成数据推送（增量/全量）后，Hermes 应执行以下验证流程确认数据可用。

## 标准验证清单

```sql
-- 1. 基础元数据
SELECT COUNT(*) AS total_rows,
       MIN(date) AS min_date,
       MAX(date) AS max_date
FROM daily_kline;

-- 2. 日期格式一致性（常见坑：Coze 推送可能混用 YYYYMMDD 与 YYYY-MM-DD）
SELECT DISTINCT date FROM daily_kline
WHERE date LIKE '%-%' 
ORDER BY 1 LIMIT 5;
-- 若无结果，则所有日期均为 YYYYMMDD 格式
-- 若有结果，则存在混合格式

-- 3. 逐日股票覆盖度（发现不完整的天）
SELECT date, COUNT(*) AS stock_count
FROM daily_kline
WHERE date >= DATE('now', '-5 days')
GROUP BY date
ORDER BY date DESC;
-- 全量推送应为 5,000+ 只/天，增量推送约 100-150 只/天

-- 4. 自选股在最新日期是否有数据
SELECT stock_code, MAX(date) AS last_date, COUNT(*) AS days
FROM daily_kline
WHERE stock_code IN (<watchlist>)
GROUP BY stock_code
ORDER BY stock_code;
```

## 常见问题模式

### 日期格式混用
- **表现**：`YYYYMMDD` 与 `YYYY-MM-DD` 两种格式共存
- **影响**：按日期排序/筛选时，两种格式交错排列，`YYYY-MM-DD` 在 DESC 排序时排在 `YYYYMMDD` 之后（因为 `-` ASCII 45 < `0` ASCII 48）
- **根因**：Coze 推送脚本的日期格式化方式不一致
- **修复**：统一为 `YYYY-MM-DD`（ISO 8601 标准），ALTER TABLE 转换旧数据

### 股票代码体系不匹配
- **表现**：自选股在旧格式数据中有值，但在新格式全量数据中查不到
- **根因**：Coze 两次推送使用了不同的股票代码体系（恒生聚源 InnerCode vs 其他）
- **验证**：
  ```sql
  -- 检查自选股在新格式数据中是否存在
  SELECT stock_code, MAX(date) FROM daily_kline
  WHERE stock_code IN (<watchlist>)
    AND date LIKE '%-%'
  GROUP BY stock_code;
  ```

### 字段 NULL
- **表现**：`amplitude`, `pct_change`, `change`, `turnover` 为 NULL
- **影响**：依赖这些字段的分析脚本报错
- **处理**：Hermes 侧可从 close/pre_close 自行计算 pct_change 和 change，其余字段标注"暂不支持"

## 验证流程

```
Coze 推送完成 → Hermes 执行验证清单
                ├─ 通过 → 更新 memory 记录最新日期
                └─ 发现问题 → 向 Coze 发送工单报告
                              ├─ 格式问题（如日期格式）
                              └─ 数据问题（如缺失日期、代码不匹配）
```
