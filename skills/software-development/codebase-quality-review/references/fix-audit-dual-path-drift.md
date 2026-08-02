# Fix Audit: Dual-Path & Sibling Drift Findings

Reference from a production fix-audit session (2026-07-02). The user had 9 fixes implemented across a quant system; verification found 2 that were only partially applied. These patterns recur in any system with multiple code paths and multiple deployment copies.

## Setup

System: `~/my_quant_system` (A-share stock screening + backtesting)
Task: Verify 9 specific fixes were correctly implemented
Scope: 4 Python files + 2 shell scripts + 1 cron config

## Finding 1: Dual-Path ST/Suspension Exclusion Gap

**Context:** The screening system has two code paths:
- **Table path** (`screen_from_factors`) — queries precomputed `daily_factors` table. No volume/close info available.
- **Fallback path** (`screen_fallback`) — iterates each stock, computes from K-line + moneyflow. Has volume/close.

**The fix:** Exclude ST stocks and suspended stocks.

**Verified:**
- `filter_st_stocks()` → called from `print_results()` and `main()` → both paths ✅
- `filter_suspended()` → the code at `screen_v4.py:171-178` was a **stub**:
  ```python
  def filter_suspended(df: pd.DataFrame) -> pd.DataFrame:
      """过滤掉停牌股票 (volume=0 AND close≈pre_close)"""
      # 仅在 screen_from_factors 模式有完整数据时生效
      if 'zhuli_holding' not in df.columns:
          return df          # ← EXITS HERE: zhuli_holding NOT in table-path DataFrame
      # 检查停牌：需要结合K线判断，此处简单标记
      # 实际停牌排除在回退模式中已有 volume/close 检查
      return df              # ← ALSO JUST RETURNS DF
  ```
- Fallback path has volume+close check at lines 109-114 ✅

**Root cause:** The function was written with good intentions but the table-path DataFrame doesn't contain the columns needed for volume/close detection, so the function silently passes through. The fix was never completed for the table path.

**Lesson:** When a system has two execution paths for the same task, verify EVERY fix on BOTH paths. The same `filter_st_stocks(stub_end)` bug would look equivalent on a line-count metric.

## Finding 2: Sibling Script Drift (Cron Failure Notification)

**Context:** Cron runs `daily_factor_update.sh`. Two copies exist:

| Location | Size | Has `$?` check? | Has `FACTOR_UPDATE_FAILED`? |
|----------|------|------------------|----------------------------|
| `my_quant_system/scripts/daily_factor_update.sh` | 627 bytes | ✅ | ✅ |
| `~/.hermes/scripts/daily_factor_update.sh` | 461 bytes | ❌ | ❌ (prints `[DONE]` even on failure) |

**The cron job** (`~/.hermes/cron/jobs.json`) references `"script": "daily_factor_update.sh"` — Hermes resolves short names to `~/.hermes/scripts/`, so the live copy is the **461-byte version without error handling**.

**Root cause:** The fix was only applied to the project source copy. The cron-deployed copy (which is the one that actually runs) was never updated.

**Lesson:** When finding scripts referenced by cron:
1. `hermes cron list` or `cat ~/.hermes/cron/jobs.json`
2. For each script field, determine which path Hermes resolves to (usually `~/.hermes/scripts/<name>`)
3. `ls -la` both the project copy and the `.hermes/` copy
4. If they differ (different sizes), the `.hermes/` copy is the one cron actually calls — verify it has the fix

## Finding 3: Stub Function Detection (surface check)

`filter_suspended()` passed all standard code review checks:
- ✅ Has a docstring explaining what it does
- ✅ Has type hints
- ✅ Has `return df` at the end (makes callers work)
- ✅ Is called in the right places (`print_results` calls it)

But the body does **no actual filtering** — it's a no-op pass-through.

**Detection trick:** Look at functions that end with `return df` or `return dframe` and trace back through the body: are there any intermediate assignments that filter/modify the dataframe? If every code path just returns the input, it's a stub.

## Fix Verification Checklist

Use this when auditing bug fixes across a multi-path system:

```
[ ] 1. Identify all code paths for the task (table/fast, compute/slow, fallback)
[ ] 2. For each file changed in the fix, verify the change exists
[ ] 3. For each code path, trace the FIX not just the FILE:
     - Does path A have the logic? (SQL WHERE, pandas filter)
     - Does path B have the logic? (inline check, function call)
[ ] 4. Check sibling files: are there the-same-name copies elsewhere?
[ ] 5. Check cron: which copy does cron actually call?
[ ] 6. Run an import/syntax check on every changed file
[ ] 7. Run the actual code path with a known input to verify the fix
[ ] 8. Check cron schedule config (in Hermes cron jobs.json)
[ ] 9. Verify cron timeout: 19:00 cron for data that arrives at 18:45 → 15 min buffer is tight
```
