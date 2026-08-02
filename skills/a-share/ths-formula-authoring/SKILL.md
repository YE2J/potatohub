---
name: ths-formula-authoring
description: "Author and debug 同花顺/通达信 (TDX) formula language indicators for A-share trading. Covers syntax, color rules, DRAWICON/STICKLINE/DRAWBAND conventions, common pitfalls, and the workflow of converting Python backtest logic into tradeable 副图/选股 formulas."
version: 1.0.0
author: User-defined workflow
license: MIT
metadata:
  hermes:
    tags: [ths, tonghuashun, tdx, formula, indicator, stock]
    related_skills: [review-driven-execution, a-share-backtesting, a-share-factor-ic-evaluation]
---
# 同花顺/通达信 Formula Authoring

## Overview

同花顺 and 通达信 share a common formula language (TDX language) for creating custom indicators. This skill covers:
- Converting Python backtest strategies into TDX formulas
- Syntax rules and color/value conventions
- Common pitfalls that cause compile errors or signal errors
- The standard workflow: backtest → audit → formula → verify

## When to Use

- User asks to convert a backtest strategy into a 同花顺 indicator
- User wants to create a 副图 (sub-chart) or 选股 (stock screener) formula
- User reports a formula that doesn't compile or behaves unexpectedly
- You're reviewing a TDX formula for correctness
- Creating buy/sell signal markers on KDJ, MACD, RSI, or other technical indicators

## TDX Formula Syntax Reference

### Variable Types

```tongdaxin
{Curly braces = comments}
VarName:=expression;      {Intermediate variable (:= not shown on chart)}
VarName:expression;       {Output variable (shown on chart, can color/style)}
```

### Built-in Constants
| Symbol | Meaning |
|--------|---------|
| `OPEN` | Today's open price |
| `CLOSE` | Today's close price |
| `HIGH` | Today's high price |
| `LOW` | Today's low price |
| `VOL` | Today's volume |
| `AMOUNT` | Today's amount |

### Key Functions
| Function | Description |
|----------|-------------|
| `REF(X, N)` | Value of X N periods ago |
| `SMA(X, N, M)` | Smoothed MA: `(M*X + (N-M)*REF)/N` |
| `MA(X, N)` | Simple moving average |
| `EMA(X, N)` | Exponential moving average |
| `HHV(X, N)` | Highest value of X in N periods |
| `LLV(X, N)` | Lowest value of X in N periods |
| `CROSS(A, B)` | 1 when A crosses above B, 0 otherwise |
| `RSI(X, N)` | RSI of X over N periods |
| `STICKLINE(COND, P1, P2, W, E)` | Draw vertical line from P1 to P2 |
| `DRAWICON(COND, PRICE, TYPE)` | Draw icon at position |
| `DRAWBAND(V1, C1, V2, C2)` | Fill band between V1 and V2 |
| `DRAWTEXT(COND, PRICE, TEXT)` | Write text string |
| `NODRAW` | Suppress display of a variable |

### DRAWICON Icon Types

| TYPE | Icon | Color/Meaning | Usage |
|------|------|---------------|-------|
| 1 | 😊 Smiley | Yellow | General positive |
| 2 | 😢 Frown | Green | General negative |
| 3 | ○ Circle | Red | Generic marker |
| **4** | **↑ Up arrow** | **Red/Buy signal** | **Use for buy signals** |
| **5** | **↓ Down arrow** | **Green/Sell signal** | **Use for sell signals** |
| 6 | ✕ Cross | Red | Invalid/reject |
| 7 | ✓ Checkmark | Green | Confirmed |
| 8 | ★ Red star | Red | Important |
| 9 | ★ Yellow star | Yellow | Notable |

⚠️ **Type 4 = Red up arrow (买), Type 5 = Green down arrow (卖)** — these are the standard conventions for buy/sell signals in TDX formulas.

### Color Names

**Valid predefined colors** (no prefix needed):
`COLORBLACK`, `COLORBLUE`, `COLORBROWN`, `COLORCYAN`, `COLORGREEN`, `COLORMAGENTA`, `COLORRED`, `COLORWHITE`, `COLORYELLOW`

**Valid light (LI) colors:**
`COLORLIBLUE` (light blue), `COLORLIGREEN` (light green), `COLORLIRED` (light red)

**❌ NOT valid:** `COLORLIGRAY`, `COLORLIGREY`, `COLORLIGREY` — light gray is NOT a predefined color; use `RGB(192,192,192)` instead.

**Custom colors via RGB:**
```tongdaxin
RGB(R, G, B)   {R,G,B each 0-255, e.g. RGB(160,160,160) for gray}
```

### Variable Naming Rules
- Allowed: Chinese characters, English letters, digits, underscore `_`
- **NOT allowed** in variable names: `()`, `%`, `-`, `.`, spaces
- ❌ `距20日高%` — contains `()` and `%`, old versions may error
- ✅ `距20日高_pct` — safe version
- ✅ `距20日高_pct2` — safe

## KDJ Formula (Standard)

```tongdaxin
N:=9; M1:=3; M2:=3;
RSV:=(CLOSE-LLV(LOW,N))/(HHV(HIGH,N)-LLV(LOW,N))*100;
K:SMA(RSV,M1,1);
D:SMA(K,M2,1);
J:3*K-2*D;
```

**Important:** `SMA(RSV,3,1)` = `(1*RSV + 2*REF(K,1))/3` — this is NOT the same as `MA(RSV,3)` (which is simple average). The `SMA(X,N,M)` with M=1 is the standard KDJ calculation used by 同花顺's built-in KDJ indicator.

KDJ_SMA的计算方式与Python回测完全等价：
```python
k = rsv.ewm(alpha=1/3, adjust=False).mean()  # same as SMA(RSV,3,1)
```

## Common Pitfalls

### ❌ RGB COLORLIGRAY Does Not Exist
**Problem:** `COLORLIGRAY` causes compile error.
**Fix:** Use `RGB(192,192,192)` or `RGB(160,160,160)` instead.

### ❌ Special Characters in Variable Names
**Problem:** Variables like `距20日高%` with `()` or `%` may fail in old 同花顺 versions.
**Fix:** Use underscore + abbreviation: `距20日高_pct`.

### ⚠️ DRAWBAND Compatibility
**Problem:** Very old 同花顺 versions (pre-2018) may not support DRAWBAND.
**Fix:** 
- For maximum compatibility, use STICKLINE as fallback
- Most modern 同花顺 versions (远航版/极速版) support it

### ⚠️ Signal Re-triggering (No Holding-State Memory)
**Problem:** TDX formulas have no state/memory between days. A sell signal fires every time the condition is true, even if already sold. This causes:
- Sell signals that fire repeatedly for days after the first signal
- Buy signals that fire again too soon after selling
**Fix:** Use `CROSS` instead of bare comparisons. Add lookback windows:
```tongdaxin
{Only buy if no sell signal in last 5 days}
买点:=条件 AND NOT ANY(卖点[5]);  {NOT valid TDX syntax}
{Use this instead:}
买点:=条件 AND REF(卖点,1)=0 AND REF(卖点,2)=0;
```

### ⚠️ J > 100 May Never Fire on Strong Stocks
**Problem:** CROSS(100,J) only triggers when J falls back BELOW 100. In strongly trending stocks, J may peak at 85-99 and never reach 100, then turn down.
**Fix:** Add supplementary sell conditions:
```tongdaxin
卖点:=CROSS(100,J) OR (J>80 AND RSI(CLOSE,14)>70 AND J<REF(J,1));
```

### ⚠️ TDX Has No Position-Level Concept
**Problem:** 5% stop-loss is a per-position rule, but TDX formulas have no concept of entry price or position state. You cannot encode "sell when this position loses 5%" in a 副图 formula.
**Fix:** The formula can only show entry/exit signals; stop-loss is an execution rule the trader follows manually or via conditional order.

## Workflow: Backtest → Formula

### Step 1: Validate Strategy in Python
Use `a-share-backtesting` or your own backtest framework to:
- Run full history simulation
- Verify signal conditions produce reasonable signal frequency
- Confirm win rate, max drawdown, Sharpe ratio

### Step 2: 3-Agent Audit the Code
Before converting to TDX, review the Python backtest with 3 agents:
1. **Signal logic** — KDJ/RSI/MACD calculations match TDX behavior
2. **Data correctness** — no future leakage, correct date handling
3. **Realism** — stop loss (5% not 0.01%), trading costs, slippage, limit_up/limit_down checks

### Step 3: Convert to TDX Formula
- Map Python conditions to TDX functions
- Simplify: TDX has no `if/else`, loops, or external data
- All conditions must be vector operations on current/ref/prev values
- Add proper color coding and visual elements

### Step 4: 3-Agent Audit the Formula
Use `review-driven-execution` with specific TDX checkpoints:
1. **Syntax agent:** Check color names, variable names, function signatures
2. **Logic agent:** Verify conditions match Python backtest exactly (thresholds, AND/OR semantics)
3. **Practicality agent:** Signal frequency, visual crowding, real-world tradability

### Step 5: Save to File
Save to `~/my_quant_system/同花顺公式/<name>.txt` with:
- Complete header comments explaining strategy logic and parameters
- Backtest results (return, max drawdown, win rate) for reference
- Usage instructions

## Visual Design Guidelines

### Signal Markers
| Element | Buy | Sell |
|---------|-----|------|
| Arrow | DRAWICON(买点, -5, 4) — red up arrow | DRAWICON(卖点, 105, 5) — green down arrow |
| Bar | STICKLINE(买点, 0, J, 2, 0), COLORRED | STICKLINE(卖点, 100, J, 2, 0), COLORGREEN |
| Text (optional) | DRAWTEXT(买点, J*0.5, '买'), COLORRED | DRAWTEXT(卖点, 105, '卖'), COLORGREEN |

**Best practice:** Use DRAWICON + STICKLINE only; skip DRAWTEXT to avoid visual crowding.

### Color Choices
- A-share convention: **Red** = buy/up, **Green** = sell/down (same as candle colors in 同花顺)
- Reference lines: `COLORWHITE, DOTLINE` for neutral levels (0, 100)
- Bands: Use muted RGB values, not 100% saturation
  - Oversold (J < 0): `DRAWBAND(0, RGB(25,100,25), -20, RGB(8,30,8))` — muted green
  - Overbought (J > 100): `DRAWBAND(100, RGB(100,25,25), 120, RGB(30,8,8))` — muted red

### Arrow Position
- Buy arrow: Anchor near -5 (below the oversold area) — avoids overlapping J line
- Sell arrow: Anchor at 105 (above the overbought area) — fixed position, doesn't drift with J

## KDJ超跌反弹 Formula Template

See `references/kdj-fusion-strategy.md` for the full v3 formula derived from the fusion strategy backtest, with exact parameters (距20日高点>-10%, VOL > 10日均量×80%, 5%止损, 25%×3只仓位).

## Verification Checklist
- [ ] All color names are valid (check: no COLORLIGRAY, no invalid COLOLIxxx)
- [ ] Variable names avoid `()`, `%`, `-`, spaces
- [ ] Buy/sell conditions match the Python backtest thresholds exactly
- [ ] J值>100 or RSI>80 logic uses CROSS or direct comparison correctly
- [ ] Signal frequency is reasonable (not 50+ signals/year on average stock)
- [ ] DRAWBAND anchors in valid range (not drawn outside chart bounds)
- [ ] DRAWICON uses correct icon types (4=buy ↑, 5=sell ↓)
- [ ] File saved to `~/my_quant_system/同花顺公式/<name>.txt`
- [ ] Header comments document strategy params, backtest results, and usage
