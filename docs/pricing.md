# Model Pricing

## Jev / TypeSafe AI

Pricing snapshot date: **2026-09-25**.

Official TypeSafe pricing:

- input: **$42 / 1 billion tokens** = **$0.042 / 1 million input tokens**;
- output: **$0 / 1 million tokens** (official launch material describes output as free / too cheap to meter).

Sources:

- https://typesafe.ai/
- https://typesafe.ai/blog/introducing-system-one-models-and-jev

Canonical calculation:

```text
jev_cost_usd =
  input_tokens  * 0.042 / 1_000_000
  +
  output_tokens * 0.000 / 1_000_000
```

Example from the File Discovery V1 convergence benchmark:

```text
input_tokens = 212,584
cost = 212,584 * 0.042 / 1,000,000
     = $0.008928528
```

The implementation is versioned in `src/model_pricing.py` and the source snapshot is pinned in `fixtures/pricing/typesafe-jev-2026-09-25.json`.

Every File Discovery V1 result records the pricing snapshot and estimated USD cost under `usage.pricing`.

## System2 cost

The System2 comparison does not infer cost from a hard-coded model alias. Claude Code's run manifest/provider model usage is treated as the primary cost record when available.

This matters because model choice, prompt caching, provider routing, and future list-price changes can alter effective cost. The workflow records the explicit System2 model alongside provider-reported cost.