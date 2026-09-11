"""Jurisdiction packs.

The plan adapts to where the death happened and where the person is laid to
rest. Packs are DATA, so coverage grows without touching the agent. Each task
is a (title, phase, target, deadline_days) tuple; deadline_days=None means no
hard clock.

This is the differentiator most competitors lack: non-US jurisdictions and
cross-border repatriation as first-class.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .phases import Phase


class Jurisdiction(str, Enum):
    KE = "KE"   # Kenya
    UK = "UK"   # United Kingdom
    US = "US"   # United States


@dataclass(frozen=True)
class Task:
    title: str
    phase: Phase
    target: str            # who the notice/action is directed at
    deadline_days: int | None = None
    note: str = ""


# --- Kenya -----------------------------------------------------------------
_KE = [
    Task("Obtain medical cause-of-death / burial permit", Phase.IMMEDIATE,
         "hospital / attending doctor", 2,
         "Needed before the body can be released or moved."),
    Task("Register the death (Huduma Centre / Civil Registration)", Phase.IMMEDIATE,
         "Civil Registration Dept", 6,
         "Death certificate is the document everything downstream depends on."),
    Task("Settle the hospital bill to release the body", Phase.IMMEDIATE,
         "hospital billing", 2,
         "Body is often not released until the bill is cleared. WEIGHTY."),
    Task("Choose mortuary and confirm holding period + daily cost", Phase.IMMEDIATE,
         "mortuary", 3),
    Task("Engage a funeral director", Phase.IMMEDIATE, "funeral director", None),
    Task("Notify employer and next of kin", Phase.IMMEDIATE, "employer / family", None),
    Task("Arrange burial permit and venue", Phase.FUNERAL, "county / church", None),
    Task("Publish obituary / death notice", Phase.FUNERAL, "newspaper / community", None),
    Task("Coordinate funeral contributions (harambee / M-Pesa)", Phase.FUNERAL,
         "family & community", None),
    Task("Claim NSSF / pension survivor benefit", Phase.ADMIN, "NSSF / pension", 30,
         "Time-boxed benefit. WEIGHTY."),
    Task("Notify NHIF and close cover", Phase.ADMIN, "NHIF", None),
    Task("Notify banks and start succession", Phase.ADMIN, "bank(s)", None),
    Task("Cancel utilities and subscriptions", Phase.ADMIN, "utilities / subs", None),
    Task("Begin estate succession (if assets)", Phase.ADMIN, "court / lawyer", None,
         "May need a lawyer. WEIGHTY."),
]

# --- United Kingdom --------------------------------------------------------
_UK = [
    Task("Get the Medical Certificate of Cause of Death", Phase.IMMEDIATE,
         "hospital / GP", 2),
    Task("Register the death (Register Office)", Phase.IMMEDIATE, "Register Office", 5,
         "Must register within 5 days in England/Wales. Time-critical."),
    Task("Use 'Tell Us Once' to notify govt departments", Phase.IMMEDIATE,
         "GOV.UK Tell Us Once", None),
    Task("Engage a funeral director", Phase.IMMEDIATE, "funeral director", None),
    Task("Arrange the funeral / cremation", Phase.FUNERAL, "funeral director", None),
    Task("Publish obituary / notice", Phase.FUNERAL, "newspaper", None),
    Task("Notify banks, pensions, insurers", Phase.ADMIN, "financial institutions", None),
    Task("Value the estate and check probate need", Phase.ADMIN, "HMRC / probate", None,
         "May need probate. WEIGHTY."),
    Task("Cancel utilities and subscriptions", Phase.ADMIN, "utilities / subs", None),
]

# --- United States ---------------------------------------------------------
_US = [
    Task("Obtain the death certificate (order several copies)", Phase.IMMEDIATE,
         "funeral home / vital records", 5),
    Task("Engage a funeral home", Phase.IMMEDIATE, "funeral home", None),
    Task("Notify Social Security Administration", Phase.IMMEDIATE, "SSA", None),
    Task("Arrange the funeral / burial / cremation", Phase.FUNERAL, "funeral home", None),
    Task("Publish obituary", Phase.FUNERAL, "newspaper", None),
    Task("File any survivor / life-insurance benefit claim", Phase.ADMIN,
         "SSA / insurer", 30, "Time-boxed benefit. WEIGHTY."),
    Task("Notify banks, brokerages, creditors", Phase.ADMIN, "financial institutions", None),
    Task("Open probate if required", Phase.ADMIN, "probate court", None,
         "May need a lawyer. WEIGHTY."),
    Task("Cancel utilities and subscriptions", Phase.ADMIN, "utilities / subs", None),
]

_PACKS: dict[Jurisdiction, list[Task]] = {
    Jurisdiction.KE: _KE,
    Jurisdiction.UK: _UK,
    Jurisdiction.US: _US,
}


def supported_jurisdictions() -> list[str]:
    return [j.value for j in _PACKS]


def get_pack(j: Jurisdiction | str) -> list[Task]:
    if isinstance(j, str):
        j = Jurisdiction(j.upper())
    return list(_PACKS[j])


def _repatriation_tasks(died_in: Jurisdiction, rest_in: Jurisdiction) -> list[Task]:
    """Cross-border: extra immediate-phase tasks when body must move countries."""
    return [
        Task(f"Decide: repatriate to {rest_in.value} vs bury/cremate in {died_in.value}",
             Phase.IMMEDIATE, "family decision", 3,
             "Cost + time tradeoff. Irreversible. WEIGHTY."),
        Task("Obtain embalming certificate to ICAO standards for air transport",
             Phase.IMMEDIATE, "funeral director", 4,
             "Required for international air transport of remains."),
        Task(f"Get consular / embassy paperwork for transfer to {rest_in.value}",
             Phase.IMMEDIATE, "embassy / high commission", 5),
        Task("Arrange air cargo for repatriation of remains", Phase.IMMEDIATE,
             "airline cargo", None, "WEIGHTY (cost)."),
    ]


def tasks_for(died_in: Jurisdiction | str,
              rest_in: Jurisdiction | str | None = None) -> list[Task]:
    """Full task list for a case.

    Uses the pack of the country where the death occurred, and appends
    cross-border repatriation tasks when the resting place is a different
    country.
    """
    if isinstance(died_in, str):
        died_in = Jurisdiction(died_in.upper())
    tasks = get_pack(died_in)
    if rest_in is not None:
        if isinstance(rest_in, str):
            rest_in = Jurisdiction(rest_in.upper())
        if rest_in != died_in:
            tasks = _repatriation_tasks(died_in, rest_in) + tasks
    return tasks
