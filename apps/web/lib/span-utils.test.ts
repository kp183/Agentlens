import test from "node:test";
import assert from "node:assert/strict";
import { isSpanRunning, formatDuration, getGanttMetrics } from "./span-utils";

test("0ms finished span is not marked as running and displays <1ms", () => {
  const span = {
    started_at: "2026-11-04T10:00:00.000Z",
    ended_at: "2026-11-04T10:00:00.000Z",
    duration_ms: 0,
    status: "success",
  };

  assert.equal(isSpanRunning(span), false);
  assert.equal(formatDuration(span), "<1ms");
});

test("sub-millisecond finished span displays <1ms", () => {
  const span = {
    started_at: "2026-11-04T10:00:00.000Z",
    ended_at: "2026-11-04T10:00:00.000Z",
    duration_ms: 0.4,
    status: "success",
  };

  assert.equal(isSpanRunning(span), false);
  assert.equal(formatDuration(span), "<1ms");
});

test("span with no end/finish info is decided as running", () => {
  const span = {
    started_at: "2026-11-04T10:00:00.000Z",
    status: "running",
  };

  assert.equal(isSpanRunning(span), true);
  assert.equal(formatDuration(span), "running");
});

test("span with error status and duration 0 is not running", () => {
  const span = {
    started_at: "2026-11-04T10:00:00.000Z",
    duration_ms: 0,
    status: "error",
  };

  assert.equal(isSpanRunning(span), false);
  assert.equal(formatDuration(span), "<1ms");
});

test("normal duration formats with ms suffix", () => {
  const span = {
    started_at: "2026-11-04T10:00:00.000Z",
    ended_at: "2026-11-04T10:00:00.045Z",
    duration_ms: 45,
    status: "success",
  };

  assert.equal(isSpanRunning(span), false);
  assert.equal(formatDuration(span), "45ms");
});

test("Gantt metrics gives 0ms span a minimum visible width of at least 2%", () => {
  const span = {
    started_at: "2026-11-04T10:00:00.000Z",
    ended_at: "2026-11-04T10:00:00.000Z",
    duration_ms: 0,
    status: "success",
  };

  const metrics = getGanttMetrics(span, "2026-11-04T10:00:00.000Z", 1000);
  assert.equal(metrics.left, 0);
  assert.ok(metrics.width >= 2, `Expected width >= 2, got ${metrics.width}`);
});
