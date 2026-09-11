"""The three phases of the journey, in order."""

from __future__ import annotations

from enum import Enum


class Phase(str, Enum):
    IMMEDIATE = "immediate"   # hours -> days: body, registration, funeral director
    FUNERAL = "funeral"       # days -> week: ceremony, permits, notices, contributions
    ADMIN = "admin"           # weeks -> months: banks, benefits, estate, subscriptions


PHASE_ORDER = [Phase.IMMEDIATE, Phase.FUNERAL, Phase.ADMIN]

PHASE_LABEL = {
    Phase.IMMEDIATE: "Immediate (hours-days)",
    Phase.FUNERAL: "Funeral (days-week)",
    Phase.ADMIN: "Admin / estate (weeks-months)",
}

# Keyword hints used to classify a free-text task into a phase when a task
# does not already carry one. Deterministic, longest-match wins.
_PHASE_HINTS = {
    Phase.IMMEDIATE: [
        "death certificate", "register the death", "registration", "mortuary",
        "morgue", "hospital bill", "release the body", "post-mortem", "autopsy",
        "repatriation", "repatriate", "embalm", "funeral director", "next of kin",
        "notify family", "notify people", "employer notification",
    ],
    Phase.FUNERAL: [
        "funeral", "burial", "cremation", "ceremony", "venue", "obituary",
        "notice", "eulogy", "casket", "coffin", "burial permit", "contribution",
        "harambee", "fundraiser", "program",
    ],
    Phase.ADMIN: [
        "bank", "account", "insurer", "insurance", "benefit", "pension",
        "utility", "subscription", "employer final pay", "estate", "probate",
        "will", "tax", "government", "social security", "nssf", "nhif",
    ],
}


def phase_of_task(text: str) -> Phase:
    """Best-effort deterministic phase for a free-text task description.

    Defaults to ADMIN (the long tail) when nothing matches, since the acute
    phases have the most distinctive vocabulary.
    """
    t = (text or "").lower()
    best: tuple[int, Phase] | None = None
    for phase, hints in _PHASE_HINTS.items():
        for h in hints:
            if h in t:
                score = len(h)
                if best is None or score > best[0]:
                    best = (score, phase)
    return best[1] if best else Phase.ADMIN
