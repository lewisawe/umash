"""The phases of the journey, in order.

Four phases now, so the arc the README promises — from the moment of death to
long after the burial — is actually modeled, not crammed into three buckets:

  IMMEDIATE  the moment of death and the acute first 72 hours
  FUNERAL    planning and holding the service (days -> ~a week)
  ADMIN      estate, banks, benefits, government (weeks -> months)
  AFTERCARE  the long tail after burial (months -> a year+): digital accounts,
             property transfer, memorials, and grief support
"""

from __future__ import annotations

from enum import Enum


class Phase(str, Enum):
    IMMEDIATE = "immediate"   # moment of death + hours -> days: body, registration, director
    FUNERAL = "funeral"       # days -> week: ceremony, permits, notices, contributions
    ADMIN = "admin"           # weeks -> months: banks, benefits, estate, subscriptions
    AFTERCARE = "aftercare"   # months -> year+: digital estate, property, memorials, grief


PHASE_ORDER = [Phase.IMMEDIATE, Phase.FUNERAL, Phase.ADMIN, Phase.AFTERCARE]

PHASE_LABEL = {
    Phase.IMMEDIATE: "Immediate (moment of death - days)",
    Phase.FUNERAL: "Funeral (days - week)",
    Phase.ADMIN: "Admin / estate (weeks - months)",
    Phase.AFTERCARE: "Aftercare (months - year+)",
}

# Keyword hints used to classify a free-text task into a phase when a task
# does not already carry one. Deterministic, longest-match wins.
_PHASE_HINTS = {
    Phase.IMMEDIATE: [
        # moment of death
        "pronounce", "pronouncement", "coroner", "call the doctor", "call a doctor",
        "organ donation", "tissue donation", "donate organs", "locate the will",
        "funeral wishes", "prepaid funeral", "who is caring", "care for dependents",
        "care for children", "care for pets", "secure the home", "secure the body",
        # acute admin
        "death certificate", "register the death", "registration", "mortuary",
        "morgue", "hospital bill", "release the body", "post-mortem", "autopsy",
        "inquest", "repatriation", "repatriate", "embalm", "funeral director",
        "next of kin", "notify family", "notify people", "employer notification",
    ],
    Phase.FUNERAL: [
        "funeral", "burial", "cremation", "ceremony", "venue", "obituary",
        "notice", "eulogy", "casket", "coffin", "urn", "burial permit",
        "contribution", "harambee", "fundraiser", "program", "order of service",
        "officiant", "celebrant", "pallbearer", "flowers", "catering", "reception",
        "hearse", "transport of remains", "wake", "viewing",
    ],
    Phase.ADMIN: [
        "bank", "account", "insurer", "insurance", "benefit", "pension",
        "utility", "subscription", "employer final pay", "death-in-service",
        "estate", "probate", "will reading", "tax", "final tax return",
        "government", "social security", "nssf", "nhif", "creditor", "debt",
        "redirect mail", "mail redirection",
    ],
    Phase.AFTERCARE: [
        "digital account", "digital estate", "social media account",
        "email account", "close online", "memorialize", "memorialise",
        "headstone", "memorial marker", "gravestone", "anniversary",
        "memorial service", "personal effects", "heirloom", "distribute belongings",
        "property title", "transfer title", "vehicle title", "transfer the house",
        "grief support", "bereavement", "counselling", "counseling",
        "update your own will", "update beneficiaries",
    ],
}


def phase_of_task(text: str) -> Phase:
    """Best-effort deterministic phase for a free-text task description.

    Defaults to ADMIN (the mid-tail) when nothing matches, since the acute and
    aftercare phases have the most distinctive vocabulary and admin is the
    safest catch-all for generic institutional tasks.
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
