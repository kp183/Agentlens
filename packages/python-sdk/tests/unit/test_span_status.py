"""Unit tests for Span.set_status() in AgentLens SDK."""

import pytest
import agentlens as al
from agentlens.decorators import Span


def test_span_set_status_validation():
    s = Span(id="test-span", trace_id="test-trace")

    # Valid statuses
    s.set_status("success")
    assert s.status == "success"
    assert s.error_message is None
    assert s.error_type is None

    s.set_status("error", message="Something broke")
    assert s.status == "error"
    assert s.error_message == "Something broke"
    assert s.error_type == "Error"

    s.set_status("error", message="Policy violated", error_type="PolicyError")
    assert s.status == "error"
    assert s.error_message == "Policy violated"
    assert s.error_type == "PolicyError"

    # Invalid status
    with pytest.raises(ValueError, match="Invalid status 'invalid'"):
        s.set_status("invalid")


def test_span_context_manager_manual_error():
    client = al.init("test-key", base_url="http://localhost:8000")
    enqueued = []
    client._safe_enqueue = lambda payload: enqueued.append(payload)

    with al.span("manual_fail_span", span_type="custom") as s:
        s.set_status("error", message="Pathlayer STOP: loop detected", error_type="GuardrailStop")

    assert len(enqueued) == 1
    payload = enqueued[0]
    assert payload["name"] == "manual_fail_span"
    assert payload["status"] == "error"
    assert payload["error_message"] == "Pathlayer STOP: loop detected"
    assert payload["error_type"] == "GuardrailStop"


def test_span_context_manager_manual_success():
    client = al.init("test-key", base_url="http://localhost:8000")
    enqueued = []
    client._safe_enqueue = lambda payload: enqueued.append(payload)

    with al.span("manual_success_span") as s:
        s.set_status("success")

    assert len(enqueued) == 1
    payload = enqueued[0]
    assert payload["name"] == "manual_success_span"
    assert payload["status"] == "success"
    assert "error_type" not in payload
    assert "error_message" not in payload


def test_exception_path_takes_precedence_over_manual_status():
    client = al.init("test-key", base_url="http://localhost:8000")
    enqueued = []
    client._safe_enqueue = lambda payload: enqueued.append(payload)

    with pytest.raises(ZeroDivisionError):
        with al.span("exception_span") as s:
            s.set_status("success")
            _ = 1 / 0

    assert len(enqueued) == 1
    payload = enqueued[0]
    assert payload["status"] == "error"
    assert payload["error_type"] == "ZeroDivisionError"
    assert "division by zero" in payload["error_message"]
    assert "error_stack" in payload
