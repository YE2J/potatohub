# 策略武器库架构

## 目录结构
## 目录结构

```strategy_library/
├── __init__.py           ← 公开入口（catalog, indicators, core）
├── _core.py              ← TDX核心函数（SMA/EMA/CROSS/HHV/LLV/REF/SUM/COUNT/IF/MAX/MIN/ABS + safe_div）
├── _catalog.py           ← 注册表（INDICATORS + ENGINES dict + 加载/列表/打印 API）
├── indicators/
│   ├── __init__.py       ← 公开导入所有 calc_xxx 函数
│   ├── _zhuli_radar.py   ← 主力雷达
│   ├── _ai_activity.py   ← AI机构活跃度
│   ├── _gs_signal.py     ← GS信号
│   ├── _dark_pool.py     ← 暗盘资金
│   └── _zhuli_holdings.py ← 主力持仓
└── adapters/
    ├── __init__.py
    └── moneyflow.py      ← 资金流适配器（DB→降级估算→THS列映射）
```

## 设计原则

1. **每个指标独立模块** — 可单独调用，不互相依赖
2. **统一接口** — 所有指标函数签名: `calc_xxx(df: pd.DataFrame) -> pd.DataFrame`
3. **注册表管理** — `_catalog.py` 是策略真相源，含名称/状态/数据需求/描述
4. **向后兼容** — `indicators_tdx.py` 从 strategy_library 重新导出

## 添加新指标模板

```python
# strategy_library/indicators/_my_new.py
"""
同花顺指标: My New Indicator
严格复现原版通达信公式逻辑。

依赖: strategy_library._core
"""
import numpy as np
import pandas as pd
from strategy_library._core import TDX_EMA, TDX_CROSS, TDX_REF, safe_div

def calc_my_new(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    C = df['close'].values.astype(float)
    # ... 指标计算 ...
    result['my_output'] = ...
    return result
```

然后在 `indicators/__init__.py` 添加导入，在 `_catalog.py` 注册。

## 指标状态含义

| 状态 | 含义 |
|------|------|
| `active` | 完整可用，仅需OHLCV数据 |
| `available` | 代码已实现，需额外数据源（如Tushare moneyflow） |
| `degraded` | 降级模式可用（核心数据不可得但有fallback） |

## 暗盘资金 & 主力持仓数据适配

两个指标当前以**降级模式**运行（用 K线数据估算资金流向）。完整模式需要：
- **Tushare ≥2000 积分** → `moneyflow` 接口 → 写入 `moneyflow_daily` 表
- **东方财富 API（不可用）** — 被防火墙限制

### 降级估算逻辑（`adapters/moneyflow.py`）

```python
from strategy_library.adapters.moneyflow import MoneyflowAdapter
adapter = MoneyflowAdapter('stock_data.db')
mf_df = adapter.get_moneyflow('000988')  # → DataFrame with THS column names
```

适配器三段式：`DB查询 → 降级估算（pct_chg分配买卖）→ 列映射到同花顺公式变量名`

### 升级路径

获得 Tushare ≥2000 积分后：
1. 运行数据拉取脚本填充 `moneyflow_daily` 表
2. `MoneyflowAdapter._from_db()` 自动读取真实数据
3. 两个指标自动切换完整模式（无需修改 `_dark_pool.py` / `_zhuli_holdings.py`）

### 数据库表（已建）

```sql
moneyflow_daily (stock_code TEXT, date TEXT, main_net_amt REAL, lg_buy_amt REAL,
    lg_sell_amt REAL, elg_buy_amt REAL, elg_sell_amt REAL,
    md/sm buy/sell, net_mf_amt REAL, data_source TEXT, PRIMARY KEY (stock_code, date))
```
