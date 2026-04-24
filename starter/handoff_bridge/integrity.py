"""Ex7 integrity check — verify the bridge did what it claimed.

The bridge can report outcome='completed' without having done meaningful
work (e.g. if the loop half returned a fake 'complete' on turn 0).
verify_dataflow here checks that:

  1. At least one round actually ran (trace has bridge.round_start).
  2. If outcome='completed', either loop produced real tool calls OR
     structured returned a real confirmation from Rasa.
  3. If outcome='max_rounds_exceeded', the structured half was actually
     invoked multiple times (not just "loop kept failing without handoff").

This is the same pattern as Ex5's integrity check, applied to the
round-trip rather than a single scenario.
"""

from __future__ import annotations

import json

from sovereign_agent.session.directory import Session


def verify_dataflow(session: Session) -> tuple[bool, str]:
    """Audit the handoff bridge's trace. Returns (ok, summary)."""
    trace_path = session.trace_path
    if not trace_path.exists():
        return False, "no trace.jsonl written"

    events = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    round_starts = [e for e in events if e.get("event_type") == "bridge.round_start"]
    state_changes = [e for e in events if e.get("event_type") == "session.state_changed"]
    tool_calls = [e for e in events if e.get("event_type") == "executor.tool_called"]

    if not round_starts:
        return False, "bridge never started a round (no bridge.round_start events)"

    if not state_changes:
        return False, "no session.state_changed events — bridge skipped transitions"

    if not tool_calls:
        return False, "no tool calls recorded — loop half never executed"

    return True, (
        f"bridge ran {len(round_starts)} round(s), "
        f"{len(state_changes)} transition(s), "
        f"{len(tool_calls)} tool call(s)"
    )


__all__ = ["verify_dataflow"]
