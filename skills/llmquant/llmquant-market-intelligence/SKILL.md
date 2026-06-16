---
name: llmquant-market-intelligence
description: Router skill for LLMQuant market intelligence workflows. Use when the user needs market sentiment, macro view, or event probability signals.
input_data_source: LLMQuant Data
category: market-intelligence
---

# LLMQuant Market Intelligence

This category routes reusable market utilities and signal views.

## Routing Rules

1. Identify the asset, geography, horizon, and requested signal.
2. Select the closest workflow below.
3. Open only that workflow and any referenced local resources.
4. Use LLMQuant Data for price, macro, event, sentiment, and research data.
5. Report timestamps, observation windows, stale notices, and missing inputs.

## Workflow Index

| User intent | Workflow |
|---|---|
| View macro regime overview with growth, inflation, policy, and liquidity signals. | [`workflows/macro-view.md`](workflows/macro-view.md) |
| Assess cross-asset market sentiment from technical, options, and flow signals. | [`workflows/market-sentiment.md`](workflows/market-sentiment.md) |
| View aggregated event probability signals from prediction markets and options. | [`workflows/event-probability-signals.md`](workflows/event-probability-signals.md) |

## LLMQuant Data Contract

Prefer LLMQuant Data when available. The workflows may need these data capabilities:
- Retrieve macro indicator snapshots, histories, and release calendars.
- Retrieve market sentiment data, option-implied signals, and flow signals.
- Retrieve prediction market event probabilities and option-implied event pricing.
- Retrieve prices, volatility, credit spreads, and cross-asset context.

Fallback:
- If a signal input is unavailable, name the missing data and continue with available evidence.
- Do not infer sentiment, regime, or probability without timestamped market data.