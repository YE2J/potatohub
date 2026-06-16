# Tencent Stock API Reference

Base URL: `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get`

## Request Format

```
GET ?param={prefix}{code},day,{start_date},{end_date},{max_count},qfq
```

### Parameters

| Field | Description |
|-------|-------------|
| `prefix` | `sz` for Shenzhen / `sh` for Shanghai / `sh` for 5xxx funds |
| `code` | 6-digit stock code |
| `day` | Period — always `day` for daily kline |
| `start_date` | YYYY-MM-DD |
| `end_date` | YYYY-MM-DD |
| `max_count` | Max records (capped at ~500 by server) |
| `qfq` | `qfq` = 前复权 (forward-adjusted), omit = unadjusted |

### Examples

```
# 平安银行 (SZ)
?param=sz000001,day,2025-12-14,2026-06-13,500,qfq

# 贵州茅台 (SH)  
?param=sh600519,day,2025-12-14,2026-06-13,500,qfq
```

## Response Format

```json
{
  "code": 0,
  "msg": "",
  "data": {
    "sz000001": {
      "qfqday": [
        ["2025-12-15", "10.850", "10.720", "10.920", "10.690", "5846256.000"],
        ...
      ],
      "qt": "...",
      "mx_price": "...",
      "version": "..."
    }
  }
}
```

### Kline Entry Format

Each entry in `qfqday` is an array with up to 7 elements:

```
[date, open, close, high, low, volume, (optional_dividend_dict)]
```

| Index | Field | Type | Notes |
|-------|-------|------|-------|
| 0 | date | string | YYYY-MM-DD |
| 1 | open | string | 开盘价 |
| 2 | close | string | 收盘价 |
| 3 | high | string | 最高价 |
| 4 | low | string | 最低价 |
| 5 | volume | string | 成交量 |
| 6 | dividend | dict | ⚠️ Optional — dividend/ex-right info |

### ⚠️ Critical: 7th Field

Some entries have a 7th field that is a **dict** (not a string):

```python
{'nd': '2024', 'fh_sh': '2.46', 'djr': '2024-10-09',
 'cqr': '2024-10-10', 'FHcontent': '10派2.46元'}
```

**Always take only `kline[0..5]`** and ignore `kline[6]`. Attempting `float(kline[6])` will raise `TypeError: float() argument must be a string or a number, not 'dict'`.

## Known Limitations

1. **Max ~500 records per request**: If you need more data, paginate by date range.
2. **Start/end dates are approximate**: The API may return fewer records than the date range suggests. Filter client-side.
3. **Rate limiting**: Tested reliably at ~8 requests/second with 0.12s delay. No hard cap observed but be respectful.
4. **No authentication needed**: Public API, no token required.
5. **Only daily kline**: For minute/5min/15min kline, use different endpoints or data sources.

## Comparison with akshare

| Aspect | akshare (EastMoney) | Tencent API |
|--------|-------------------|-------------|
| Accessible from abroad | ❌ Often blocked | ✅ Works globally |
| Data columns | Full (including 换手率, 振幅) | Basic OHLCV only |
| Speed | ~7s (3 retries × 2s + 1s) | ~1s direct |
| Rate limit | Unknown | ~8 req/s safe |
| Code requirement | pip install akshare | None (plain requests) |
