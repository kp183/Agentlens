"""AgentLens Python SDK — zero-overhead observability for AI agents.
"""

from __future__ import annotations

import atexit
import logging
from typing import Any, Callable, List, Optional, Set, Union

from agentlens.client import AgentLensClient
from agentlens.decorators import span, trace
from agentlens.instruments.anthropic import instrument_anthropic
from agentlens.instruments.langgraph import AgentLensLangGraphCallbackHandler, instrument_langgraph
from agentlens.instruments.openai import instrument_openai

__version__ = "0.2.2"

__all__ = [
    "__version__",
    "init",
    "instrument_openai",
    "instrument_anthropic",
    "instrument_langgraph",
    "AgentLensLangGraphCallbackHandler",
    "trace",
    "span",
    "flush",
]

_global_client: Optional[AgentLensClient] = None
logger = logging.getLogger("agentlens")


def init(
    api_key: str,
    base_url: str = "http://localhost:8000",
    debug: bool = False,
    enabled: bool = True,
    capture_inputs: bool = True,
    capture_outputs: bool = True,
    capture_prompts: Optional[bool] = None,
    capture_completions: Optional[bool] = None,
    redact_fields: Optional[Union[List[str], Set[str]]] = None,
    redact_fn: Optional[Callable[[str, Any], Any]] = None,
) -> AgentLensClient:
    """Initialize the global AgentLens client.

    Args:
        api_key: AgentLens API key or project key.
        base_url: AgentLens backend URL.
        debug: Enable debug logging.
        enabled: Toggle tracing on or off globally.
        capture_inputs: Whether to record prompt and input payloads (default: True).
        capture_outputs: Whether to record completion and output payloads (default: True).
        capture_prompts: Alias for capture_inputs.
        capture_completions: Alias for capture_outputs.
        redact_fields: Field names whose values will be replaced with '[REDACTED]'.
        redact_fn: Custom callable (key, value) -> redacted_value for custom sanitization.
    """
    global _global_client

    if _global_client is not None:
        _global_client.stop()

    _global_client = AgentLensClient(
        api_key=api_key,
        base_url=base_url,
        debug=debug,
        enabled=enabled,
        capture_inputs=capture_inputs,
        capture_outputs=capture_outputs,
        capture_prompts=capture_prompts,
        capture_completions=capture_completions,
        redact_fields=redact_fields,
        redact_fn=redact_fn,
    )

    # Register exit handler to flush queue on shutdown
    if enabled:
        atexit.register(flush)

    return _global_client


def flush(timeout: float = 5.0) -> None:
    """Flush all currently buffered spans in the global client."""
    global _global_client
    if _global_client is not None and _global_client.enabled:
        try:
            _global_client.flush(timeout=timeout)
        except Exception as e:
            if _global_client.debug:
                logger.debug(f"Failed to flush spans: {e}", exc_info=True)
