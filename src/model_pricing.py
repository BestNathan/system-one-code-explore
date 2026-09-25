"""Versioned model pricing helpers used by benchmark artifacts."""
from __future__ import annotations

JEV_PRICING_SNAPSHOT = {
    "provider": "TypeSafe AI",
    "model_family": "Jev",
    "snapshot_date": "2026-09-25",
    "input_usd_per_million": 0.042,
    "output_usd_per_million": 0.0,
    "sources": [
        "https://typesafe.ai/",
        "https://typesafe.ai/blog/introducing-system-one-models-and-jev",
    ],
}


def token_cost_usd(
    input_tokens,
    output_tokens,
    *,
    input_usd_per_million,
    output_usd_per_million,
):
    return (
        float(input_tokens or 0) * float(input_usd_per_million)
        + float(output_tokens or 0) * float(output_usd_per_million)
    ) / 1_000_000.0


def jev_cost_usd(input_tokens, output_tokens=0):
    return token_cost_usd(
        input_tokens,
        output_tokens,
        input_usd_per_million=(
            JEV_PRICING_SNAPSHOT["input_usd_per_million"]
        ),
        output_usd_per_million=(
            JEV_PRICING_SNAPSHOT["output_usd_per_million"]
        ),
    )


def jev_cost_record(input_tokens, output_tokens=0):
    return {
        "provider": JEV_PRICING_SNAPSHOT["provider"],
        "model_family": JEV_PRICING_SNAPSHOT["model_family"],
        "pricing_snapshot_date": (
            JEV_PRICING_SNAPSHOT["snapshot_date"]
        ),
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "input_usd_per_million": (
            JEV_PRICING_SNAPSHOT["input_usd_per_million"]
        ),
        "output_usd_per_million": (
            JEV_PRICING_SNAPSHOT["output_usd_per_million"]
        ),
        "estimated_cost_usd": round(
            jev_cost_usd(input_tokens, output_tokens),
            12,
        ),
        "sources": list(JEV_PRICING_SNAPSHOT["sources"]),
    }


DEEPSEEK_FLASH_PRICING_SNAPSHOT = {
    "provider": "DeepSeek",
    "model": "deepseek-flash",
    "snapshot_date": "2026-09-25",
    "currency": "USD",
    "peak": {
        "input_cache_hit_usd_per_million": 0.006,
        "input_cache_miss_usd_per_million": 0.30,
        "output_usd_per_million": 1.20,
    },
    "off_peak": {
        "input_cache_hit_usd_per_million": 0.003,
        "input_cache_miss_usd_per_million": 0.15,
        "output_usd_per_million": 0.60,
    },
    "peak_utc": [
        {"start": "01:00", "end": "04:00"},
        {"start": "06:00", "end": "10:00"},
    ],
    "peak_weekdays": "Monday-Friday",
    "source": "https://api-docs.deepseek.com/quick_start/pricing/",
}


def deepseek_flash_cost_usd(
    input_tokens,
    cache_read_input_tokens,
    output_tokens,
    *,
    peak,
):
    tier = DEEPSEEK_FLASH_PRICING_SNAPSHOT[
        "peak" if peak else "off_peak"
    ]
    return (
        float(input_tokens or 0)
        * tier["input_cache_miss_usd_per_million"]
        + float(cache_read_input_tokens or 0)
        * tier["input_cache_hit_usd_per_million"]
        + float(output_tokens or 0)
        * tier["output_usd_per_million"]
    ) / 1_000_000.0


def deepseek_flash_cost_range(
    input_tokens,
    cache_read_input_tokens,
    output_tokens,
):
    return {
        "pricing_snapshot_date": (
            DEEPSEEK_FLASH_PRICING_SNAPSHOT["snapshot_date"]
        ),
        "currency": "USD",
        "off_peak_usd": round(
            deepseek_flash_cost_usd(
                input_tokens,
                cache_read_input_tokens,
                output_tokens,
                peak=False,
            ),
            12,
        ),
        "peak_usd": round(
            deepseek_flash_cost_usd(
                input_tokens,
                cache_read_input_tokens,
                output_tokens,
                peak=True,
            ),
            12,
        ),
        "source": DEEPSEEK_FLASH_PRICING_SNAPSHOT["source"],
    }
