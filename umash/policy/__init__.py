"""Deterministic policy layer.

Everything safety-critical lives here as plain Python, NOT as model output:
phase ordering, consequence tiers, the batch-vs-escalate decision, deadlines,
and jurisdiction packs. The agent calls into this; it never overrides it.
"""

from .phases import Phase, PHASE_ORDER, phase_of_task
from .consequence import Consequence, classify, is_escalation, ROUTINE, WEIGHTY
from .jurisdictions import (
    Jurisdiction,
    get_pack,
    supported_jurisdictions,
    tasks_for,
)
from .casestate import CaseState, TaskState, Status, InvalidTransition
from .drafting import build_draft


def build_case(case_id: str, died_in, rest_in=None,
               deceased_name: str = "the deceased") -> CaseState:
    """Build a populated CaseState from the jurisdiction packs.

    This is where the stateless policy (tasks_for + classify) becomes a stateful,
    persistable case the family works over time. Each task is classified once and
    its weighty/routine verdict is frozen into the case.
    """
    cs = CaseState(case_id, str(died_in), str(rest_in) if rest_in else None,
                   deceased_name)
    for t in tasks_for(died_in, rest_in):
        v = classify(t.title, t.deadline_days)
        cs.add_task(title=t.title, phase=t.phase.value, target=t.target,
                    weighty=v.escalates, deadline_days=t.deadline_days)
    return cs


__all__ = [
    "Phase",
    "PHASE_ORDER",
    "phase_of_task",
    "Consequence",
    "classify",
    "is_escalation",
    "ROUTINE",
    "WEIGHTY",
    "Jurisdiction",
    "get_pack",
    "supported_jurisdictions",
    "tasks_for",
    "CaseState",
    "TaskState",
    "Status",
    "InvalidTransition",
    "build_case",
    "build_draft",
]
