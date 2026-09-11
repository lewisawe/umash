"""Persistent case state — the memory of a case.

The rest of the policy layer is stateless: it classifies and orders. But a real
family works a case over days and weeks, so *something* has to remember what has
been drafted, what the human approved, and which institutions went silent. That
memory lives here, as plain data with an explicit lifecycle — not in the model's
context window, which would be lost between sessions and can't be trusted with
safety-critical status.

Task lifecycle:

    PENDING ─▶ DRAFTED ─▶ APPROVED ─▶ SENT ─▶ CONFIRMED
                   │                     │
                   └──────── (weighty: needs a decision first) ───────┘

Weighty tasks cannot move to APPROVED without an explicit human decision being
recorded. That invariant is enforced here in code, not left to the agent.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum


class Status(str, Enum):
    PENDING = "pending"        # known, nothing prepared yet
    DRAFTED = "drafted"        # a notice/plan is prepared, awaiting the human
    APPROVED = "approved"      # human said go (weighty tasks need a decision first)
    SENT = "sent"              # the human sent/filed it themselves (we never do)
    CONFIRMED = "confirmed"    # the institution acknowledged
    DECLINED = "declined"      # human decided not to proceed


# Statuses that mean "the human has dealt with this, stop surfacing it".
_RESOLVED = {Status.APPROVED, Status.SENT, Status.CONFIRMED, Status.DECLINED}


@dataclass
class TaskState:
    task_id: str
    title: str
    phase: str
    target: str
    weighty: bool
    deadline_days: int | None = None
    status: Status = Status.PENDING
    draft: str = ""
    decision: str = ""          # the human's recorded decision, for weighty tasks
    history: list[dict] = field(default_factory=list)

    def _log(self, event: str) -> None:
        self.history.append({"event": event, "at": time.time()})

    @property
    def resolved(self) -> bool:
        return self.status in _RESOLVED

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TaskState":
        d = dict(d)
        d["status"] = Status(d.get("status", "pending"))
        return cls(**d)


class InvalidTransition(Exception):
    """Raised when a status change would violate the safety lifecycle."""


class CaseState:
    """Ordered, persistable collection of task states for one case."""

    def __init__(self, case_id: str, died_in: str, rest_in: str,
                 deceased_name: str = "the deceased"):
        self.case_id = case_id
        self.died_in = died_in.upper()
        self.rest_in = (rest_in or died_in).upper()
        self.deceased_name = deceased_name
        self.cross_border = self.rest_in != self.died_in
        self._tasks: dict[str, TaskState] = {}
        self._order: list[str] = []

    # --- construction -----------------------------------------------------
    def add_task(self, title: str, phase: str, target: str, weighty: bool,
                 deadline_days: int | None = None) -> TaskState:
        task_id = self._make_id(title)
        ts = TaskState(task_id=task_id, title=title, phase=phase, target=target,
                       weighty=weighty, deadline_days=deadline_days)
        ts._log("added")
        self._tasks[task_id] = ts
        self._order.append(task_id)
        return ts

    def _make_id(self, title: str) -> str:
        base = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
        base = "-".join(filter(None, base.split("-")))[:48] or "task"
        tid, n = base, 2
        while tid in self._tasks:
            tid = f"{base}-{n}"
            n += 1
        return tid

    # --- access -----------------------------------------------------------
    def tasks(self) -> list[TaskState]:
        return [self._tasks[i] for i in self._order]

    def get(self, task_id: str) -> TaskState:
        if task_id not in self._tasks:
            raise KeyError(task_id)
        return self._tasks[task_id]

    def routine(self) -> list[TaskState]:
        return [t for t in self.tasks() if not t.weighty]

    def weighty(self) -> list[TaskState]:
        return [t for t in self.tasks() if t.weighty]

    def pending_escalations(self) -> list[TaskState]:
        """Unresolved weighty tasks, most urgent first (soonest deadline wins)."""
        esc = [t for t in self.tasks() if t.weighty and not t.resolved]
        esc.sort(key=lambda t: (t.deadline_days is None,
                                t.deadline_days if t.deadline_days is not None else 10**6))
        return esc

    def unconfirmed(self) -> list[TaskState]:
        """Tasks the human has SENT but no institution has acknowledged yet —
        these are the ones worth chasing. Approved-but-not-sent tasks are the
        human's to act on, not something to chase an institution about."""
        return [t for t in self.tasks() if t.status is Status.SENT]

    # --- transitions (safety-critical) -----------------------------------
    def record_draft(self, task_id: str, draft: str) -> TaskState:
        t = self.get(task_id)
        t.draft = draft
        if t.status is Status.PENDING:
            t.status = Status.DRAFTED
            t._log("drafted")
        return t

    def approve(self, task_id: str, decision: str = "") -> TaskState:
        """Approve a task. A weighty task REQUIRES a recorded decision — the
        whole point of the product is that these are never rubber-stamped."""
        t = self.get(task_id)
        if t.weighty and not (decision or t.decision):
            raise InvalidTransition(
                f"'{t.title}' is weighty and needs an explicit decision before approval")
        if decision:
            t.decision = decision
        t.status = Status.APPROVED
        t._log(f"approved: {decision}" if decision else "approved")
        return t

    def decline(self, task_id: str, reason: str = "") -> TaskState:
        t = self.get(task_id)
        t.decision = reason
        t.status = Status.DECLINED
        t._log(f"declined: {reason}" if reason else "declined")
        return t

    def mark_sent(self, task_id: str) -> TaskState:
        """The human sent/filed it. Umash never reaches this state on its own."""
        t = self.get(task_id)
        if t.status not in (Status.APPROVED, Status.DRAFTED):
            raise InvalidTransition(
                f"'{t.title}' must be approved before it can be sent")
        t.status = Status.SENT
        t._log("sent by human")
        return t

    def confirm(self, task_id: str) -> TaskState:
        t = self.get(task_id)
        t.status = Status.CONFIRMED
        t._log("confirmed by institution")
        return t

    # --- progress ---------------------------------------------------------
    def summary(self) -> dict:
        tasks = self.tasks()
        by_status: dict[str, int] = {}
        for t in tasks:
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        return {
            "case_id": self.case_id,
            "total": len(tasks),
            "routine": len(self.routine()),
            "weighty": len(self.weighty()),
            "resolved": sum(1 for t in tasks if t.resolved),
            "pending_escalations": len(self.pending_escalations()),
            "by_status": by_status,
        }

    # --- persistence ------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "died_in": self.died_in,
            "rest_in": self.rest_in,
            "deceased_name": self.deceased_name,
            "order": list(self._order),
            "tasks": {i: self._tasks[i].to_dict() for i in self._order},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CaseState":
        cs = cls(d["case_id"], d["died_in"], d["rest_in"],
                 d.get("deceased_name", "the deceased"))
        cs._order = list(d.get("order", []))
        cs._tasks = {i: TaskState.from_dict(td) for i, td in d.get("tasks", {}).items()}
        # tolerate any ids present in tasks but missing from order
        for i in cs._tasks:
            if i not in cs._order:
                cs._order.append(i)
        return cs

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "CaseState":
        with open(path) as f:
            return cls.from_dict(json.load(f))
