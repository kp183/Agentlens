# AgentLens Python SDK

The official Python client for AgentLens. Easily trace agent execution steps, nested tool calls, and LLM completions with non-blocking, asynchronous ingestion.

## Key Features

- **Micro-Batched Background Ingestion**: Uses a thread-safe daemon worker (`SpanQueue` wrapping a safe `queue.Queue`) to buffer and flush spans concurrently without delaying agent execution.
- **Zero-Dependency Exception Guard**: The SDK never propagates internal networking or API exceptions, ensuring your production agent runs remain robust.
- **Automatic Cost & Token Estimation**: Immediate calculations of token consumption and pricing for popular OpenAI and Anthropic models.
- **Auto-Instrumentation**: Monkey-patches OpenAI and Anthropic clients to capture inputs, outputs, tokens, and streaming responses out-of-the-box.

---

## Installation

Install the package via `pip` (or `uv` / `poetry`):

```bash
pip install agentlens-py
```

> [!NOTE]
> Note that the package is installed via `agentlens-py`, but the Python import name remains `import agentlens as al`.

---

## Quick Start

Instrument your application and generate your first trace in seconds:

```bash
pip install agentlens-py openai
```

> [!NOTE]
> The live quickstart requires an active `OPENAI_API_KEY` environment variable (`export OPENAI_API_KEY="your-key"` or `$env:OPENAI_API_KEY="your-key"`). No OpenAI key? Run the simulated offline demo: `python examples/offline_demo.py`.

```python
import agentlens as al
import openai

# 1. Initialize the global client and instrument OpenAI
al.init(api_key="al_live_YOUR_API_KEY_HERE", base_url="http://localhost:8000")
al.instrument_openai()

client = openai.OpenAI()

# 2. Establish a trace root using @al.trace
@al.trace(name="My First Agent Run")
def main():
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Explain quantizing neural networks."}],
    )

response = main()
al.flush()

# Traces appear live in your dashboard at http://localhost:3000
```

---

## Detailed Usage

### Decorators & Context Managers

Trace custom Python functions or specific logical blocks inside your agents:

```python
import agentlens as al

# 1. Trace a high-level agent loop
@al.trace(name="Customer Assistant Agent")
def run_assistant(user_query: str):
    print("Agent started...")
    
    # 2. Trace tool calls or sub-steps using context managers
    with al.span(name="Database Lookup", span_type="tool") as s:
        s.set_metadata("query", user_query)
        result = db_search(user_query)
        s.set_output({"results_count": len(result)})
        
    return result
```

### Auto-Instrumentation Examples

Auto-instrumented calls must be executed within an `@al.trace` context so spans are properly grouped and organized into a hierarchical trace tree:

#### OpenAI (Both Streaming & Non-Streaming)

```python
import openai
import agentlens as al

al.init(api_key="al_live_...")
al.instrument_openai()

client = openai.OpenAI()

@al.trace(name="OpenAI Generation")
def generate():
    # Spans are automatically created for completions, including token counts and costs
    return client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Explain quantizing neural networks."}]
    )

generate()
al.flush()
```

#### Anthropic (Both Streaming & Non-Streaming)

```python
import anthropic
import agentlens as al

al.init(api_key="al_live_...")
al.instrument_anthropic()

client = anthropic.Anthropic()

@al.trace(name="Anthropic Generation")
def generate():
    return client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        messages=[{"role": "user", "content": "What is reinforcement learning?"}]
    )

generate()
al.flush()
```

#### LangGraph Auto-Instrumentation

```python
import agentlens as al
from langgraph.graph import StateGraph

al.init(api_key="al_live_...")
al.instrument_langgraph()

# All LangGraph CompiledStateGraph invocations automatically record
# node transitions, routing decisions, and tool executions as nested spans
@al.trace(name="LangGraph Workflow")
def run_graph():
    graph = builder.compile()
    return graph.invoke({"messages": [("user", "Calculate 2 + 2")]})

run_graph()
al.flush()
```

---

## 🔒 Privacy, Redaction & Data Transmission

By default, AgentLens records prompts (`input`), completions (`output`), token counts, model names, latency, and exception details to help you debug and inspect agents.

### Data Collection & Transmission Statement
When tracing is enabled, AgentLens transmits JSON batches to `{base_url}/v1/ingest` containing:
- `id`, `trace_id`, `parent_span_id`: Span identifiers for hierarchy.
- `name`, `span_type`, `model`, `provider`: Operational metadata.
- `duration_ms`, `started_at`, `ended_at`: Performance metrics.
- `input_tokens`, `output_tokens`, `cost_usd`: Token accounting and estimated cost.
- `input`: Prompts and messages (unless disabled or redacted).
- `output`: Generated completions and tool calls (unless disabled or redacted).
- `error_type`, `error_message`, `error_stack`: Failure diagnostics (when calls fail).

Your AgentLens API key is sent in the `Authorization: Bearer <key>` header and is never included in the payload. Provider API keys (e.g. OpenAI / Anthropic keys) are never transmitted.

### Configuring Prompt & Completion Capture
You can disable capture of prompts or completions globally:

```python
al.init(
    api_key="al_live_...",
    capture_prompts=False,       # Omit prompt/input contents entirely
    capture_completions=False,   # Omit completion/output contents entirely
)
```
Or via environment variables:
```bash
export AGENTLENS_CAPTURE_PROMPTS=false
export AGENTLENS_CAPTURE_COMPLETIONS=false
```

### Field-Level Redaction
You can specify sensitive keys (e.g., passwords, tokens, PII) to automatically mask as `"[REDACTED]"` in all nested inputs, outputs, error messages, and metadata:

```python
al.init(
    api_key="al_live_...",
    redact_fields=["password", "secret", "token", "ssn", "api_key"],
    # Optional custom redaction callable: (key, value) -> sanitized_value
    redact_fn=lambda key, val: "***" if "secret" in key.lower() else val,
)
```
Or via environment variable:
```bash
export AGENTLENS_REDACT_FIELDS="password,token,secret,credit_card"
```

---

## Public API Reference

### `al.init(...) -> AgentLensClient`
Configures the global AgentLens client, spins up the thread-safe background ingestion worker, and registers an `atexit` hook to flush remaining spans on application termination.
- `api_key`: Your active AgentLens project API key (prefixed with `al_live_`).
- `base_url`: Endpoint of your FastAPI backend (default: `http://localhost:8000`).
- `debug`: Enable internal logging for SDK debugging.
- `enabled`: If set to `False`, all tracing operations, monkey-patches, and decorators gracefully fallback to no-ops.
- `capture_inputs` / `capture_prompts`: Set to `False` to omit prompts and input payloads (default: `True`).
- `capture_outputs` / `capture_completions`: Set to `False` to omit generated completions and outputs (default: `True`).
- `redact_fields`: List of case-insensitive field names to redact as `"[REDACTED]"`.
- `redact_fn`: Optional callable `(key, value) -> redacted_value` for custom value masking.

### `al.trace(name: str | None = None, tags: list[str] | None = None)`
Decorator to declare a new root trace context. Propagates the trace context down the execution tree.

### `al.span(name: str, span_type: str = "custom")`
Context manager to record a logical sub-step inside an active trace context. Supports updating metadata and final outputs.

### `al.flush(timeout: float = 5.0) -> None`
Manually blocks and flushes any enqueued spans to the API backend up to the specified timeout. Excellent for short-running serverless function environments.
