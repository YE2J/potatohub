---
name: llmquant-strategies
description: "Router skill for LLMQuant strategy playbooks. Use when the user needs hedge fund or portfolio manager strategy workflows: equity long/short, long-biased, event-driven, macro, quant, or multi-strategy."
input_data_source: LLMQuant Data
category: strategies
---

# LLMQuant Strategies

This category routes hedge-fund and portfolio-manager strategy playbooks.

## Routing Rules

1. Identify the strategy type, universe, benchmark, constraints, and objective.
2. Select the closest workflow below.
3. Open only that workflow and any referenced local resources.
4. Use LLMQuant Data for prices, filings, fundamentals, ownership, macro, risk, and portfolio context.
5. Report data periods, filing dates, observation windows, stale notices, and missing inputs.

## Workflow Index

| User intent | Workflow |
|---|---|
| Equity long/short: fundamental research, catalyst timing, and pair/multi-pair construction. | [`workflows/equity-long-short.md`](workflows/equity-long-short.md) |
| Long-biased: quality compounding, concentrated core, and drawdown management. | [`workflows/long-biased.md`](workflows/long-biased.md) |
| Event-driven: M&A, special situations, catalysts, and risk-arbitrage. | [`workflows/event-driven.md`](workflows/event-driven.md) |
| Macro: top-down regime, cross-asset allocation and tail-risk overlay. | [`workflows/macro.md`](workflows/macro.md) |
| Quant: systematic factor, statistical arbitrage, and signal-driven strategies. | [`workflows/quant.md`](workflows/quant.md) |
| Multi-strategy: capital allocation across sleeves with risk aggregation. | [`workflows/multi-strategy.md`](workflows/multi-strategy.md) |

## LLMQuant Data Contract

Prefer LLMQuant Data when available. The workflows may need these data capabilities:
- Retrieve equity prices, fundamentals, filings, ownership, and event calendars.
- Retrieve factor exposures, risk models, correlation matrices, and portfolio analytics.
- Retrieve macro indicators, central-bank policy, rates, FX, credit, and commodity context.
- Retrieve options, volatility, and hedging instrument pricing.

Fallback:
- If strategy-specific data is unavailable, name the missing inputs and continue with available evidence.
- Do not simulate strategy performance without timestamped pricing and risk data.