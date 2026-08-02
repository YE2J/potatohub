# API数据源字段映射验证方法论

> 当集成商业API数据源（如同花顺Financial-API）到现有SQLite系统时，字段映射是最常见的错误源。
> 本方法论用于在数据集成后快速验证字段映射正确性。

## 验证流程

### 第1步：对比API响应与表结构

```python
# 1) 调用一次API，观察实际返回字段
result = subprocess.run([fuyao_cli, cmd], capture_output=True, text=True)
sample = json.loads(result.stdout)

# 2) 获取表DDL
cursor.execute(f"PRAGMA table_info({table_name})")
table_cols = {r[1]: r[2] for r in cursor.fetchall()}

# 3) 对比
api_fields = set(sample[0].keys()) if isinstance(sample, list) else set(sample.keys())
table_fields = set(table_cols.keys())
print(f"API有但表没有: {api_fields - table_fields}")
print(f"表有但API没有: {table_fields - api_fields}")
```

### 第2步：NULL比率扫描

```python
cursor.execute(f"PRAGMA table_info({table_name})")
cols = [r[1] for r in cursor.fetchall()]
for col in cols:
    cnt = cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {col} IS NULL").fetchone()[0]
    total = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    if cnt > 0:
        print(f"  ⚠️ {col}: {cnt}/{total} NULL ({cnt/total*100:.0f}%)")
```

### 第3步：数据去重检查

```python
cursor.execute(f"SELECT {pk_cols}, COUNT(*) FROM {table_name} GROUP BY {pk_cols} HAVING COUNT(*) > 1")
dupes = cursor.fetchall()
if dupes:
    print(f"⚠️ PK重复: {len(dupes)}组")
```

### 第4步：语义验证

```python
cursor.execute(f"SELECT MIN(col), MAX(col), AVG(col) FROM {table_name} WHERE col IS NOT NULL")
min_v, max_v, avg_v = cursor.fetchone()
```

## 常见字段映射陷阱

| 陷阱 | 现象 | 根因 | 修复 |
|------|------|------|------|
| **字段名不匹配** | 字段全NULL | API字段名与表字段名不一致 | 查API文档，修改映射 |
| **数据源不提供** | 字段全NULL | 设计时假设了API提供某字段但实际不提供 | 删字段或从其他表JOIN补充 |
| **同一值写两列** | 两列数值完全相同 | 拷贝代码时忘了改字段名 | 检查映射逻辑 |
| **代码格式不一致** | JOIN失败/0行 | watchlist裸代码(600519) vs 带后缀(600519.SH) | 统一后缀或strip |
| **日期格式不统一** | SQL过滤错误 | API返回YYYYMMDD，表存YYYY-MM-DD | 写入层统一转换 |
| **单位不一致** | 数值偏差几个数量级 | API用亿元，表存元或反之 | 乘/除10000或100000000 |

## 本系统已修复的映射问题

| 问题 | 表 | 修复方式 |
|------|----|---------|
| daily_anomaly期望price/pct_chg但API返回tag_name/keyword_list | daily_anomaly | 重建表匹配API实际字段 |
| total_amount和buy_top_amount写入同一个值 | dragon_tiger_daily | 删total_amount列 |
| API有seal_money但没映射到fd_amount | limit_up_pool | 脚本加item.get(\"seal_money\") |
| API不直接返回涨跌幅/价格 | hot_stock_daily | 从daily_kline JOIN补充 |
