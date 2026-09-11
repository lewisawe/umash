"""The session coordinator — the batch-vs-escalate loop, made real.

`run_offline()` in agent.py produces a static snapshot. This module drives the
actual product behavior over a live `CaseState`:

  1. Prepare every ROUTINE task quietly (draft it) and present them as ONE batch
     the human approves in a single stroke.
  2. Then surface WEIGHTY tasks ONE AT A TIME, most urgent first, each with its
     tradeoffs, and record the human's decision before moving on.

It never sends, files, or pays. Approving a weighty task only records the
decision; the human still acts in the real world and comes back to mark it sent
or confirmed.

The loop is decoupled from I/O via a `Decider` callable, so the same logic runs:
  - interactively (prompt the terminal),
  - scripted (tests / demo, with canned answers),
  - or auto (non-interactive demo that just shows the choreography).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .policy import CaseState, TaskState, build_case, build_draft
from .policy.phases import PHASE_ORDER, PHASE_LABEL, Phase


@dataclass
class Decision:
    """A human's answer to one escalation."""
    approve: bool
    note: str = ""


# A Decider is asked to resolve one weighty task. Returning None means "skip for
# now" (leave it pending). Anything else is a Decision.
Decider = Callable[[TaskState], Optional[Decision]]


def auto_decider(task: TaskState) -> Decision:
    """Non-interactive decider for demos: approves with a recorded rationale so
    the choreography is visible end-to-end without a human at the keyboard."""
    return Decision(approve=True,
                    note="(demo auto-decision — a real family decides here)")


def prompt_decider(task: TaskState) -> Optional[Decision]:
    """Interactive decider: ask the human at the terminal."""
    dl = (f"  ⏰ due in {task.deadline_days} day(s)"
          if task.deadline_days is not None else "  (no fixed deadline)")
    print(f"\n  >> A DECISION IS NEEDED{dl}")
    print(f"     {task.title}")
    print(f"     directed at: {task.target}")
    if task.draft:
        print("     ---")
        for line in task.draft.splitlines():
            print(f"     {line}")
        print("     ---")
    while True:
        ans = input("     Approve / Decline / Skip? [a/d/s]: ").strip().lower()
        if ans in ("a", "approve", "y", "yes"):
            note = input("     Note your decision (optional): ").strip()
            return Decision(True, note or "approved")
        if ans in ("d", "decline", "n", "no"):
            note = input("     Reason (optional): ").strip()
            return Decision(False, note or "declined")
        if ans in ("s", "skip", ""):
            return None
        print("     Please answer a, d, or s.")


class Session:
    """Drives one case through the batch-then-escalate flow over a CaseState."""

    def __init__(self, case: CaseState):
        self.case = case

    @classmethod
    def new(cls, case_id: str, died_in: str, rest_in: str | None,
            deceased_name: str) -> "Session":
        return cls(build_case(case_id, died_in, rest_in, deceased_name))

    # --- step 1: quiet routine drafting ----------------------------------
    def prepare_routine(self) -> list[TaskState]:
        """Draft every routine task quietly. Returns the batch for one approval."""
        prepared = []
        for t in self.case.routine():
            if t.status.value == "pending":
                _, draft = build_draft(t.target, t.title, self.case.deceased_name)
                self.case.record_draft(t.task_id, draft)
            prepared.append(t)
        return prepared

    def approve_routine_batch(self) -> int:
        """Approve the whole routine batch in one stroke. Routine only — weighty
        tasks are never swept into a batch approval, and routine tasks need no
        recorded decision (that's the point of batching them)."""
        n = 0
        for t in self.case.routine():
            if not t.resolved:
                self.case.approve(t.task_id)
                n += 1
        return n

    # --- step 2: escalate weighty, one at a time -------------------------
    def prepare_escalations(self) -> None:
        """Attach a decision-prompt draft to each weighty task."""
        for t in self.case.weighty():
            if not t.draft:
                _, draft = build_draft(t.target, t.title, self.case.deceased_name)
                self.case.record_draft(t.task_id, draft)

    def run_escalations(self, decider: Decider) -> list[dict]:
        """Surface unresolved weighty tasks ONE AT A TIME, most urgent first.

        Each is passed to `decider`; the returned Decision is recorded on the
        case (approved-with-decision or declined). Nothing is sent. Returns a
        log of what happened, in order.
        """
        self.prepare_escalations()
        log = []
        for t in self.case.pending_escalations():
            d = decider(t)
            if d is None:
                log.append({"task_id": t.task_id, "title": t.title,
                            "outcome": "skipped"})
                continue
            if d.approve:
                self.case.approve(t.task_id, d.note or "approved by human")
                log.append({"task_id": t.task_id, "title": t.title,
                            "outcome": "approved", "note": d.note})
            else:
                self.case.decline(t.task_id, d.note)
                log.append({"task_id": t.task_id, "title": t.title,
                            "outcome": "declined", "note": d.note})
        return log

    # --- convenience: the whole flow -------------------------------------
    def run(self, decider: Decider) -> dict:
        """Full flow: draft routine, batch-approve it, then escalate weighty."""
        routine = self.prepare_routine()
        approved = self.approve_routine_batch()
        esc_log = self.run_escalations(decider)
        return {
            "routine_prepared": len(routine),
            "routine_approved": approved,
            "escalations": esc_log,
            "summary": self.case.summary(),
        }

    # --- grouped view for display ----------------------------------------
    def phased_view(self) -> dict:
        phases = {p.value: {"label": PHASE_LABEL[p], "routine": [], "weighty": []}
                  for p in PHASE_ORDER}
        for t in self.case.tasks():
            bucket = "weighty" if t.weighty else "routine"
            phases.setdefault(t.phase, {"label": t.phase, "routine": [], "weighty": []})
            phases[t.phase][bucket].append(t)
        return phases
