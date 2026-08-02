# is_open 类型比较 Bug 案例

**发现日期**: 2026-07-22  
**发现方式**: 用户报告晨报异常 → 手动追踪  
**Agent 漏检**: 4-Agent 评审全部通过，无人发现

## 问题
```python
# trade_cal.is_open 在 SQLite 中为 INTEGER (0/1)
is_open = is_trade and is_trade[0] == '1'
# Python: 1 == '1' → False
```

## 根因
1. SQLite 的 SQL 层是类型宽松的：`WHERE is_open='1'` 正常工作，掩盖了类型问题
2. Python fetchone() 后是严格类型：`int(1) == str('1')` → `False`
3. 静态代码审查无法发现——必须执行 `PRAGMA table_info` 确认列类型

## 修复
```python
is_open = is_trade and int(is_trade[0]) == 1
```

## 教训
- 涉及 `trade_cal.is_open` 或类似数据库布尔字段的代码，必须先跑 `PRAGMA table_info` 确认类型
- SQL 层和 Python 层的类型规则不同，同一个比较操作符在两层含义不同
- 这在 Xiaomi 故障统计中排名第 3（类型/模式不匹配，共 3 次）
