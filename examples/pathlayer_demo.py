"""AgentLens + Pathlayer Loop Guardrail Integration Demo.

Demonstrates runtime loop detection via Pathlayer with full observability
in AgentLens. Replays Pathlayer's demo_loop scenario: an agent repeating
alternating file inspection calls without progressing is stopped cleanly.
Each tool event is traced as an AgentLens span, and Pathlayer's post-mortem
is captured in a final pathlayer:STOP span.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import agentlens as al
from pathlayer import Pipeline
from pathlayer.detectors.loop import LoopDetector
from pathlayer.events import ToolEvent
from pathlayer.policies import Action, Actuator, wire
from pathlayer.postmortem import PostMortem


@dataclass
class RunControl:
    """Cooperative drain flag toggled by Pathlayer Actuator."""

    stopped: bool = False
    reason: str = ""


class DemoActuator(Actuator):
    """Actuator that requests a cooperative drain on Action.STOP."""

    def __init__(self, control: RunControl) -> None:
        self._control = control

    def apply(self, action: Action, post_mortem: PostMortem | None) -> None:
        if action is not Action.STOP:
            return
        self._control.stopped = True
        self._control.reason = post_mortem.reason if post_mortem is not None else "stop"


def looping_agent() -> Iterator[ToolEvent]:
    """Agent stuck in a loop alternating list_dir and read_file on src/main.py."""
    step = 0
    while True:
        for tool in ("list_dir", "read_file"):
            yield ToolEvent(tool=tool, args={"path": "src/main.py"}, ts=float(step))
            step += 1


def _triggering_detector(pm: PostMortem) -> str:
    if not pm.signals:
        return "?"
    return max(pm.signals, key=lambda s: s.confidence).name


@al.trace(name="Pathlayer Loop Demo")
def run_loop_scenario() -> tuple[Pipeline, RunControl]:
    """Execute looping agent guarded by Pathlayer, tracing each step in AgentLens."""
    pipeline = Pipeline([LoopDetector()])
    control = RunControl()
    sink = wire(pipeline, DemoActuator(control))

    for event in looping_agent():
        # Handle each tool event inside an AgentLens span (name = tool name, input = args)
        with al.span(name=event.tool, span_type="tool") as s:
            s.set_input(event.args)
            sink(event)
            s.set_output({"status": "executed"})

        if control.stopped:
            break

    # When Pathlayer's STOP fires, record post-mortem in a final span
    if control.stopped and pipeline.post_mortem is not None:
        pm = pipeline.post_mortem
        with al.span(name="pathlayer:STOP", span_type="custom") as s:
            s.set_output({
                "reason": pm.reason,
                "triggering_detector": _triggering_detector(pm),
                "action_index": pm.stopped_at_index + 1,
                "events_processed": pm.events_processed,
            })

    return pipeline, control


def main() -> None:
    print("=" * 60)
    print("AgentLens + Pathlayer Integration Demo")
    print("=" * 60)

    # Initialize AgentLens SDK
    client = al.init(api_key="local-dev-key", base_url="http://localhost:8000")

    pipeline, control = run_loop_scenario()
    
    # Flush buffered spans and wait for background worker thread to finish ingestion
    al.flush()
    if client is not None:
        client.stop()

    pm = pipeline.post_mortem
    if pm is not None:
        print(f"\n[Pathlayer] STOP triggered after {pm.events_processed} actions.")
        print(f"  Reason:              {pm.reason}")
        print(f"  Triggering detector: {_triggering_detector(pm)}")
        print(f"  Stopped at action:   {pm.stopped_at_index + 1}")
        print(f"  Drain requested:     {control.stopped}")
    else:
        print("\n[Pathlayer] No intervention triggered.")

    print("\nTrace successfully ingested into AgentLens at http://localhost:8000")
    print("View visualization at http://localhost:3000\n")


if __name__ == "__main__":
    main()
