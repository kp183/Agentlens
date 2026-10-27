"""Decorators and context managers for AgentLens instrumentation.
"""

from __future__ import annotations

import inspect
import logging
import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, List, Optional

from agentlens.context import (
    _current_llm_span_count,
    _current_span_id,
    _current_trace_id,
    get_llm_span_count,
    get_span_id,
    get_trace_id,
    increment_llm_span_count,
    set_llm_span_count,
    set_span_id,
    set_trace_id,
)

logger = logging.getLogger("agentlens")
_warned_no_llm_spans: bool = False


def trace(name: Optional[str] = None, tags: Optional[List[str]] = None) -> Callable[..., Any]:
    """Decorator to mark a function as a trace root or nested trace span."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                import agentlens
                if agentlens._global_client is None or not agentlens._global_client.enabled:
                    return await func(*args, **kwargs)

                parent_trace_id = get_trace_id()
                is_root = parent_trace_id is None
                trace_id = parent_trace_id if not is_root else str(uuid.uuid4())
                parent_span_id = get_span_id() if not is_root else None
                span_id = str(uuid.uuid4())

                trace_token = set_trace_id(trace_id)
                span_token = set_span_id(span_id)
                llm_count_token = set_llm_span_count(0) if is_root else None

                span_name = name or func.__name__
                started_at = datetime.now(timezone.utc)
                start_time = time.time()

                status = "success"
                error_type = None
                error_message = None
                error_stack = None

                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    status = "error"
                    error_type = type(e).__name__
                    error_message = str(e)
                    error_stack = traceback.format_exc()
                    raise e
                finally:
                    ended_at = datetime.now(timezone.utc)
                    duration_ms = int((time.time() - start_time) * 1000)

                    span_payload = {
                        "id": span_id,
                        "trace_id": trace_id,
                        "parent_span_id": parent_span_id,
                        "name": span_name,
                        "span_type": "custom",
                        "status": status,
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "duration_ms": duration_ms,
                        "tags": tags or [],
                    }
                    if error_type:
                        span_payload.update({
                            "error_type": error_type,
                            "error_message": error_message,
                            "error_stack": error_stack,
                        })

                    agentlens._global_client._safe_enqueue(span_payload)

                    if is_root:
                        llm_count = get_llm_span_count()
                        global _warned_no_llm_spans
                        if llm_count == 0 and not _warned_no_llm_spans:
                            _warned_no_llm_spans = True
                            logger.warning(
                                "No LLM spans captured under @al.trace. Did you forget to call al.instrument_openai() or al.instrument_anthropic()?"
                            )
                        if llm_count_token is not None:
                            _current_llm_span_count.reset(llm_count_token)

                    _current_span_id.reset(span_token)
                    _current_trace_id.reset(trace_token)

            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                import agentlens
                if agentlens._global_client is None or not agentlens._global_client.enabled:
                    return func(*args, **kwargs)

                parent_trace_id = get_trace_id()
                is_root = parent_trace_id is None
                trace_id = parent_trace_id if not is_root else str(uuid.uuid4())
                parent_span_id = get_span_id() if not is_root else None
                span_id = str(uuid.uuid4())

                trace_token = set_trace_id(trace_id)
                span_token = set_span_id(span_id)
                llm_count_token = set_llm_span_count(0) if is_root else None

                span_name = name or func.__name__
                started_at = datetime.now(timezone.utc)
                start_time = time.time()

                status = "success"
                error_type = None
                error_message = None
                error_stack = None

                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    status = "error"
                    error_type = type(e).__name__
                    error_message = str(e)
                    error_stack = traceback.format_exc()
                    raise e
                finally:
                    ended_at = datetime.now(timezone.utc)
                    duration_ms = int((time.time() - start_time) * 1000)

                    span_payload = {
                        "id": span_id,
                        "trace_id": trace_id,
                        "parent_span_id": parent_span_id,
                        "name": span_name,
                        "span_type": "custom",
                        "status": status,
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "duration_ms": duration_ms,
                        "tags": tags or [],
                    }
                    if error_type:
                        span_payload.update({
                            "error_type": error_type,
                            "error_message": error_message,
                            "error_stack": error_stack,
                        })

                    agentlens._global_client._safe_enqueue(span_payload)

                    if is_root:
                        llm_count = get_llm_span_count()
                        global _warned_no_llm_spans
                        if llm_count == 0 and not _warned_no_llm_spans:
                            _warned_no_llm_spans = True
                            logger.warning(
                                "No LLM spans captured under @al.trace. Did you forget to call al.instrument_openai() or al.instrument_anthropic()?"
                            )
                        if llm_count_token is not None:
                            _current_llm_span_count.reset(llm_count_token)

                    _current_span_id.reset(span_token)
                    _current_trace_id.reset(trace_token)

            return sync_wrapper
    return decorator


class Span:
    def __init__(self, id: str, trace_id: str, parent_span_id: Optional[str] = None):
        self.id = id
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.metadata = {}
        self.input = None
        self.output = None
        self.input_tokens = None
        self.output_tokens = None
        self.model = None
        self.provider = None

    def set_metadata(self, key_or_dict: Any, value: Any = None):
        if isinstance(key_or_dict, dict):
            for k, v in key_or_dict.items():
                self._set_key(k, v)
        else:
            self._set_key(key_or_dict, value)

    def _set_key(self, key: str, value: Any):
        if key == "input_tokens":
            self.input_tokens = value
        elif key == "output_tokens":
            self.output_tokens = value
        elif key == "model":
            self.model = value
        elif key == "provider":
            self.provider = value
        else:
            self.metadata[key] = value

    def set_output(self, output: Any):
        self.output = output

    def set_input(self, input_val: Any):
        self.input = input_val


@contextmanager
def span(name: str, span_type: str = "custom", tags: Optional[List[str]] = None):
    """Context manager to mark a block of code as a span."""
    import agentlens
    if agentlens._global_client is None or not agentlens._global_client.enabled:
        yield Span(id="", trace_id="")
        return

    # Check or generate a root trace context if none exists
    trace_id = get_trace_id()
    trace_token = None
    if not trace_id:
        trace_id = str(uuid.uuid4())
        trace_token = set_trace_id(trace_id)

    parent_span_id = get_span_id()
    span_id = str(uuid.uuid4())

    span_token = set_span_id(span_id)

    started_at = datetime.now(timezone.utc)
    start_time = time.time()

    status = "success"
    error_type = None
    error_message = None
    error_stack = None

    s = Span(id=span_id, trace_id=trace_id, parent_span_id=parent_span_id)

    try:
        yield s
    except Exception as e:
        status = "error"
        error_type = type(e).__name__
        error_message = str(e)
        error_stack = traceback.format_exc()
        raise e
    finally:
        ended_at = datetime.now(timezone.utc)
        duration_ms = int((time.time() - start_time) * 1000)

        span_payload = {
            "id": span_id,
            "trace_id": trace_id,
            "parent_span_id": parent_span_id,
            "name": name,
            "span_type": span_type,
            "status": status,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "duration_ms": duration_ms,
            "tags": tags or [],
        }
        if error_type:
            span_payload.update({
                "error_type": error_type,
                "error_message": error_message,
                "error_stack": error_stack,
            })

        if s.input is not None:
            span_payload["input"] = s.input
        if s.output is not None:
            span_payload["output"] = s.output
        if s.metadata:
            span_payload["metadata"] = s.metadata
        if s.input_tokens is not None:
            span_payload["input_tokens"] = s.input_tokens
        if s.output_tokens is not None:
            span_payload["output_tokens"] = s.output_tokens
        if s.model is not None:
            span_payload["model"] = s.model
        if s.provider is not None:
            span_payload["provider"] = s.provider

        agentlens._global_client._safe_enqueue(span_payload)

        _current_span_id.reset(span_token)
        if trace_token:
            _current_trace_id.reset(trace_token)
