"""Unit tests for CometAPI pricing sync logic.
"""

from unittest.mock import MagicMock, patch
import pytest

from agentlens.pricing import PRICING
from agentlens.pricing_sync import sync_pricing


def test_sync_pricing_normal_null_and_unknown_fields():
    mock_data = {
        "data": [
            {
                "id": "gpt-5-turbo",
                "pricing": {"input": 2.5, "output": 10.0},
                "unknown_extra_field": "some_value",
            },
            {
                "id": "experimental-null-model",
                "pricing": None,
                "unknown_extra_field": "ignored",
            },
            {
                "id": "model-missing-input-price",
                "pricing": {"input": None, "output": 5.0},
            },
            {
                "code": "new-cool-model",
                "pricing": {"input": 1.0, "output": 4.0},
            },
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        res = sync_pricing("https://mock.cometapi.com/api/models")

    # 1. Normal model mapped correctly (per million divided by 1,000,000)
    assert "gpt-5-turbo" in res
    assert res["gpt-5-turbo"]["input"] == pytest.approx(2.5 / 1_000_000)
    assert res["gpt-5-turbo"]["output"] == pytest.approx(10.0 / 1_000_000)

    # 2. Null pricing skipped (not added)
    assert "experimental-null-model" not in res
    assert "model-missing-input-price" not in res

    # 3. Model with alternative key 'code' and unknown fields parsed correctly
    assert "new-cool-model" in res
    assert res["new-cool-model"]["input"] == pytest.approx(1.0 / 1_000_000)

    # 4. Existing entries in PRICING preserved
    assert "gpt-4o" in res
