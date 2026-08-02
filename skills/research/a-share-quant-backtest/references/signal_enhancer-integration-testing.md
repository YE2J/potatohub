# signal_enhancer 集成验证模式（2026-07-05）

## 验证脚本模板

修改 `signal_enhancer.py` 或 `backtest_v4.py` 的增强信号集成后，创建 `test_enhanced.py` 做系统验证。

### 六项检查

| # | 检查 | 验证内容 | 常见失败模式 |
|---|------|---------|-------------|
| 1 | **模块导入** | 3 个核心函数加载成功 | `sys.path` 错误、`_safe_query` 模块级调用静默失败 |
| 2 | **DB 表结构** | 4 张增强表列数/行数/列名前 8 个 | 新表不存在、列名与代码不匹配 |
| 3 | **语法检查** | `backtest_v4.py` + `signal_enhancer.py` 编译通过 | patch/merge 导致缩进损坏 |
| 4 | **快速功能测试** | 用模拟 dict 调用 3 个核心函数 | 参数签名不匹配（dict vs 平铺参数） |
| 5 | **CLI 帮助** | `--enhanced --help` 正常输出 | argparse 冲突 |
| 6 | **端到端回测** | 单股回测 `--enhanced --codes 000899` 完整跑完 | SQL 列名错误、缩进错误、数据缺失 |

### 发现流程

```
创建 test_enhanced.py → 运行 → 检查失败项:
  模块导入失败     → sys.path / import 路径
  DB 列名不匹配   → PRAGMA table_info 查实际列名 → patch signal_enhancer
  语法错误         → compile / indentation fix
  函数调用失败     → 查函数签名 → 调整测试参数
  SQL 运行时错误   → 查 actual 表结构 → 修正 SQL
```

## PRAGMA 表结构查询

```bash
# 查看所有表
sqlite3 stock_data.db ".tables"

# 查看表列名（列名不匹配是 #1 错误源）
sqlite3 stock_data.db "PRAGMA table_info(limit_up_pool);"

# 查看示例数据
sqlite3 stock_data.db "SELECT * FROM limit_up_pool LIMIT 1;"
```

## 已发现的列名不匹配（修复于 2026-07-05）

| 表 | 代码中写的列名 | 实际列名 | 影响查询 |
|----|---------------|---------|---------|
| `limit_up_pool` | `first_time`, `last_time` | `first_limit_time`, `last_limit_time` | 涨停强度评分（3分）全为 0 |
| `limit_up_ladder` | `nums` | `board_nums` | 连板情绪评分（2分）全为 0 |

## 修复工作流（已验证）

```bash
# Step 1: 创建验证脚本
cd ~/my_quant_system
cat > test_enhanced.py << 'PYEOF'
# ... 见模板 ...
PYEOF

# Step 2: 运行验证
~/.pyenv/versions/3.11.11/bin/python3 test_enhanced.py

# Step 3: 修复列名不匹配
# 在 signal_enhancer.py 中用 PRAGMA 确认后 patch

# Step 4: 重新验证
~/.pyenv/versions/3.11.11/bin/python3 test_enhanced.py

# Step 5: 端到端回测
~/.pyenv/versions/3.11.11/bin/python3 backtest_v4.py \
  --enhanced --codes 000899 --capital 100000 --max-pos 3
```

## 关键细节

### 函数签名（signal_enhancer.py）

```python
# 买入：接收 base_signal dict，非平铺参数
def enhance_buy_signal(
    base_signal: Dict[str, Any],       # 含 gs_ok/cross_zero/holding_ok/inflow_ok
    conn: Optional[sqlite3.Connection] = None,
    trade_date: Optional[str] = None,
    stock_code: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:      # (score 0-20, detail_dict)

# 卖出：接收 position_info dict
def enhance_sell_signal(
    position_info: Dict[str, Any],     # 含 profit_pct/peak_profit_pct/zhuli_last_3/...
    conn: Optional[sqlite3.Connection] = None,
    trade_date: Optional[str] = None,
    stock_code: Optional[str] = None,
) -> Tuple[str, str]:                 # (A_强制卖出/B_建议卖出/C_减半仓/NONE, reason)

# 动态仓位：接收 conn + date
def dynamic_max_positions(
    conn: sqlite3.Connection,
    trade_date: str,
    default_max: int = 3,
) -> int:
```

### 常见诱导错误

- **`_safe_query` 模块级调用**：如果 `_safe_query()` 在模块顶层被调用且 `conn=None`，抛出 `AttributeError: 'int' object has no attribute 'execute'`。虽被 except 捕获，但打印的"查询异常"信息造成困惑。应仅在函数内按需创建连接。
- **dict 参数传递**：`enhance_buy_signal` 和 `enhance_sell_signal` 都接收 dict，不是平铺参数。单元测试必须用 dict，否则 TypeError。
- **DB 列名与代码 SQL 不同步**：`Financial-API` 管线创建的表使用实际同花顺/Tushare 的列名，手动编写的 SQL 查询容易写错。每次修改 SQL 后必须用 PRAGMA 验证。
