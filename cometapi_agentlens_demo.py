"""
AgentLens x CometAPI — multi-provider fallback demo
=====================================================

What this shows:
  1. AgentLens auto-instruments the OpenAI client. Because CometAPI is
     OpenAI-protocol-compatible, pointing that same client at CometAPI's
     base_url means every call gets traced for free — no special adapter.
  2. A small fallback router that tries a chain of models *through
     CometAPI* and lets AgentLens capture each attempt (success, error,
     tokens, latency) as a span nested under one trace.
  3. A real gap this exposes: AgentLens' built-in cost table only knows
     ~11 native OpenAI/Anthropic model names. Anything routed through
     CometAPI under a different model alias (glm-5.2, gemini-3.1-pro-preview,
     kimi-k2.7-code, etc.) comes back with cost_usd = 0.0.

Setup:
  pip install -e packages/python-sdk
  pip install openai
  export AGENTLENS_API_KEY="al_live_..."
  export AGENTLENS_BASE_URL="http://localhost:8000"
  export COMETAPI_KEY="sk-..."

Run:
  python cometapi_agentlens_demo.py
"""

import os
import sys

import agentlens as al
from openai import OpenAI

al.init(
    api_key=os.environ.get("AGENTLENS_API_KEY", ""),
    base_url=os.environ.get("AGENTLENS_BASE_URL", "http://localhost:8000"),
)
al.instrument_openai()

client = OpenAI(
    api_key=os.environ.get("COMETAPI_KEY", ""),
    base_url="https://api.cometapi.com/v1",
)

# Deliberately put a bad/likely-unavailable model first so the fallback
# path actually triggers in a demo run, instead of depending on timing
# a real provider outage.
MODEL_CHAIN = [
    ("gpt-5.4-mini-does-not-exist", "primary (intentionally broken for demo)"),
    ("glm-5.2", "fallback-1"),
    ("gemini-3.1-pro-preview", "fallback-2"),
]


@al.trace(name="Multi-Provider Chat via CometAPI")
def ask(prompt: str) -> str:
    """Root trace: one logical user request, routed through CometAPI
    with a model fallback chain. Every attempt becomes its own nested
    LLM span (auto-instrumented), inside one parent 'router' span."""
    with al.span(name="CometAPI Fallback Router", span_type="tool") as router:
        attempts = []
        for model, role in MODEL_CHAIN:
            router.set_metadata("attempting", {"model": model, "role": role})
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                )
                router.set_output({"used_model": model, "role": role})
                attempts.append({"model": model, "status": "success"})
                _print_cost_gap(model, response)
                return response.choices[0].message.content
            except Exception as e:
                attempts.append({"model": model, "status": "error", "error": str(e)})
                router.set_metadata(f"failed::{model}", str(e))
                continue
        router.set_metadata("all_attempts", attempts)
        raise RuntimeError("All models in the fallback chain failed.")


def _print_cost_gap(model: str, response) -> None:
    """Demonstrates the cost-tracking blind spot for non-native model
    names. AgentLens' pricing table only covers ~11 OpenAI/Anthropic
    model strings, so anything else silently costs $0.00 in the trace."""
    from agentlens.pricing import calculate_cost, PRICING

    usage = getattr(response, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", 0) or 0
    out_tok = getattr(usage, "completion_tokens", 0) or 0
    cost = calculate_cost(model, in_tok, out_tok)

    print(f"\n--- Cost tracking check for model='{model}' ---")
    print(f"tokens: in={in_tok} out={out_tok}")
    print(f"AgentLens-calculated cost_usd: ${cost:.6f}")
    if model not in PRICING:
        print(
            f"^ $0.00 because '{model}' isn't in AgentLens' built-in pricing "
            "table. This is exactly the gap a CometAPI-side cost/usage field "
            "would close."
        )
    print("-" * 50)


if __name__ == "__main__":
    if not os.environ.get("AGENTLENS_API_KEY") or not os.environ.get("COMETAPI_KEY"):
        print(
            "Missing env vars. Set AGENTLENS_API_KEY and COMETAPI_KEY before running.",
            file=sys.stderr,
        )
        sys.exit(1)

    result = ask("In two sentences, explain why model fallback matters for production agents.")
    print("\n=== Final answer ===")
    print(result)

    al.flush()  # make sure spans are sent before the process exits
