"""Consequence classification and the batch-vs-escalate decision.

This is the safety core. The rule the whole product rests on:

    routine + low-stakes            -> prepare quietly, batch for ONE approval
    weighty / irreversible /        -> ESCALATE one at a time, with tradeoffs
    time-critical                      and NEVER execute autonomously

Kept deterministic on purpose: whether something needs a grieving human's
decision must not depend on a model's mood.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Consequence(str, Enum):
    ROUTINE = "routine"      # reversible, low-stakes: batch it
    WEIGHTY = "weighty"      # money / legal / irreversible / time-critical: escalate


ROUTINE = Consequence.ROUTINE
WEIGHTY = Consequence.WEIGHTY


@dataclass
class Verdict:
    consequence: Consequence
    reasons: list[str] = field(default_factory=list)
    # populated when time-critical, so the agent can order escalations by urgency
    deadline_days: int | None = None

    @property
    def escalates(self) -> bool:
        return self.consequence is Consequence.WEIGHTY


# Signals that force WEIGHTY. Any hit escalates. These are deliberately narrow:
# escalation is for genuine DECISIONS (money leaving, an irreversible commitment,
# a legal signature) — NOT for routine logistics that merely happen to cost money
# or have a scheduling deadline. Over-escalation defeats the whole product.
_MONEY = ["settle the bill", "hospital bill", "pay ", "deposit", "wire",
          "transfer funds", "release funds", "payout"]
_LEGAL = ["sign for", "authorize", "authorise", "power of attorney",
          "probate", "estate filing", "estate succession", "begin estate",
          "succession", "affidavit", "notarize", "executor"]
_IRREVERSIBLE = ["release the body", "sign for the body", "repatriate vs",
                 "repatriate to", "cremate", "post-mortem", "autopsy",
                 "close the account permanently", "donate organs"]
_TIME_CRITICAL = ["time-critical", "before release", "expires"]

# Benefit/claim actions are weighty (money inflow with a filing decision), but
# only when they are the CLAIM itself, not a routine notification.
_CLAIM = ["survivor benefit", "benefit claim", "insurance claim",
          "claim nssf", "life-insurance benefit"]


def classify(task_text: str, deadline_days: int | None = None) -> Verdict:
    """Classify a task's consequence deterministically.

    Escalation is about the DECISION, not the deadline. `deadline_days` is
    carried through for URGENCY ORDERING only — a routine task with a near
    deadline stays routine (it still just needs doing, not a decision).
    """
    t = (task_text or "").lower()
    reasons: list[str] = []

    def _hit(bucket: list[str], label: str) -> bool:
        for kw in bucket:
            if kw in t:
                reasons.append(f"{label}: '{kw}'")
                return True
        return False

    weighty = False
    weighty |= _hit(_MONEY, "money")
    weighty |= _hit(_LEGAL, "legal")
    weighty |= _hit(_IRREVERSIBLE, "irreversible")
    weighty |= _hit(_TIME_CRITICAL, "time-critical")
    weighty |= _hit(_CLAIM, "claim")

    if weighty:
        return Verdict(Consequence.WEIGHTY, reasons, deadline_days)
    return Verdict(Consequence.ROUTINE, ["no decision signals — routine"],
                   deadline_days)


def is_escalation(task_text: str, deadline_days: int | None = None) -> bool:
    """Convenience: does this task need a human decision?"""
    return classify(task_text, deadline_days).escalates
