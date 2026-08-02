# KDJ超跌反弹 Fusion Strategy (v3)

## Origin
Derived from backtest_v5_fusion.py, 3-agent code review, and 3-agent TDX formula review.
Session: 2026-07-06, ~727 lines of Python + ~80 lines of TDX formula.

## Strategy Parameters

### Buy Conditions (ALL must be true)
| Condition | TDX Code | Value |
|-----------|----------|-------|
| KDJ_J < 0 for 2 consecutive days | `J<0 AND REF(J,1)<0` | Confirmation filter |
| Drawdown from 20d high > 10% | `(CLOSE-HHV(HIGH,20))/HHV(HIGH,20)*100 < -10` | -10% threshold |
| Volume recovery | `VOL > MA(VOL,10) * 0.8` | >80% of 10d avg vol |

### Sell Conditions (ANY triggers sell)
| Condition | TDX Code | Value |
|-----------|----------|-------|
| KDJ_J > 100 | `J > 100` | Extreme overbought |
| RSI(14) > 80 | `RSI(CLOSE,14) > 80` | RSI overbought confirmation |

### Risk Management
| Parameter | Value | Note |
|-----------|-------|------|
| Stop loss | 5% | Per-position, manual execution |
| Max positions | 3 | Hard limit |
| Per position capital | 25% | Dynamic: `cash*0.25` or `initial*0.25` |
| Reserve cash | 25% | For new signals in drawdown |

## Backtest Results (2025-01 to 2026-07)

### 99只自选股
- Total return: **+141.4%**
- Max drawdown: **4.04%**
- Win rate: **76.5%**
- Avg win / avg loss: +18.8% / -2.7%

### 20只AI案例股
- Total return: **+134.3%**
- Max drawdown: **9.36%**
- Win rate: **64.4%**
- Vs buy-hold (+380%): strategies naturally underperform on cherry-picked winners

## TDX Formula Bugs Found During 3-Agent Review

### Bug 1: COLORLIGRAY is not a valid TDX color
- Line: `距20日高%:(...), COLORLIGRAY, NODRAW`
- Fix: Change to `RGB(160,160,160)` or `RGB(192,192,192)`
- Why: TDX only defines COLORLIBLUE, COLORLIGREEN, COLORLIRED; not COLORLIGRAY

### Bug 2: Special characters in variable names
- Line: `距20日高%:` — contains `()` and `%`
- Fix: Rename to `距20日高_pct`
- Why: Old 同花顺 versions choke on non-standard variable name characters

### Bug 3: DRAWBAND may not work in old versions
- Fix: Test in actual 同花顺; versions from 2018+ support it

## Icon References for Signal Drawing
| Icon | Type Code | Usage |
|------|-----------|-------|
| ↑ Red up arrow | `DRAWICON(买点, -5, 4)` | Buy signal |
| ↓ Green down arrow | `DRAWICON(卖点, 105, 5)` | Sell signal |

## File Location
`~/my_quant_system/同花顺公式/KDJ超跌反弹_副图.txt`
