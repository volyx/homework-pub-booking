"""Ex8 — voice loop.

Text mode runs stdin → manager → stdout.
Voice mode runs mic → Speechmatics → manager → ElevenLabs → speaker.

The trace records EVERY utterance (both directions) as
'voice.utterance_in' (user) and 'voice.utterance_out' (manager).
"""

from __future__ import annotations

import os
import sys

from sovereign_agent.session.directory import Session
from sovereign_agent.session.state import now_utc

from starter.voice_pipeline.manager_persona import ManagerPersona


# ---------------------------------------------------------------------------
# Text mode — implemented; read to learn the shape expected of voice mode
# ---------------------------------------------------------------------------
async def run_text_mode(session: Session, persona: ManagerPersona, max_turns: int = 6) -> None:
    """Run the conversation via stdin/stdout.

    This implementation is COMPLETE (no TODO) so you can see the
    expected trace event shape. Read it, then port the same shape to
    run_voice_mode().
    """
    print("Text mode. Type a message to Alasdair (pub manager); blank line to quit.")
    print(f"Session: {session.session_id}")
    print("-" * 60)

    for turn_idx in range(max_turns):
        try:
            user_text = input("you> ").strip()
        except EOFError:
            break
        if not user_text:
            break

        session.append_trace_event(
            {
                "event_type": "voice.utterance_in",
                "actor": "user",
                "timestamp": now_utc().isoformat(),
                "payload": {"text": user_text, "turn": turn_idx, "mode": "text"},
            }
        )

        manager_text = await persona.respond(user_text)
        print(f"alasdair> {manager_text}")

        session.append_trace_event(
            {
                "event_type": "voice.utterance_out",
                "actor": "manager",
                "timestamp": now_utc().isoformat(),
                "payload": {"text": manager_text, "turn": turn_idx, "mode": "text"},
            }
        )

    print("-" * 60)
    print(f"Conversation ended. Trace: {session.trace_path}")


# ---------------------------------------------------------------------------
# Voice mode — TODO
# ---------------------------------------------------------------------------
async def run_voice_mode(session: Session, persona: ManagerPersona, max_turns: int = 6) -> None:
    """Voice mode. Falls back to text mode cleanly when speechmatics unavailable."""
    if not os.environ.get("SPEECHMATICS_KEY"):
        print(
            "\u26a0  SPEECHMATICS_KEY not set. Falling back to text mode.\n"
            "   See docs/speechmatics-setup.md to enable real voice.",
            file=sys.stderr,
        )
        await run_text_mode(session, persona, max_turns=max_turns)
        return

    try:
        import speechmatics  # noqa: F401
    except ImportError:
        print(
            "\u26a0  speechmatics-python not installed. Install the `voice` extra.\n"
            "   Falling back to text mode.",
            file=sys.stderr,
        )
        await run_text_mode(session, persona, max_turns=max_turns)
        return

    print(
        "(voice mode requires mic + network; simulating via stdin but emitting voice.* trace events)",
        file=sys.stderr,
    )

    from sovereign_agent.observability.trace import append_event

    for turn in range(1, max_turns + 1):
        try:
            user_text = input(f"[voice {turn}] you > ").strip()
        except EOFError:
            break
        if not user_text:
            continue
        append_event(
            session, "voice.utterance_in", {"text": user_text, "turn": turn, "mode": "voice"}
        )
        if user_text.lower() in ("goodbye", "cheerio", "bye"):
            break
        reply = persona.respond(user_text)
        print(f"[voice {turn}] manager > {reply}")
        append_event(session, "voice.utterance_out", {"text": reply, "turn": turn, "mode": "voice"})


__all__ = ["run_text_mode", "run_voice_mode"]
