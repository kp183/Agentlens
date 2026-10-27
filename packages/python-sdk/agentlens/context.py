"""ContextVar-based trace/span ID propagation.

These vars are set by the @trace decorator and span() context manager so that
nested calls automatically inherit the current trace and span context without
any explicit passing.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_current_trace_id: ContextVar[Optional[str]] = ContextVar("_current_trace_id", default=None)
_current_span_id: ContextVar[Optional[str]] = ContextVar("_current_span_id", default=None)


def get_trace_id() -> Optional[str]:
    return _current_trace_id.get()


def get_span_id() -> Optional[str]:
    return _current_span_id.get()


def set_trace_id(value: Optional[str]):
    return _current_trace_id.set(value)


def set_span_id(value: Optional[str]):
    return _current_span_id.set(value)


_current_llm_span_count: ContextVar[int] = ContextVar("_current_llm_span_count", default=0)


def get_llm_span_count() -> int:
    return _current_llm_span_count.get()


def set_llm_span_count(value: int):
    return _current_llm_span_count.set(value)


def increment_llm_span_count() -> None:
    _current_llm_span_count.set(_current_llm_span_count.get() + 1)

