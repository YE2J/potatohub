# 东财 push2his → 问财 OpenAPI 资金流 Fallback 参考

## 场景

Hermes cron job `209c43908019` "每日资金流更新"，每日拉取 99 只自选股资金流数据写入 SQLite。东财 push2his 可能因服务中断返回 502，需要降级到问财 OpenAPI。

## 降级触发条件

```
如果以下任一条件满足，立即停止东财请求并切换问财：
- 单批5个URL中 ≥3个返回 502/403/connection error/空JSON
- 前3批（12只股票）中 ≥8只无数据
- 任何 web_extract 返回内容包含 "502 Bad Gateway"
```

## 东财 push2his（主流程）

```
URL: https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get
Params: lmt=3, klt=1, secid=0.{code} (深市) / secid=1.{code} (沪市)
Fields: fields1=f1,f2,f3,f7, fields2=f51,f52,f53,f54,f55,f56,f61,f62

映射: f52=主力净流入, f53=超大单净流入, f54=大单净流入, f55=中单净流入, f56=小单净流入
```

## 问财 OpenAPI（降级）

### 认证

```
API_KEY=$(grep IWENCAI_API_KEY ~/.hermes/.env | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs)
```

### 批量查询（每批 ≤15 只）

```bash
RESP=$(curl -s -X POST https://openapi.iwencai.com/v1/query2data \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Claw-Skill-Id: hithink-market-query" \
  -H "X-Claw-Skill-Version: 1.0.0" \
  -H "X-Claw-Trace-Id: $(openssl rand -hex 32)" \
  -d '{"query":"CODE1,CODE2,...,CODE15 超大单净流入 大单净流入 中单净流入 小单净流入","page":"1","limit":"20"}')
```

### 响应格式

```json
{
  "datas": [
    {
      "股票代码": "600519.SH",
      "超大单净流入": 1.23e8,
      "大单净流入": -5.6e7,
      "中单净流入": -4.2e7,
      "小单净流入": -2.5e7
    }
  ]
}
```

字段均为净额（正=流入，负=流出）。

### 解析 & 写入（jq + bc + sqlite3）

```bash
TODAY=$(date +%Y%m%d)

echo "$RESP" | jq -r '.datas[] | [
  (.超大单净流入 // "0"), (.大单净流入 // "0"),
  (.中单净流入 // "0"), (.小单净流入 // "0"),
  (.股票代码 // "")
] | @tsv' | while IFS=$'\t' read elg lg md sm raw_code; do
  code=$(echo "$raw_code" | sed 's/\.SZ//;s/\.SH//;s/\.BJ//')
  [ -z "$code" ] && continue

  # 主力净流入 = 超大单 + 大单
  main_net=$(echo "$elg + $lg" | bc -l)

  # 买卖拆分：正值→买入，负值取绝对值→卖出
  elg_buy=$(echo "if($elg > 0) $elg else 0" | bc -l)
  elg_sell=$(echo "if($elg < 0) -1 * $elg else 0" | bc -l)
  lg_buy=$(echo "if($lg > 0) $lg else 0" | bc -l)
  lg_sell=$(echo "if($lg < 0) -1 * $lg else 0" | bc -l)
  md_buy=$(echo "if($md > 0) $md else 0" | bc -l)
  md_sell=$(echo "if($md < 0) -1 * $md else 0" | bc -l)
  sm_buy=$(echo "if($sm > 0) $sm else 0" | bc -l)
  sm_sell=$(echo "if($sm < 0) -1 * $sm else 0" | bc -l)

  # 总净流入 = 四类合计（应为 ~0）
  net_mf=$(echo "$elg + $lg + $md + $sm" | bc -l)

  sqlite3 ~/my_quant_system/stock_data.db "INSERT OR REPLACE INTO moneyflow_daily
    (stock_code, date, main_net_amt, lg_buy_amt, lg_sell_amt,
     md_buy_amt, md_sell_amt, sm_buy_amt, sm_sell_amt,
     elg_buy_amt, elg_sell_amt, net_mf_amt, data_source)
    VALUES ('$code', '$TODAY', $main_net, $lg_buy, $lg_sell,
            $md_buy, $md_sell, $sm_buy, $sm_sell,
            $elg_buy, $elg_sell, $net_mf, 'iwencai');"
done
```

## SQLite 表结构

```sql
CREATE TABLE moneyflow_daily (
    stock_code TEXT, date TEXT,
    main_net_amt REAL, lg_buy_amt REAL, lg_sell_amt REAL,
    md_buy_amt REAL, md_sell_amt REAL, sm_buy_amt REAL, sm_sell_amt REAL,
    elg_buy_amt REAL, elg_sell_amt REAL,
    net_mf_amt REAL, data_source TEXT,
    PRIMARY KEY (stock_code, date)
);
```

## 字段映射对照

| SQLite 列 | 东财 push2his | 问财 OpenAPI |
|-----------|-------------|-------------|
| main_net_amt | f52 | elg + lg |
| elg_buy_amt | max(f53,0) | max(elg,0) |
| elg_sell_amt | abs(min(f53,0)) | abs(min(elg,0)) |
| lg_buy_amt | max(f54,0) | max(lg,0) |
| lg_sell_amt | abs(min(f54,0)) | abs(min(lg,0)) |
| md_buy_amt | max(f55,0) | max(md,0) |
| md_sell_amt | abs(min(f55,0)) | abs(min(md,0)) |
| sm_buy_amt | max(f56,0) | max(sm,0) |
| sm_sell_amt | abs(min(f56,0)) | abs(min(sm,0)) |
| net_mf_amt | f52+f53+f54 | elg+lg+md+sm |
| data_source | 'eastmoney' | 'iwencai' |

## 数据口径差异

- **东财主力** = f52（API 直接返回的主力净流入字段）
- **问财主力** = 超大单 + 大单（问财无单独主力字段，需合成）
- 降级数据 `data_source='iwencai'` 标记来源，下游可按需过滤
