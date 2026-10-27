"""AgentLens SDK Client for background batch span ingestion.
"""

from __future__ import annotations

import atexit
import logging
import os
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Union

import httpx

logger = logging.getLogger("agentlens")


class AgentLensClient:
    def __init__(
        self,
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
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.debug = debug
        self.enabled = enabled

        # Resolve capture_inputs / capture_prompts
        if capture_prompts is not None:
            self.capture_inputs = bool(capture_prompts)
        elif "AGENTLENS_CAPTURE_PROMPTS" in os.environ:
            self.capture_inputs = os.environ["AGENTLENS_CAPTURE_PROMPTS"].strip().lower() not in ("0", "false", "no", "off")
        elif "AGENTLENS_CAPTURE_INPUTS" in os.environ:
            self.capture_inputs = os.environ["AGENTLENS_CAPTURE_INPUTS"].strip().lower() not in ("0", "false", "no", "off")
        else:
            self.capture_inputs = bool(capture_inputs)

        # Resolve capture_outputs / capture_completions
        if capture_completions is not None:
            self.capture_outputs = bool(capture_completions)
        elif "AGENTLENS_CAPTURE_COMPLETIONS" in os.environ:
            self.capture_outputs = os.environ["AGENTLENS_CAPTURE_COMPLETIONS"].strip().lower() not in ("0", "false", "no", "off")
        elif "AGENTLENS_CAPTURE_OUTPUTS" in os.environ:
            self.capture_outputs = os.environ["AGENTLENS_CAPTURE_OUTPUTS"].strip().lower() not in ("0", "false", "no", "off")
        else:
            self.capture_outputs = bool(capture_outputs)

        # Resolve redact_fields and redact_fn
        fields_set: Set[str] = set()
        if redact_fields:
            fields_set.update(f.strip().lower() for f in redact_fields if f and f.strip())
        env_redact = os.environ.get("AGENTLENS_REDACT_FIELDS")
        if env_redact:
            fields_set.update(f.strip().lower() for f in env_redact.split(",") if f.strip())
        self.redact_fields: Set[str] = fields_set
        self.redact_fn = redact_fn

        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=10000)
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        if self.enabled:
            self.start()

    @property
    def capture_prompts(self) -> bool:
        return self.capture_inputs

    @capture_prompts.setter
    def capture_prompts(self, val: bool) -> None:
        self.capture_inputs = bool(val)

    @property
    def capture_completions(self) -> bool:
        return self.capture_outputs

    @capture_completions.setter
    def capture_completions(self, val: bool) -> None:
        self.capture_outputs = bool(val)

    def _redact_value(self, key: Optional[str], value: Any) -> Any:
        if key is not None and key.lower() in self.redact_fields:
            return "[REDACTED]"
        if self.redact_fn is not None and key is not None:
            custom = self.redact_fn(key, value)
            if custom is not value:
                return custom
        if isinstance(value, dict):
            return {k: self._redact_value(str(k), v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._redact_value(key, v) for v in value]
        elif isinstance(value, tuple):
            return tuple(self._redact_value(key, v) for v in value)
        return value

    def _sanitize_span(self, span: Dict[str, Any]) -> Dict[str, Any]:
        span_copy = dict(span)
        if not self.capture_inputs:
            if "input" in span_copy:
                span_copy["input"] = None
        elif "input" in span_copy and span_copy["input"] is not None and (self.redact_fields or self.redact_fn):
            span_copy["input"] = self._redact_value("input", span_copy["input"])

        if not self.capture_outputs:
            if "output" in span_copy:
                span_copy["output"] = None
        elif "output" in span_copy and span_copy["output"] is not None and (self.redact_fields or self.redact_fn):
            span_copy["output"] = self._redact_value("output", span_copy["output"])

        if self.redact_fields or self.redact_fn:
            for k in list(span_copy.keys()):
                if k in ("input", "output"):
                    continue
                if k.lower() in self.redact_fields:
                    span_copy[k] = "[REDACTED]"
                elif self.redact_fn is not None:
                    span_copy[k] = self.redact_fn(k, span_copy[k])
                elif isinstance(span_copy[k], (dict, list, tuple)):
                    span_copy[k] = self._redact_value(k, span_copy[k])

        return span_copy

    def start(self):
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def enqueue(self, item: Dict[str, Any]):
        if not self.enabled:
            return
        if item.get("span_type") == "llm":
            from agentlens.context import increment_llm_span_count
            increment_llm_span_count()
        item = self._sanitize_span(item)
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            logger.warning("AgentLens queue full. Draining one item to make space.")
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except (queue.Empty, ValueError):
                pass
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                pass  # Fail-safe

    def _safe_enqueue(self, item: Dict[str, Any]):
        try:
            self.enqueue(item)
        except Exception as e:
            if self.debug:
                logger.debug(f"Failed to enqueue span: {e}", exc_info=True)

    def _send_batch(self, batch: List[Dict[str, Any]]):
        if not batch:
            return
        try:
            batch = [self._sanitize_span(s) for s in batch]
            url = f"{self.base_url}/v1/ingest"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {"spans": batch}

            # Sync request since we are on background worker thread
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    if self.debug:
                        logger.debug(
                            f"Ingest failed with status {resp.status_code}: {resp.text}"
                        )
        except Exception as e:
            if self.debug:
                logger.debug(f"Error sending batch to AgentLens: {e}", exc_info=True)

    def _worker(self):
        while not self._stop_event.is_set():
            batch = []
            start_time = time.time()
            while len(batch) < 100:
                elapsed = time.time() - start_time
                if elapsed >= 0.5:
                    break
                timeout = 0.5 - elapsed
                try:
                    item = self._queue.get(timeout=timeout)
                    batch.append(item)
                except queue.Empty:
                    break

            if batch:
                self._send_batch(batch)
                for _ in range(len(batch)):
                    self._queue.task_done()
            else:
                time.sleep(0.05)

    def flush(self, timeout: float = 5.0):
        start_time = time.time()
        while not self._queue.empty():
            if time.time() - start_time > timeout:
                break
            batch = []
            while len(batch) < 100:
                try:
                    item = self._queue.get_nowait()
                    batch.append(item)
                except queue.Empty:
                    break
            if batch:
                self._send_batch(batch)
                for _ in range(len(batch)):
                    self._queue.task_done()
            else:
                break

    def stop(self, timeout: float = 5.0):
        self._stop_event.set()
        self.flush(timeout=timeout)
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=timeout)
