import asyncio
import logging
import agentlens as al
from agentlens import decorators


def test_warns_once_when_no_llm_spans_captured(caplog):
    """b) Traced function with no LLM call and no instrumentation -> ONE warning."""
    # Reset warning state for test
    decorators._warned_no_llm_spans = False

    al.init(api_key="test-key", base_url="http://localhost:8000")

    @al.trace(name="Test No LLM")
    def run_without_llm():
        return 42

    with caplog.at_level(logging.WARNING, logger="agentlens"):
        res = run_without_llm()
        assert res == 42

    expected_msg = (
        "No LLM spans captured under @al.trace. "
        "Did you forget to call al.instrument_openai() or al.instrument_anthropic()?"
    )
    warning_records = [r for r in caplog.records if expected_msg in r.message]
    assert len(warning_records) == 1

    # Calling it a second time should not emit the warning again (single one-time warning)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="agentlens"):
        res2 = run_without_llm()
        assert res2 == 42

    assert not any(expected_msg in r.message for r in caplog.records)


def test_no_warning_when_llm_span_captured(caplog):
    """
    a) Root trace with nested traced functions that make LLM calls -> NO warning.
    c) Instrumentation on with LLM call present -> NO warning (sync and async).
    """
    # Reset warning state for test
    decorators._warned_no_llm_spans = False
    expected_msg = (
        "No LLM spans captured under @al.trace. "
        "Did you forget to call al.instrument_openai() or al.instrument_anthropic()?"
    )

    client = al.init(api_key="test-key", base_url="http://localhost:8000")

    # c) Sync: Traced sync function with LLM call
    @al.trace(name="Sync With LLM")
    def run_sync_with_llm():
        client.enqueue({
            "id": "sync-span",
            "name": "sync-llm-call",
            "span_type": "llm",
        })
        return "sync_ok"

    with caplog.at_level(logging.WARNING, logger="agentlens"):
        res = run_sync_with_llm()
        assert res == "sync_ok"
    assert not any(expected_msg in r.message for r in caplog.records)

    # c) Async: Traced async function with LLM call
    @al.trace(name="Async With LLM")
    async def run_async_with_llm():
        client.enqueue({
            "id": "async-span",
            "name": "async-llm-call",
            "span_type": "llm",
        })
        return "async_ok"

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="agentlens"):
        res = asyncio.run(run_async_with_llm())
        assert res == "async_ok"
    assert not any(expected_msg in r.message for r in caplog.records)

    # a) Root trace with nested traced functions that make LLM calls -> NO warning
    @al.trace(name="Nested Traced Step")
    def nested_traced_step():
        client.enqueue({
            "id": "nested-span",
            "name": "nested-llm-call",
            "span_type": "llm",
        })
        return "nested_ok"

    @al.trace(name="Root Traced Flow")
    def root_flow():
        step_res = nested_traced_step()
        return f"root_{step_res}"

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="agentlens"):
        res = root_flow()
        assert res == "root_nested_ok"
    assert not any(expected_msg in r.message for r in caplog.records)
