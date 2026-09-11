"""Draft text generation — deterministic, no model, no Strands.

Lives in the policy layer (not tools.py) on purpose: drafting a plain notice is
pure string work over the consequence verdict, and the offline product (CLI,
session loop, tests) must run it without importing Strands or touching Bedrock.
tools.py wraps this for the agent; it does not own it.

For weighty tasks the "draft" is deliberately a decision prompt, not a
send-ready letter — Umash will not pre-compose something consequential as if it
were about to go out.
"""

from __future__ import annotations

from .consequence import classify


def build_draft(target: str, task: str,
                deceased_name: str = "the deceased") -> tuple[bool, str]:
    """Return (escalates, draft_text) for a task."""
    v = classify(task)
    if v.escalates:
        draft = (
            f"[NEEDS YOUR DECISION FIRST — not to be sent until you approve]\n\n"
            f"Re: {deceased_name}\n\n"
            f"This concerns: {task}. Because it involves "
            f"{', '.join(r.split(':')[0] for r in v.reasons)}, Umash has not "
            f"drafted a send-ready notice. Here is what it would say once you "
            f"decide how to proceed, {target}."
        )
    else:
        draft = (
            f"To {target},\n\n"
            f"I am writing about {deceased_name}, who has passed away. "
            f"{task.capitalize()}. Please let me know what you need from me to "
            f"complete this, and I will provide it.\n\n"
            f"Thank you for your understanding at this difficult time.\n"
        )
    return v.escalates, draft
