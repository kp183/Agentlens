"""AgentLens Zero-Config Offline Demo.

Run this script to test trace capture and dashboard visualization without
requiring an OpenAI API key or network access to third-party model providers.
Uses an in-memory httpx mock transport to simulate chat completions.
"""

from __future__ import annotations

import httpx
import agentlens as al
from openai import OpenAI


class MockOpenAITransport(httpx.BaseTransport):
    """Mock HTTP transport returning a simulated OpenAI ChatCompletion."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        mock_payload = {
            "id": "chatcmpl-offline-demo",
            "object": "chat.completion",
            "created": 1719500000,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! Your AgentLens offline demo trace was captured and transmitted successfully.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 19,
                "completion_tokens": 15,
                "total_tokens": 34,
            },
        }
        return httpx.Response(200, json=mock_payload, request=request)


# 1. Initialize AgentLens SDK & auto-instrument OpenAI
al.init(api_key="local-dev-key", base_url="http://localhost:8000")
al.instrument_openai()

# 2. Configure OpenAI client with mock transport (no live API key needed)
mock_client = httpx.Client(transport=MockOpenAITransport())
client = OpenAI(api_key="mock-offline-key", http_client=mock_client)


# 3. Execute trace
@al.trace(name="Offline Demo Run")
def main():
    print("Sending simulated LLM chat completion through instrumented client...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Test offline AgentLens tracing!"}],
    )
    print(f"Assistant response: {response.choices[0].message.content}")


if __name__ == "__main__":
    main()
    al.flush()
    print("\nTrace successfully recorded and flushed!")
    print("Open the dashboard at http://localhost:3000 to inspect your trace.")
