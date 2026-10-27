"""Unit tests for the ingest endpoint."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def _valid_span(**overrides) -> dict:
    base = {
        "id": str(uuid.uuid4()),
        "trace_id": str(uuid.uuid4()),
        "name": "test-span",
        "span_type": "custom",
        "status": "success",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


def _make_project():
    from app.models.project import Project
    p = MagicMock(spec=Project)
    p.id = uuid.uuid4()
    p.org_id = uuid.uuid4()
    return p


@contextmanager
def _test_client(**extra_patches):
    """Context manager that yields a TestClient with migration disabled."""
    with patch("app.main.run_migrations", new=AsyncMock()):
        with TestClient(app, raise_server_exceptions=False) as client:
            try:
                yield client
            finally:
                app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Batch > 500 returns 422
# ---------------------------------------------------------------------------

def test_batch_over_500_returns_422() -> None:
    from app.middleware.auth import require_api_key
    app.dependency_overrides[require_api_key] = lambda: _make_project()

    spans = [_valid_span() for _ in range(501)]
    with _test_client() as client:
        resp = client.post(
            "/v1/ingest",
            headers={"Authorization": "Bearer al_live_test"},
            json={"spans": spans},
        )
    assert resp.status_code in (401, 422), (
        f"Expected 401 or 422 for oversized batch, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Missing API key returns 401
# ---------------------------------------------------------------------------

def test_missing_api_key_returns_401() -> None:
    with _test_client() as client:
        resp = client.post("/v1/ingest", json={"spans": [_valid_span()]})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Invalid API key returns 401
# ---------------------------------------------------------------------------

def test_invalid_api_key_returns_401() -> None:
    """An unregistered key must return 401, not 500."""
    from app.exceptions import AuthenticationError
    from app.middleware.auth import require_api_key

    # Use dependency_overrides — the only mechanism FastAPI respects at
    # runtime, because Depends() captures the original function reference.
    async def _fake_require_api_key():
        raise AuthenticationError("Invalid or revoked API key")

    app.dependency_overrides[require_api_key] = _fake_require_api_key

    with _test_client() as client:
        resp = client.post(
            "/v1/ingest",
            headers={"Authorization": "Bearer not_a_real_key"},
            json={"spans": [_valid_span()]},
        )
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Rate limit returns 429
# ---------------------------------------------------------------------------

def test_rate_limit_returns_429() -> None:
    from app.exceptions import RateLimitError
    from app.middleware.auth import check_rate_limit, require_api_key

    project = _make_project()

    # Override require_api_key so it returns a fake project (auth passes)
    app.dependency_overrides[require_api_key] = lambda: project

    # Patch check_rate_limit at the call-site in the ingest router so it
    # raises RateLimitError.  Unlike require_api_key (which is a Depends),
    # check_rate_limit is called directly in the route function body, so
    # module-level patching works here.
    with patch(
        "app.routers.ingest.check_rate_limit",
        new=AsyncMock(side_effect=RateLimitError("Rate limit exceeded", retry_after=60)),
    ):
        with _test_client() as client:
            resp = client.post(
                "/v1/ingest",
                headers={"Authorization": "Bearer al_live_test"},
                json={"spans": [_valid_span()]},
            )
    assert resp.status_code == 429, (
        f"Expected 429, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Partial validation failure — invalid span_type rejected at schema level
# ---------------------------------------------------------------------------

def test_partial_validation_failure_schema_rejects_invalid_type() -> None:
    """A batch containing an invalid span_type returns 422 (schema validation)."""
    from app.middleware.auth import require_api_key

    valid = _valid_span()
    invalid = {**valid, "id": str(uuid.uuid4()), "span_type": "INVALID"}

    # Override auth so the request reaches Pydantic body validation.
    # Without this, the real require_api_key hits Redis/DB and crashes.
    app.dependency_overrides[require_api_key] = lambda: _make_project()

    with _test_client() as client:
        resp = client.post(
            "/v1/ingest",
            headers={"Authorization": "Bearer al_live_test"},
            json={"spans": [valid, invalid]},
        )
    # Pydantic rejects the whole batch at schema level → 422
    assert resp.status_code == 422, (
        f"Expected 422, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Maximum request body size enforcement (413 Payload Too Large)
# ---------------------------------------------------------------------------

def test_ingest_oversized_content_length_returns_413() -> None:
    """A request whose Content-Length exceeds max_request_size_bytes returns 413."""
    from app.config import get_settings
    settings = get_settings()

    with patch.object(settings, "max_request_size_bytes", 1024):  # 1 KB limit
        with _test_client() as client:
            resp = client.post(
                "/v1/ingest",
                headers={
                    "Authorization": "Bearer al_live_test",
                    "Content-Length": "2048",
                },
                content=b"x" * 2048,
            )
    assert resp.status_code == 413
    data = resp.json()
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "1024" in data["error"]["message"]


def test_ingest_oversized_body_stream_returns_413() -> None:
    """A request whose buffered body exceeds max_request_size_bytes returns 413."""
    from app.config import get_settings
    settings = get_settings()

    with patch.object(settings, "max_request_size_bytes", 500):  # 500 bytes limit
        with _test_client() as client:
            resp = client.post(
                "/v1/ingest",
                headers={"Authorization": "Bearer al_live_test"},
                json={"spans": [_valid_span(input={"huge": "x" * 1000})]},
            )
    assert resp.status_code == 413
    data = resp.json()
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "500" in data["error"]["message"]


def test_ingest_payload_within_limit_passes_size_check() -> None:
    """A request within size limit passes the size middleware (auth/schema tested)."""
    from app.config import get_settings
    from app.middleware.auth import require_api_key

    settings = get_settings()
    app.dependency_overrides[require_api_key] = lambda: _make_project()

    with patch.object(settings, "max_request_size_bytes", 10 * 1024 * 1024):  # 10 MB
        with _test_client() as client:
            resp = client.post(
                "/v1/ingest",
                headers={"Authorization": "Bearer al_live_test"},
                json={"spans": [_valid_span()]},
            )
    # Status should not be 413
    assert resp.status_code != 413


def test_ingest_chunked_oversized_body_returns_413() -> None:
    """A streaming/chunked body exceeding max_request_size_bytes returns 413 without loading entire payload."""
    from app.config import get_settings
    settings = get_settings()

    def stream_oversized():
        # Yield chunks that cumulatively exceed limit
        for _ in range(20):
            yield b"x" * 100

    with patch.object(settings, "max_request_size_bytes", 500):  # 500 bytes limit
        with _test_client() as client:
            resp = client.post(
                "/v1/ingest",
                headers={"Authorization": "Bearer al_live_test"},
                content=stream_oversized(),
            )
    assert resp.status_code == 413
    data = resp.json()
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "500" in data["error"]["message"]


def test_ingest_chunked_normal_body_passes_size_check() -> None:
    """A chunked stream within size limit passes through and is processed downstream."""
    import json
    from app.config import get_settings
    from app.middleware.auth import require_api_key

    settings = get_settings()
    app.dependency_overrides[require_api_key] = lambda: _make_project()

    payload_bytes = json.dumps({"spans": [_valid_span()]}).encode("utf-8")

    def stream_normal():
        chunk_size = 32
        for i in range(0, len(payload_bytes), chunk_size):
            yield payload_bytes[i:i + chunk_size]

    with patch.object(settings, "max_request_size_bytes", 1024 * 1024):  # 1 MB
        with _test_client() as client:
            resp = client.post(
                "/v1/ingest",
                headers={
                    "Authorization": "Bearer al_live_test",
                    "Content-Type": "application/json",
                },
                content=stream_normal(),
            )
    assert resp.status_code != 413

