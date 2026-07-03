"""Trace query service — cursor pagination, detail, span tree reconstruction."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.span import Span
from app.models.trace import Trace
from app.schemas.traces import SpanDiff, SpanNode, TraceDiffResult, TraceListItem


# ---------------------------------------------------------------------------
# Cursor encoding / decoding
# ---------------------------------------------------------------------------

def encode_cursor(started_at: datetime, trace_id: uuid.UUID) -> str:
    """Encode a pagination cursor as base64-urlsafe JSON.

    Format: base64url({"t": "<iso>", "i": "<uuid>"})
    """
    payload = {"t": started_at.isoformat(), "i": str(trace_id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode a pagination cursor back to (started_at, trace_id).

    Raises ValueError on malformed input.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        data = json.loads(raw)
        started_at = datetime.fromisoformat(data["t"])
        trace_id = uuid.UUID(data["i"])
        return started_at, trace_id
    except Exception as exc:
        raise ValueError(f"Invalid cursor: {exc}") from exc


# ---------------------------------------------------------------------------
# Trace list (paginated)
# ---------------------------------------------------------------------------

async def list_traces(
    session: AsyncSession,
    project_id: uuid.UUID,
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
    model: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> tuple[list[Trace], str | None]:
    """Return a page of traces for *project_id* and the next cursor.

    Uses the composite index ``idx_traces_project_started`` for efficient
    keyset pagination on (started_at DESC, id DESC).
    """
    stmt = (
        select(Trace)
        .where(Trace.project_id == project_id)
        .order_by(Trace.started_at.desc(), Trace.id.desc())
        .limit(limit + 1)  # fetch one extra to detect next page
    )

    if cursor:
        cursor_started_at, cursor_id = decode_cursor(cursor)
        stmt = stmt.where(
            (Trace.started_at < cursor_started_at)
            | (
                (Trace.started_at == cursor_started_at)
                & (Trace.id < cursor_id)
            )
        )

    if status:
        stmt = stmt.where(Trace.status == status)
    if model:
        stmt = stmt.where(Trace.model == model)
    if start_date:
        stmt = stmt.where(Trace.started_at >= start_date)
    if end_date:
        stmt = stmt.where(Trace.started_at <= end_date)

    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = encode_cursor(last.started_at, last.id)

    return rows, next_cursor


# ---------------------------------------------------------------------------
# Trace detail
# ---------------------------------------------------------------------------

async def get_trace(
    session: AsyncSession,
    trace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Trace | None:
    """Return a single trace, enforcing project ownership."""
    result = await session.execute(
        select(Trace).where(
            Trace.id == trace_id,
            Trace.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Span tree reconstruction
# ---------------------------------------------------------------------------

async def get_span_tree(
    session: AsyncSession,
    trace_id: uuid.UUID,
) -> list[SpanNode]:
    """Fetch all spans for *trace_id* and build a parent-child tree.

    Returns root spans (parent_span_id IS NULL) at the top level.
    Each span's ``children`` list contains direct children ordered by started_at.
    """
    result = await session.execute(
        select(Span)
        .where(Span.trace_id == trace_id)
        .order_by(Span.started_at.asc())
    )
    spans = list(result.scalars().all())

    # Build SpanNode map
    nodes: dict[uuid.UUID, SpanNode] = {}
    for span in spans:
        nodes[span.id] = SpanNode(
            id=span.id,
            trace_id=span.trace_id,
            parent_span_id=span.parent_span_id,
            name=span.name,
            span_type=span.span_type,
            status=span.status,
            started_at=span.started_at,
            ended_at=span.ended_at,
            duration_ms=span.duration_ms,
            model=span.model,
            provider=span.provider,
            input_tokens=span.input_tokens,
            output_tokens=span.output_tokens,
            cost_usd=float(span.cost_usd) if span.cost_usd is not None else None,
            tool_name=span.tool_name,
            tool_call_id=span.tool_call_id,
            input=span.input,
            output=span.output,
            metadata=span.metadata_,
            tags=span.tags,
            error_type=span.error_type,
            error_message=span.error_message,
            error_stack=span.error_stack,
        )

    # Wire children
    roots: list[SpanNode] = []
    for node in nodes.values():
        if node.parent_span_id is None:
            roots.append(node)
        elif node.parent_span_id in nodes:
            nodes[node.parent_span_id].children.append(node)

    # Sort children by started_at
    def _sort_children(node: SpanNode) -> None:
        node.children.sort(key=lambda c: c.started_at)
        for child in node.children:
            _sort_children(child)

    roots.sort(key=lambda r: r.started_at)
    for root in roots:
        _sort_children(root)

    return roots


# ---------------------------------------------------------------------------
# Trace diffing
# ---------------------------------------------------------------------------

async def diff_traces(
    session: AsyncSession,
    base_trace_id: uuid.UUID,
    target_trace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> TraceDiffResult | None:
    """Compare two traces side-by-side and calculate delta metrics and span-level diffs."""
    base_trace = await get_trace(session, base_trace_id, project_id)
    target_trace = await get_trace(session, target_trace_id, project_id)

    if not base_trace or not target_trace:
        return None

    # Fetch flat spans for both traces
    base_result = await session.execute(
        select(Span).where(Span.trace_id == base_trace_id).order_by(Span.started_at.asc())
    )
    base_spans = list(base_result.scalars().all())

    target_result = await session.execute(
        select(Span).where(Span.trace_id == target_trace_id).order_by(Span.started_at.asc())
    )
    target_spans = list(target_result.scalars().all())

    def _to_span_node(s: Span) -> SpanNode:
        return SpanNode(
            id=s.id,
            trace_id=s.trace_id,
            parent_span_id=s.parent_span_id,
            name=s.name,
            span_type=s.span_type,
            status=s.status,
            started_at=s.started_at,
            ended_at=s.ended_at,
            duration_ms=s.duration_ms,
            model=s.model,
            provider=s.provider,
            input_tokens=s.input_tokens,
            output_tokens=s.output_tokens,
            cost_usd=float(s.cost_usd) if s.cost_usd is not None else None,
            tool_name=s.tool_name,
            tool_call_id=s.tool_call_id,
            input=s.input,
            output=s.output,
            metadata=s.metadata_,
            tags=s.tags,
            error_type=s.error_type,
            error_message=s.error_message,
            error_stack=s.error_stack,
        )

    base_nodes = [_to_span_node(s) for s in base_spans]
    target_nodes = [_to_span_node(s) for s in target_spans]

    base_by_key: dict[tuple[str, str], list[SpanNode]] = {}
    for n in base_nodes:
        base_by_key.setdefault((n.name, n.span_type), []).append(n)

    target_by_key: dict[tuple[str, str], list[SpanNode]] = {}
    for n in target_nodes:
        target_by_key.setdefault((n.name, n.span_type), []).append(n)

    all_keys = list(dict.fromkeys(list(base_by_key.keys()) + list(target_by_key.keys())))
    span_diffs: list[SpanDiff] = []

    for key in all_keys:
        b_list = base_by_key.get(key, [])
        t_list = target_by_key.get(key, [])

        max_len = max(len(b_list), len(t_list))
        for i in range(max_len):
            b_span = b_list[i] if i < len(b_list) else None
            t_span = t_list[i] if i < len(t_list) else None

            if b_span and not t_span:
                span_diffs.append(
                    SpanDiff(
                        name=key[0],
                        span_type=key[1],
                        change_type="removed",
                        base_span=b_span,
                        target_span=None,
                        status_change=[b_span.status, None],
                        duration_diff_ms=-(b_span.duration_ms or 0),
                        cost_diff_usd=-(b_span.cost_usd or 0.0),
                    )
                )
            elif t_span and not b_span:
                span_diffs.append(
                    SpanDiff(
                        name=key[0],
                        span_type=key[1],
                        change_type="added",
                        base_span=None,
                        target_span=t_span,
                        status_change=[None, t_span.status],
                        duration_diff_ms=t_span.duration_ms or 0,
                        cost_diff_usd=t_span.cost_usd or 0.0,
                    )
                )
            elif b_span and t_span:
                dur_diff = (t_span.duration_ms or 0) - (b_span.duration_ms or 0)
                cost_diff = (t_span.cost_usd or 0.0) - (b_span.cost_usd or 0.0)
                status_chg = [b_span.status, t_span.status] if b_span.status != t_span.status else None

                is_modified = status_chg is not None or dur_diff != 0 or round(cost_diff, 6) != 0.0 or b_span.input != t_span.input or b_span.output != t_span.output

                span_diffs.append(
                    SpanDiff(
                        name=key[0],
                        span_type=key[1],
                        change_type="modified" if is_modified else "unchanged",
                        base_span=b_span,
                        target_span=t_span,
                        status_change=status_chg,
                        duration_diff_ms=dur_diff,
                        cost_diff_usd=cost_diff,
                    )
                )

    duration_diff_ms = (target_trace.duration_ms or 0) - (base_trace.duration_ms or 0)
    cost_diff_usd = (target_trace.total_cost_usd or 0.0) - (base_trace.total_cost_usd or 0.0)
    total_tokens_diff = (target_trace.total_tokens or 0) - (base_trace.total_tokens or 0)
    span_count_diff = target_trace.span_count - base_trace.span_count

    return TraceDiffResult(
        base_trace=TraceListItem.model_validate(base_trace),
        target_trace=TraceListItem.model_validate(target_trace),
        duration_diff_ms=duration_diff_ms,
        cost_diff_usd=cost_diff_usd,
        total_tokens_diff=total_tokens_diff,
        span_count_diff=span_count_diff,
        span_diffs=span_diffs,
    )
