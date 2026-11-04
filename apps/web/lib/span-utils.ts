/**
 * Utilities for formatting and computing span timing and Gantt metrics.
 */

export interface SpanLike {
  started_at: string;
  ended_at?: string | null;
  duration_ms?: number | null;
  status?: string;
}

/**
 * Determines if a span is currently running.
 * A span is only considered running when it has no end/finish information:
 * - ended_at is not present
 * - status is not "success" or "error"
 * - duration_ms is not present (null or undefined)
 */
export function isSpanRunning(span: Partial<SpanLike>): boolean {
  if (span.ended_at) {
    return false;
  }
  if (span.status === "success" || span.status === "error") {
    return false;
  }
  if (span.duration_ms !== null && span.duration_ms !== undefined) {
    return false;
  }
  return span.status === "running" || !span.ended_at;
}

/**
 * Formats duration for a span.
 * Shows "running" if span is running, "<1ms" for sub-millisecond durations (including 0ms),
 * and "{duration_ms}ms" otherwise.
 */
export function formatDuration(span: Partial<SpanLike>): string {
  if (isSpanRunning(span)) {
    return "running";
  }
  if (span.duration_ms !== null && span.duration_ms !== undefined) {
    if (span.duration_ms < 1) {
      return "<1ms";
    }
    return `${span.duration_ms}ms`;
  }
  return "<1ms";
}

/**
 * Calculates relative Gantt offset and width percentages.
 * Ensures a minimum visible width (at least 2%) for sub-millisecond and 0ms spans.
 */
export function getGanttMetrics(
  span: SpanLike,
  traceStartStr: string,
  traceDurationMs: number | null
): { left: number; width: number } {
  if (!traceStartStr || !traceDurationMs || traceDurationMs <= 0) {
    return { left: 0, width: 100 };
  }

  const traceStart = new Date(traceStartStr).getTime();
  const spanStart = new Date(span.started_at).getTime();

  const offsetMs = Math.max(0, spanStart - traceStart);
  const offsetPercent = (offsetMs / traceDurationMs) * 100;

  let spanDuration = span.duration_ms;
  if (spanDuration === null || spanDuration === undefined) {
    if (isSpanRunning(span)) {
      spanDuration = Math.max(0, Date.now() - spanStart);
    } else {
      spanDuration = 0;
    }
  }

  // Ensure minimum visible width of at least 2%
  const widthPercent = Math.max(2, (spanDuration / traceDurationMs) * 100);
  const left = Math.min(98, offsetPercent);
  const width = Math.min(100 - left, widthPercent);

  return { left, width };
}

