# Tencent Stock API Reference

Reliable fallback for A-share historical K-line data when akshare (EastMoney) is unreachable from non-China IPs.

## Endpoint

```
GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
```

## Parameters

| Param | Value | Description |
|-------|-------|-------------|
| `param` | `{prefix}{code},day,{start},{end},{count},qfq` | Combined parameter string |

### Prefix Rules
- `sz` — Shenzhen stocks (codes starting with `0`, `3`)
- `sh` — Shanghai stocks (codes starting with `6`)

### Date Format
- Input: `YYYY-MM-DD` (hyphenated)
- Output: same format

## Example

```
GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000001,day,2020-01-01,2025-01-01,500,qfq
```

## Response Structure

```json
{
  "code": 0,
  "data": {
    "sz000001": {
      "qfqday": [
        ["2022-12-09", "11.192", "11.492", "11.542", "11.142", "1615832.000"],
        ...
      ],
      "qt": "...",
      "mx_price": "...",
      "prec": "...",
      "version": "..."
    }
  }
}
```

### K-line Entry Format
Index 0–5 are always present. Index 6 is optional and may be a dict.

| Index | Field | Type | Notes |
|-------|-------|------|-------|
| 0 | date | string | "YYYY-MM-DD" |
| 1 | open | string | Adjusted (qfq) price |
| 2 | close | string | Adjusted (qfq) price |
| 3 | high | string | Adjusted (qfq) price |
| 4 | low | string | Adjusted (qfq) price |
| 5 | volume | string | In shares |
| 6 | dividend_info | dict (optional) | Ex-rights/dividend data; MUST be ignored |

### Dividend Dict (Field [6], When Present)
```json
{
  "nd": "2022",
  "fh_sh": "2.85",
  "djr": "2023-06-13",
  "cqr": "2023-06-14",
  "FHcontent": "10派2.85元"
}
```

## Python Parser

```python
rows = []
for kline in klines:
    rows.append({
        "date": str(kline[0]).replace("-", ""),
        "open": float(kline[1]),
        "close": float(kline[2]),
        "high": float(kline[3]),
        "low": float(kline[4]),
        "volume": float(kline[5]),
        # kline[6] if exists is dividend dict — skip
    })
df = pd.DataFrame(rows)
```

## Limits
- **Max 500 entries** per call. For longer history, make multiple calls with offset date ranges.
- **Rate limiting**: seems generous; no throttling observed.
- **Data range**: returns forward-adjusted (qfq) prices going back ~2 years from today (depends on stock).

## Comparison with akshare

| Aspect | akshare (EastMoney) | Tencent API |
|--------|-------------------|-------------|
| Columns | Full (11 cols incl. amplitude, turnover, pct_change) | Minimal (6 cols: OHLCV) |
| Availability | Fails from non-China IPs | Works globally |
| Dividend adjustment | qfq parameter | qfq in param string |
| Reliability | Occasional timeout/connection reset | Stable, fast |
