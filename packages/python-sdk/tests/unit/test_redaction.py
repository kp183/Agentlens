import os
from unittest.mock import MagicMock, patch
import pytest

from agentlens.client import AgentLensClient
import agentlens as al


@patch.object(AgentLensClient, "start")
def test_default_capture_behavior(mock_start):
    client = AgentLensClient(api_key="test_key", enabled=True)
    payload = {
        "id": "s1",
        "input": {"messages": [{"role": "user", "content": "hello secret"}]},
        "output": {"choices": [{"message": {"role": "assistant", "content": "response"}}]},
    }
    client.enqueue(payload)
    item = client._queue.get_nowait()
    assert item["input"] == {"messages": [{"role": "user", "content": "hello secret"}]}
    assert item["output"] == {"choices": [{"message": {"role": "assistant", "content": "response"}}]}


@patch.object(AgentLensClient, "start")
def test_disable_prompt_capture(mock_start):
    client = AgentLensClient(api_key="test_key", enabled=True, capture_prompts=False)
    payload = {
        "id": "s2",
        "input": {"messages": [{"role": "user", "content": "secret prompt"}]},
        "output": {"text": "allowed output"},
    }
    client.enqueue(payload)
    item = client._queue.get_nowait()
    assert item["input"] is None
    assert item["output"] == {"text": "allowed output"}


@patch.object(AgentLensClient, "start")
def test_disable_completion_capture(mock_start):
    client = AgentLensClient(api_key="test_key", enabled=True, capture_completions=False)
    payload = {
        "id": "s3",
        "input": {"messages": [{"role": "user", "content": "allowed prompt"}]},
        "output": {"text": "secret completion"},
    }
    client.enqueue(payload)
    item = client._queue.get_nowait()
    assert item["input"] == {"messages": [{"role": "user", "content": "allowed prompt"}]}
    assert item["output"] is None


@patch.object(AgentLensClient, "start")
def test_field_level_redaction(mock_start):
    client = AgentLensClient(
        api_key="test_key",
        enabled=True,
        redact_fields=["password", "secret", "content", "error_message"],
    )
    payload = {
        "id": "s4",
        "input": {
            "messages": [
                {"role": "user", "content": "super secret prompt"},
                {"role": "system", "password": "plaintext_pass"},
            ],
            "metadata": {"other": "safe"},
        },
        "output": {"text": "ok", "secret": "classified"},
        "error_message": "Failed with password: 12345",
    }
    client.enqueue(payload)
    item = client._queue.get_nowait()
    assert item["input"]["messages"][0]["content"] == "[REDACTED]"
    assert item["input"]["messages"][1]["password"] == "[REDACTED]"
    assert item["input"]["metadata"]["other"] == "safe"
    assert item["output"]["secret"] == "[REDACTED]"
    assert item["output"]["text"] == "ok"
    assert item["error_message"] == "[REDACTED]"


@patch.object(AgentLensClient, "start")
def test_custom_redact_fn(mock_start):
    def mask_emails(key, value):
        if key == "email" and isinstance(value, str) and "@" in value:
            user, domain = value.split("@", 1)
            return f"***@{domain}"
        return value

    client = AgentLensClient(api_key="test_key", enabled=True, redact_fn=mask_emails)
    payload = {
        "id": "s5",
        "input": {"user": "alice", "email": "alice@example.com"},
    }
    client.enqueue(payload)
    item = client._queue.get_nowait()
    assert item["input"]["email"] == "***@example.com"
    assert item["input"]["user"] == "alice"


@patch.object(AgentLensClient, "start")
def test_env_var_configuration(mock_start, monkeypatch):
    monkeypatch.setenv("AGENTLENS_CAPTURE_PROMPTS", "false")
    monkeypatch.setenv("AGENTLENS_CAPTURE_COMPLETIONS", "0")
    monkeypatch.setenv("AGENTLENS_REDACT_FIELDS", "ssn,credit_card")

    client = AgentLensClient(api_key="test_key", enabled=True)
    assert client.capture_inputs is False
    assert client.capture_outputs is False
    assert "ssn" in client.redact_fields
    assert "credit_card" in client.redact_fields

    payload = {
        "id": "s6",
        "input": {"text": "sensitive prompt"},
        "output": {"text": "sensitive completion"},
        "ssn": "123-45-6789",
    }
    client.enqueue(payload)
    item = client._queue.get_nowait()
    assert item["input"] is None
    assert item["output"] is None
    assert item["ssn"] == "[REDACTED]"


@patch("agentlens.client.httpx.Client")
@patch.object(AgentLensClient, "start")
def test_send_batch_sanitization_defense_in_depth(mock_start, mock_httpx_client):
    mock_post = MagicMock()
    mock_post.status_code = 200
    mock_httpx_client.return_value.__enter__.return_value.post = mock_post

    client = AgentLensClient(api_key="test_key", enabled=True, capture_prompts=False, redact_fields=["api_token"])
    raw_span = {
        "id": "s7",
        "input": {"prompt": "should be stripped"},
        "output": {"answer": "allowed"},
        "api_token": "secret_abc",
    }
    client._send_batch([raw_span])

    sent_payload = mock_post.call_args[1]["json"]
    sent_span = sent_payload["spans"][0]
    assert sent_span["input"] is None
    assert sent_span["output"] == {"answer": "allowed"}
    assert sent_span["api_token"] == "[REDACTED]"


def test_init_sdk_wrapper_options():
    client = al.init(
        api_key="test",
        enabled=False,
        capture_prompts=False,
        capture_completions=False,
        redact_fields=["token"],
    )
    assert client.capture_inputs is False
    assert client.capture_outputs is False
    assert "token" in client.redact_fields
