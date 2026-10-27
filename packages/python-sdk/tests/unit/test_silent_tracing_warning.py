import logging
import agentlens as al
from agentlens import decorators


def test_warns_once_when_no_llm_spans_captured(caplog):
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
    assert any(expected_msg in r.message for r in caplog.records)

    # Calling it a second time should not emit the warning again (single one-time warning)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="agentlens"):
        res2 = run_without_llm()
        assert res2 == 42

    assert not any(expected_msg in r.message for r in caplog.records)


def test_no_warning_when_llm_span_captured(caplog):
    # Reset warning state for test
    decorators._warned_no_llm_spans = False

    client = al.init(api_key="test-key", base_url="http://localhost:8000")

    @al.trace(name="Test With LLM")
    def run_with_llm():
        client.enqueue({
            "id": "test-span",
            "name": "llm-call",
            "span_type": "llm",
        })
        return "ok"

    with caplog.at_level(logging.WARNING, logger="agentlens"):
        res = run_with_llm()
        assert res == "ok"

    expected_msg = (
        "No LLM spans captured under @al.trace. "
        "Did you forget to call al.instrument_openai() or al.instrument_anthropic()?"
    )
    assert not any(expected_msg in r.message for r in caplog.records)
