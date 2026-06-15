import urllib.request
import json
import uuid
from datetime import datetime, timezone

# 1. Configuration
API_KEY = "local-dev-key"
INGEST_URL = "http://localhost:8000/v1/ingest"

# 2. Construct simulated nested span payloads
trace_id = str(uuid.uuid4())
root_span_id = str(uuid.uuid4())
classification_span_id = str(uuid.uuid4())
db_span_id = str(uuid.uuid4())
synthesis_span_id = str(uuid.uuid4())

print(f"Simulating live agent trace ID: {trace_id}...")

spans = [
    # Root Agent Span
    {
        "id": root_span_id,
        "trace_id": trace_id,
        "parent_span_id": None,
        "name": "Live Support Orchestrator",
        "span_type": "agent",
        "status": "success",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
    },
    # Child LLM Call 1: Intent Classification (gpt-4o-mini)
    {
        "id": classification_span_id,
        "trace_id": trace_id,
        "parent_span_id": root_span_id,
        "name": "Intent Classification (gpt-4o-mini)",
        "span_type": "llm",
        "status": "success",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "model": "gpt-4o-mini",
        "provider": "openai",
        "input_tokens": 400,
        "output_tokens": 150,
        "cost_usd": 0.00015, # Automatically aggregated in DB
        "input": {"messages": [{"role": "user", "content": "Help me reset my password."}]},
        "output": {"choices": [{"message": {"role": "assistant", "content": "Intent: Auth-Reset"}}]},
    },
    # Child Tool Call 2: DB Lookup
    {
        "id": db_span_id,
        "trace_id": trace_id,
        "parent_span_id": root_span_id,
        "name": "VectorDB Query",
        "span_type": "tool",
        "status": "success",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {"query_type": "hybrid", "limit": 3},
    },
    # Child LLM Call 3: Response Synthesis (gpt-4o)
    {
        "id": synthesis_span_id,
        "trace_id": trace_id,
        "parent_span_id": root_span_id,
        "name": "Generate Synthesis (gpt-4o)",
        "span_type": "llm",
        "status": "success",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "model": "gpt-4o",
        "provider": "openai",
        "input_tokens": 1800,
        "output_tokens": 450,
        "cost_usd": 0.009, # Automatically aggregated in DB
        "input": {"messages": [{"role": "user", "content": "Generate secure reset link"}]},
        "output": {"choices": [{"message": {"role": "assistant", "content": "Reset link generated successfully."}}]},
    }
]

# 3. Compile request payload
payload = json.dumps({"spans": spans}).encode("utf-8")

# 4. Perform HTTP POST request
req = urllib.request.Request(
    INGEST_URL,
    data=payload,
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(req) as response:
        res_body = response.read().decode("utf-8")
        print("\nSUCCESS! INGESTION RESPONSE:")
        print(json.dumps(json.loads(res_body), indent=2))
except Exception as e:
    print(f"\nError sending trace: {e}")
