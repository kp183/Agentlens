"""Unit tests for LangGraph auto-instrumentation.
"""

import sys
from unittest.mock import MagicMock, patch
import uuid
import pytest

import agentlens as al
from agentlens.instruments.langgraph import AgentLensLangGraphCallbackHandler, instrument_langgraph


@patch.object(al.AgentLensClient, "_safe_enqueue")
def test_langgraph_callback_handler_captures_spans(mock_enqueue):
    client = al.init(api_key="al_live_test", enabled=True)
    handler = AgentLensLangGraphCallbackHandler()

    # Create root trace span context manager
    with al.span("LangGraph Test Workflow"):
        run_id = uuid.uuid4()
        handler.on_chain_start(
            serialized={"name": "StateGraph"},
            inputs={"messages": ["Hello"]},
            run_id=run_id,
            metadata={"langgraph_node": "agent_step"},
        )

        # Simulate tool execution
        tool_run_id = uuid.uuid4()
        handler.on_tool_start(
            serialized={"name": "calculator"},
            input_str="2 + 2",
            run_id=tool_run_id,
            parent_run_id=run_id,
        )

        handler.on_tool_end(
            output="4",
            run_id=tool_run_id,
            parent_run_id=run_id,
        )

        handler.on_chain_end(
            outputs={"messages": ["Hello", "Result: 4"]},
            run_id=run_id,
        )

    # Verify spans were enqueued
    assert mock_enqueue.call_count >= 2

    # Check tool span
    enqueued_payloads = [call.args[0] for call in mock_enqueue.call_args_list]
    tool_spans = [s for s in enqueued_payloads if s.get("span_type") == "tool"]
    assert len(tool_spans) == 1
    assert tool_spans[0]["name"] == "calculator"
    assert tool_spans[0]["output"] == {"result": "4"}


def test_instrument_langgraph_injects_callback():
    class DummyCompiledGraph:
        _agentlens_instrumented = False

        def invoke(self, input, config=None, **kwargs):
            return {"config": config}

    mock_langgraph = MagicMock()
    mock_langgraph.graph.state.CompiledStateGraph = DummyCompiledGraph

    modules = {
        "langgraph": mock_langgraph,
        "langgraph.graph": mock_langgraph.graph,
        "langgraph.graph.state": mock_langgraph.graph.state,
    }

    with patch.dict(sys.modules, modules):
        DummyCompiledGraph._agentlens_instrumented = False
        instrument_langgraph()
        graph = DummyCompiledGraph()
        res = graph.invoke({"input": "test"})

        assert res is not None
        assert "config" in res
        callbacks = res["config"]["callbacks"]
        assert any(isinstance(c, AgentLensLangGraphCallbackHandler) for c in callbacks)
