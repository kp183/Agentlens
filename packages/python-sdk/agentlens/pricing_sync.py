"""CometAPI pricing table sync module.

Fetches current pricing from CometAPI and merges updated token costs into
AgentLens' built-in pricing dictionary.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict

import httpx

from agentlens.pricing import PRICING

logger = logging.getLogger("agentlens")

COMETAPI_MODELS_URL = "https://api.cometapi.com/api/models"


def sync_pricing(api_url: str = COMETAPI_MODELS_URL) -> Dict[str, Dict[str, float]]:
    """Fetch model pricing from CometAPI and update the PRICING dictionary in-place.

    Per-million token rates are converted to per-token rates (divided by 1,000,000).
    Models with null/missing pricing are skipped to avoid overwriting valid prices.
    Returns the updated PRICING dictionary.
    """
    try:
        response = httpx.get(api_url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.error(f"Failed to fetch pricing from {api_url}: {e}")
        return PRICING

    models = data.get("data", []) if isinstance(data, dict) else data
    if not isinstance(models, list):
        logger.warning("Unexpected response format from pricing API")
        return PRICING

    synced_count = 0
    for model in models:
        if not isinstance(model, dict):
            continue

        model_id = model.get("id") or model.get("code") or model.get("name")
        if not model_id:
            continue

        pricing = model.get("pricing")
        if not pricing or not isinstance(pricing, dict):
            logger.debug(f"Skipping model '{model_id}' — pricing is null or invalid")
            continue

        input_rate = pricing.get("input")
        output_rate = pricing.get("output")

        if input_rate is None or output_rate is None:
            logger.debug(f"Skipping model '{model_id}' — input or output pricing missing")
            continue

        try:
            in_cost = float(input_rate) / 1_000_000
            out_cost = float(output_rate) / 1_000_000
            PRICING[str(model_id)] = {
                "input": in_cost,
                "output": out_cost,
            }
            synced_count += 1
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing pricing for model '{model_id}': {e}")
            continue

    logger.info(f"Successfully synced pricing for {synced_count} models from CometAPI.")
    return PRICING


def main():
    logging.basicConfig(level=logging.INFO)
    print("Fetching latest model pricing from CometAPI...")
    updated_pricing = sync_pricing()
    print(f"Sync complete. {len(updated_pricing)} models currently in PRICING dictionary.")


if __name__ == "__main__":
    main()
