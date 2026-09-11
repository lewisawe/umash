"""The six Strands tools.

These are thin wrappers over the deterministic policy layer. The agent reasons
about ordering, tone, and what to say to the human; the *decisions that matter*
(phase, consequence, escalate-vs-batch, deadlines, jurisdiction steps) come from
`umash.policy`, not from the model. draft_notice is the only tool that produces
free text, and it still never sends anything.
"""

from __future__ import annotations

import json

from strands import tool

from .policy import (
    Consequence,
    classify,
    phase_of_task,
    tasks_for,
    supported_jurisdictions,
    build_draft,
)
from .policy.phases import PHASE_LABEL, Phase


@tool
def build_journey_plan(died_in: str, rest_in: str = "") -> str:
    """Build the full phased task plan for a death, adapted to jurisdiction.

    Args:
        died_in: ISO-ish country code where the death occurred (KE, UK, US).
        rest_in: country code where the person will be laid to rest. If it
            differs from died_in, cross-border repatriation steps are added.

    Returns:
        JSON: {phases: [{phase, label, tasks: [{title, target, deadline_days,
        consequence, escalates, note}]}]}, tasks grouped and ordered by phase.
    """
    rest = rest_in.strip() or None
    tasks = tasks_for(died_in, rest)

    grouped: dict[str, list[dict]] = {p.value: [] for p in Phase}
    for t in tasks:
        v = classify(t.title, t.deadline_days)
        grouped[t.phase.value].append({
            "title": t.title,
            "target": t.target,
            "deadline_days": t.deadline_days,
            "consequence": v.consequence.value,
            "escalates": v.escalates,
            "note": t.note,
        })

    out = {"died_in": died_in.upper(),
           "rest_in": (rest.upper() if rest else died_in.upper()),
           "cross_border": bool(rest and rest.upper() != died_in.upper()),
           "phases": []}
    for p in Phase:
        out["phases"].append({
            "phase": p.value,
            "label": PHASE_LABEL[p],
            "tasks": grouped[p.value],
        })
    return json.dumps(out, indent=2)


@tool
def classify_phase(task: str) -> str:
    """Return which journey phase a free-text task belongs to.

    Args:
        task: a task description, e.g. "register the death".

    Returns:
        one of: immediate, funeral, admin.
    """
    return phase_of_task(task).value


@tool
def classify_consequence(task: str, deadline_days: int = -1) -> str:
    """Classify a task's consequence and whether it must be escalated to the human.

    Weighty = money / legal / irreversible / time-critical -> escalate, one at a
    time, never auto-execute. Routine = reversible, low-stakes -> batch for one
    approval.

    Args:
        task: the task description.
        deadline_days: days until a hard deadline, or -1 if none.

    Returns:
        JSON: {consequence, escalates, reasons, deadline_days}.
    """
    dl = None if deadline_days is None or deadline_days < 0 else deadline_days
    v = classify(task, dl)
    return json.dumps({
        "consequence": v.consequence.value,
        "escalates": v.escalates,
        "reasons": v.reasons,
        "deadline_days": v.deadline_days,
    })


def build_draft(target: str, task: str, deceased_name: str = "the deceased") -> tuple[bool, str]:
    """Deprecated shim. The real implementation lives in umash.policy.drafting
    so the offline product needs no Strands. Kept as a re-export for any caller
    that imported it from here."""
    from .policy.drafting import build_draft as _bd
    return _bd(target, task, deceased_name)


@tool
def draft_notice(target: str, task: str, deceased_name: str = "the deceased") -> str:
    """Draft a caring, plain notice/letter for a task. NEVER sends it.

    Produces a short, human, non-corporate draft the survivor can review and
    send themselves. For weighty tasks the draft is explicitly marked as needing
    the human's decision first.

    Args:
        target: who the notice is for (e.g. "the bank", "employer").
        task: the task this notice serves.
        deceased_name: name to use, defaults to "the deceased".

    Returns:
        JSON: {target, task, escalates, draft}.
    """
    escalates, draft = build_draft(target, task, deceased_name)
    return json.dumps({"target": target, "task": task,
                       "escalates": escalates, "draft": draft})


@tool
def schedule_followup(task: str, deadline_days: int = -1) -> str:
    """Record a follow-up so slow institutions don't fall through the cracks.

    Args:
        task: the task to follow up on.
        deadline_days: days until it must be chased, or -1 to use a default.

    Returns:
        JSON: {task, follow_up_in_days, escalates_if_missed}.
    """
    dl = 14 if deadline_days is None or deadline_days < 0 else deadline_days
    v = classify(task, dl)
    return json.dumps({
        "task": task,
        "follow_up_in_days": dl,
        "escalates_if_missed": v.escalates,
    })


@tool
def track_confirmation(task: str, acknowledged: bool = False) -> str:
    """Track whether an institution acknowledged a notice; flag silent ones.

    Args:
        task: the task/notice being tracked.
        acknowledged: True if the institution has confirmed receipt.

    Returns:
        JSON: {task, status, needs_resurface}.
    """
    status = "acknowledged" if acknowledged else "awaiting_response"
    return json.dumps({
        "task": task,
        "status": status,
        "needs_resurface": not acknowledged,
    })


ALL_TOOLS = [
    build_journey_plan,
    classify_phase,
    classify_consequence,
    draft_notice,
    schedule_followup,
    track_confirmation,
]
