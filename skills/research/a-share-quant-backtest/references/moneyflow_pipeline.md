# 东方财富资金流数据管线

## API 端点

```
https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get
```

**参数**：
- `lmt=3` — 返回最新 N 个交易日（增量更新用 3，历史回填用 50）
- `klt=1` — K线类型（1=日线）
- `secid=0.{code}` — 深市（0/3开头），`secid=1.{code}` — 沪市（6开头）
- `fields2=f51,f52,f53,f54,f55,f56,f61,f62` — 返回字段
- `fmt=json` — **必须加上**，触发原始 JSON 返回而非摘要

## 字段映射

| 东财字段 | 含义 | DB列 |
|---------|------|------|
| f51 | 日期 (YYYY-MM-DD) | date |
| f52 | 主力净流入（元）| main_net_amt |
| f53 | 超大单净流入（元）| → elg_buy/elg_sell |
| f54 | 大单净流入（元）| → lg_buy/lg_sell |
| f55 | 中单净流入（元）| → md_buy/md_sell |
| f56 | 小单净流入（元）| → sm_buy/sm_sell |
| f61 | 主力净流入占比（%） | — |
| f62 | 收盘价 | — |

**注意**：东财只提供净流入值（正=净买，负=净卖），无法分离买入/卖出。存储时：
- buy_amt = max(net_value, 0)
- sell_amt = abs(min(net_value, 0))

## 网络限制与替代方案

### 问题
本地 curl/Python urllib 能完成 TLS 握手（TCP 443 OK），但服务器返回 **空回复**（curl exit code 52）。
Hermes 中继网络可正常访问。

### 替代方案
- ✅ **Hermes `web_extract`**：可正常访问。必须 `lmt ≤ 50` + `fmt=json` → 原始 JSON。`lmt > 50` → LLM 摘要，丢失原始数据。
- ✅ **Hermes Cron Job**：通过 Agent 的 `web_extract` 增量拉取，Cron ID `209c43908019`，每日 18:30。
- ❌ **本地 curl/Python/akshare**：均不可用（SSL 正常但服务器拒绝响应）。
- ❌ **Tushare `moneyflow`/`moneyflow_dc`/`moneyflow_ths`**：需 ≥2000 积分，当前无权限。
- ❌ **新浪财经 API**：`Service not found`。

## 已覆盖的 Cron Job

| Job ID | 调度 | 内容 |
|--------|------|------|
| 209c43908019 | 每日 18:30 | 拉取 STOCKS_V4 全部 99 只股票最新 3 日资金流 |

## 表结构

```sql
CREATE TABLE moneyflow_daily (
    stock_code TEXT, date TEXT,
    main_net_amt REAL,
    lg_buy_amt REAL, lg_sell_amt REAL,
    md_buy_amt REAL, md_sell_amt REAL,
    sm_buy_amt REAL, sm_sell_amt REAL,
    elg_buy_amt REAL, elg_sell_amt REAL,
    net_mf_amt REAL,
    data_source TEXT DEFAULT 'eastmoney',
    PRIMARY KEY (stock_code, date)
);
```
