"""LangGraph auto-instrumentation for AgentLens.

Hooks LangGraph state graphs and callback managers to record graph execution,
node transitions, and routing decisions as nested spans automatically.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import agentlens
from agentlens.context import get_span_id, get_trace_id

logger = logging.getLogger("agentlens")

# Duck-typed callback handler compatible with LangChain/LangGraph callback system
try:
    from langchain_core.callbacks.base import BaseCallbackHandler
except ImportError:
    class BaseCallbackHandler:
        pass


class AgentLensLangGraphCallbackHandler(BaseCallbackHandler):
    """Callback handler for LangGraph / LangChain graph node execution."""

    def __init__(self):
        super().__init__()
        self._active_spans: Dict[str, Dict[str, Any]] = {}

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        if agentlens._global_client is None or not agentlens._global_client.enabled:
            return

        trace_id = get_trace_id()
        if not trace_id:
            return

        str_run_id = str(run_id)
        parent_span_id = self._active_spans.get(str(parent_run_id), {}).get("span_id") if parent_run_id else get_span_id()
        span_id = str(uuid.uuid4())

        name = (metadata or {}).get("langgraph_node") or (serialized or {}).get("name") or "LangGraph Node"
        span_type = "agent" if "graph" in name.lower() or "agent" in name.lower() else "custom"

        started_at = datetime.now(timezone.utc)
        start_time = time.time()

        span_info = {
            "span_id": span_id,
            "trace_id": trace_id,
            "parent_span_id": parent_span_id,
            "name": name,
            "span_type": span_type,
            "started_at": started_at,
            "start_time": start_time,
            "inputs": inputs,
            "metadata": metadata or {},
        }
        self._active_spans[str_run_id] = span_info

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        str_run_id = str(run_id)
        span_info = self._active_spans.pop(str_run_id, None)
        if not span_info:
            return

        if agentlens._global_client is None or not agentlens._global_client.enabled:
            return

        ended_at = datetime.now(timezone.utc)
        duration_ms = int((time.time() - span_info["start_time"]) * 1000)

        span_payload = {
            "id": span_info["span_id"],
            "trace_id": span_info["trace_id"],
            "parent_span_id": span_info["parent_span_id"],
            "name": span_info["name"],
            "span_type": span_info["span_type"],
            "status": "success",
            "started_at": span_info["started_at"].isoformat(),
            "ended_at": ended_at.isoformat(),
            "duration_ms": duration_ms,
            "input": span_info["inputs"],
            "output": outputs,
            "metadata": span_info["metadata"],
        }
        agentlens._global_client._safe_enqueue(span_payload)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        str_run_id = str(run_id)
        span_info = self._active_spans.pop(str_run_id, None)
        if not span_info:
            return

        if agentlens._global_client is None or not agentlens._global_client.enabled:
            return

        ended_at = datetime.now(timezone.utc)
        duration_ms = int((time.time() - span_info["start_time"]) * 1000)

        span_payload = {
            "id": span_info["span_id"],
            "trace_id": span_info["trace_id"],
            "parent_span_id": span_info["parent_span_id"],
            "name": span_info["name"],
            "span_type": span_info["span_type"],
            "status": "error",
            "started_at": span_info["started_at"].isoformat(),
            "ended_at": ended_at.isoformat(),
            "duration_ms": duration_ms,
            "input": span_info["inputs"],
            "error_type": type(error).__name__,
            "error_message": str(error),
            "metadata": span_info["metadata"],
        }
        agentlens._global_client._safe_enqueue(span_payload)

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        if agentlens._global_client is None or not agentlens._global_client.enabled:
            return

        trace_id = get_trace_id()
        if not trace_id:
            return

        str_run_id = str(run_id)
        parent_span_id = self._active_spans.get(str(parent_run_id), {}).get("span_id") if parent_run_id else get_span_id()
        span_id = str(uuid.uuid4())

        tool_name = (serialized or {}).get("name") or "LangGraph Tool"
        started_at = datetime.now(timezone.utc)
        start_time = time.time()

        span_info = {
            "span_id": span_id,
            "trace_id": trace_id,
            "parent_span_id": parent_span_id,
            "name": tool_name,
            "span_type": "tool",
            "started_at": started_at,
            "start_time": start_time,
            "inputs": {"input": input_str},
            "metadata": metadata or {},
        }
        self._active_spans[str_run_id] = span_info

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        str_run_id = str(run_id)
        span_info = self._active_spans.pop(str_run_id, None)
        if not span_info:
            return

        if agentlens._global_client is None or not agentlens._global_client.enabled:
            return

        ended_at = datetime.now(timezone.utc)
        duration_ms = int((time.time() - span_info["start_time"]) * 1000)

        span_payload = {
            "id": span_info["span_id"],
            "trace_id": span_info["trace_id"],
            "parent_span_id": span_info["parent_span_id"],
            "name": span_info["name"],
            "span_type": "tool",
            "status": "success",
            "started_at": span_info["started_at"].isoformat(),
            "ended_at": ended_at.isoformat(),
            "duration_ms": duration_ms,
            "input": span_info["inputs"],
            "output": {"result": output},
            "metadata": span_info["metadata"],
        }
        agentlens._global_client._safe_enqueue(span_payload)


def instrument_langgraph():
    """Monkey-patch LangGraph's CompiledGraph invoke and stream methods to inject AgentLens tracing."""
    try:
        import langgraph.graph.state
        target_class = getattr(langgraph.graph.state, "CompiledStateGraph", None)
        if target_class is None:
            import langgraph.graph
            target_class = getattr(langgraph.graph, "CompiledGraph", None)
    except ImportError:
        logger.debug("langgraph package not installed. Skipping LangGraph instrumentation.")
        return

    if target_class is None or getattr(target_class, "_agentlens_instrumented", False):
        return
    target_class._agentlens_instrumented = True

    original_invoke = target_class.invoke

    def patched_invoke(self, input, config=None, **kwargs):
        config = config.copy() if config else {}
        callbacks = config.get("callbacks") or []
        if isinstance(callbacks, list):
            if not any(isinstance(c, AgentLensLangGraphCallbackHandler) for c in callbacks):
                callbacks = list(callbacks) + [AgentLensLangGraphCallbackHandler()]
        elif callbacks is not None:
            callbacks = [callbacks, AgentLensLangGraphCallbackHandler()]
        else:
            callbacks = [AgentLensLangGraphCallbackHandler()]

        config["callbacks"] = callbacks
        return original_invoke(self, input, config=config, **kwargs)

    target_class.invoke = patched_invoke

    if hasattr(target_class, "ainvoke"):
        original_ainvoke = target_class.ainvoke

        async def patched_ainvoke(self, input, config=None, **kwargs):
            config = config.copy() if config else {}
            callbacks = config.get("callbacks") or []
            if isinstance(callbacks, list):
                if not any(isinstance(c, AgentLensLangGraphCallbackHandler) for c in callbacks):
                    callbacks = list(callbacks) + [AgentLensLangGraphCallbackHandler()]
            elif callbacks is not None:
                callbacks = [callbacks, AgentLensLangGraphCallbackHandler()]
            else:
                callbacks = [AgentLensLangGraphCallbackHandler()]

            config["callbacks"] = callbacks
            return await original_ainvoke(self, input, config=config, **kwargs)

        target_class.ainvoke = patched_ainvoke
