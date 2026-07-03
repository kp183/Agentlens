"""Unit tests for OpenAI client provider resolution logic.
"""

from unittest.mock import MagicMock
from agentlens.instruments.openai import _get_provider_from_client


def test_provider_resolution_default_openai():
    completions = MagicMock()
    completions._client.base_url = "https://api.openai.com/v1/"
    assert _get_provider_from_client(completions) == "openai"


def test_provider_resolution_cometapi():
    completions = MagicMock()
    completions._client.base_url = "https://api.cometapi.com/v1"
    assert _get_provider_from_client(completions) == "cometapi"


def test_provider_resolution_unknown_custom_gateway():
    completions = MagicMock()
    completions._client.base_url = "https://custom.llm.gateway.io/v1"
    assert _get_provider_from_client(completions) == "custom.llm.gateway.io"


def test_provider_resolution_none_or_missing_client():
    completions = MagicMock()
    completions._client = None
    assert _get_provider_from_client(completions) == "openai"
