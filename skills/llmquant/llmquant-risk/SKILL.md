---
name: llmquant-risk
description: Router skill for LLMQuant risk workflows. Use when the user needs fear score, VIX status, hedge advisor, or research quality health checks.
input_data_source: LLMQuant Data
category: risk
---

# LLMQuant Risk

This category routes risk assessment workflows for regime, hedging, panic scoring, and research quality checks.

## Routing Rules

1. Identify the portfolio, benchmarks, hedging instruments, horizon, and risk tolerance.
2. Select the closest workflow below.
3. Open only that workflow and any referenced local resources.
4. Use LLMQuant Data for prices, volatility, credit, macro, options, and portfolio context.
5. Report timestamps, data windows, stale notices, missing inputs, and model assumptions.

## Workflow Index

| User intent | Workflow |
|---|---|
| Score market fear across volatility, credit, macro, and options signals. | [`workflows/fear-score.md`](workflows/fear-score.md) |
| Assess VIX level, term structure, regime, and hedge implications. | [`workflows/vix-status.md`](workflows/vix-status.md) |
| Review portfolio exposures and recommend hedge overlays. | [`workflows/hedge-advisor.md`](workflows/hedge-advisor.md) |
| Audit research quality: evidence sourcing, timeliness, and logical soundness. | [`workflows/research-health-check.md`](workflows/research-health-check.md) |

## LLMQuant Data Contract

Prefer LLMQuant Data when available. The workflows may need these data capabilities:
- Retrieve volatility indices, term structure, and regime signals.
- Retrieve risk factor exposures, correlation matrices, drawdowns, and stress-scenario context.
- Retrieve credit spreads, macro indicators, risk parity signals, and hedging instrument pricing.
- Retrieve research evidence metadata, data timestamps, and sourcing provenance.

Fallback:
- If risk data is unavailable, name the missing input and limit conclusions to available evidence.
- Do not estimate risk scores, hedge ratios, or fear levels without input data.