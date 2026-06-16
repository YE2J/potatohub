# Probability vs Options Pricing

## Use When

Use this workflow when the user asks to compare prediction-market odds with options-implied, asset-implied, or event-implied probabilities.

## LLMQuant Data Needed

Required:
- event contracts, settlement criteria, market odds, order-book depth, volume, fees, and close dates from prediction-market tools.
- options-implied probabilities, volatility, skew, and event-window pricing.
- related asset prices (equity, FX, rates, credit, commodities, crypto) for asset-implied probability checks.
- macro, news, and issuer context when relevant.

Freshness:
- Report market timestamp, option quote timestamp, settlement deadline, and fee structure.

Fallback:
- If options-implied or asset-implied tools are unavailable, produce only prediction-market odds with a margin-of-safety explanation.

## Workflow

1. Define the event, venues, contracts, settlement rules, and deadline.
2. Pull prediction-market odds from each available venue.
3. Pull options-implied or asset-implied probabilities when available.
4. Compare pricing across venues and structures, adjusting for liquidity, fees, and settlement risk.
5. Flag material differences with a margin-of-safety and explain which is more reliable and why.

## Output Format

1. **Probability View**
2. **Cross-Venue Comparison**
3. **Options / Asset Implied**
4. **Arbitrage Or Pricing Gap**
5. **Settlement / Fee Notes**
6. **Data Used**

## Guardrails

- Do not claim arbitrage without accounting for fees, liquidity, slippage, settlement timing, and counterparty risk.
- Do not compare across venues with different settlement methods without noting the difference.
- Do not infer binary probability from continuous options structures without explanation.