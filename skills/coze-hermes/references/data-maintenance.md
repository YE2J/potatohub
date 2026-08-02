# 前复权数据维护流程

> 最后更新：2026-06-26

## 代码体系

`daily_kline.stock_code` 存储恒生聚源 InnerCode，不是股票代码。

### 自选股映射

| 股票代码 | 名称 | InnerCode |
|----------|------|-----------|
| 000988 | 华工科技 | 605 |
| 000999 | 华润三九 | 614 |
| 301338 | 凯格精机 | 334847 |
| 301526 | 国际复材 | 383796 |

查询时用 InnerCode：
```sql
SELECT * FROM daily_kline WHERE stock_code IN ('605','614','334847','383796');
```

## 增量数据导入流程

Coze 推送增量 CSV.gz 到项目空间后：

```bash
# 1. 下载
cd ~/.hermes/health_shared/data/
coze agent file download \
  --project-id 7652507431196688676 \
  --project-file-path /data/qfq/qfq_incremental_MMDD.csv.gz

# 2. 解压（先清理旧文件）
rm -f qfq_incremental_*.csv
gunzip qfq_incremental_MMDD.csv.gz
wc -l qfq_incremental_MMDD.csv  # 验证行数

# 3. 导入
python3 << 'EOF'
import sqlite3, csv
db_path = '/Users/yellow/my_quant_system/stock_data.db'
csv_path = '/Users/yellow/.hermes/health_shared/data/qfq_incremental_MMDD.csv'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
with open(csv_path) as f:
    reader = csv.reader(f)
    next(reader)
    batch = []; count = 0
    for row in reader:
        ic, td, op, hp, lp, cp, vol, amt = row
        batch.append((ic, td, float(op), float(hp), float(lp), float(cp),
                       float(vol or 0), float(amt or 0), None, None, None, None))
        count += 1
        if len(batch) >= 5000:
            cur.executemany("INSERT OR REPLACE INTO daily_kline VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", batch)
            batch = []
    if batch:
        cur.executemany("INSERT OR REPLACE INTO daily_kline VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", batch)
conn.commit()
print(f"导入: {count} 行, 总计: {cur.execute('SELECT COUNT(*) FROM daily_kline').fetchone()[0]}")
conn.close()
EOF

# 4. 验证
sqlite3 /Users/yellow/my_quant_system/stock_data.db \
  "SELECT date, COUNT(*) FROM daily_kline WHERE date >= 'YYYY-MM-DD' GROUP BY date ORDER BY date;"

# 5. 清理
rm qfq_incremental_MMDD.csv
```

## 日期格式统一

当表中混用 `YYYYMMDD` 和 `YYYY-MM-DD` 两种格式时：

```sql
-- 1. 删除与新格式重叠的旧数据（新格式 5,000+ 只/天，旧格式 ~100 只）
DELETE FROM daily_kline 
WHERE length(date)=8 
  AND substr(date,1,4)||'-'||substr(date,5,2)||'-'||substr(date,7,2) IN (
    SELECT date FROM daily_kline WHERE date LIKE '%-%'
  );

-- 2. 转换剩余旧格式日期
UPDATE daily_kline 
SET date = substr(date,1,4)||'-'||substr(date,5,2)||'-'||substr(date,7,2) 
WHERE length(date)=8;

-- 3. 验证无残留
SELECT COUNT(*) FROM daily_kline WHERE length(date)=8;  -- 应为 0
```

## 交易日历（2026 年 6 月）

| 日期 | 星期 | 状态 |
|------|------|------|
| 06-01 ~ 06-05 | 一~五 | 交易日 |
| 06-08 ~ 06-12 | 一~五 | 交易日 |
| 06-15 ~ 06-18 | 一~四 | 交易日 |
| 06-19 | 五 | 🎉 端午节休市 |
| 06-20 ~ 06-21 | 六日 | 周末 |
| 06-22 ~ 06-26 | 一~五 | 交易日 |

序列：06-18 → 06-22（跳过端午+周末）

## 验证查询

```sql
-- 完整覆盖检查
SELECT date, COUNT(*) FROM daily_kline 
WHERE date >= '2026-06-01'
GROUP BY date ORDER BY date;

-- 自选股状态
SELECT date,
  MAX(CASE WHEN stock_code='334847' THEN close END) as '301338凯格',
  MAX(CASE WHEN stock_code='383796' THEN close END) as '301526国际复材',
  MAX(CASE WHEN stock_code='605' THEN close END) as '000988华工',
  MAX(CASE WHEN stock_code='614' THEN close END) as '000999华润三九'
FROM daily_kline
WHERE stock_code IN ('334847','383796','605','614')
  AND date >= '2026-06-20'
GROUP BY date ORDER BY date;
```
