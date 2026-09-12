"""Jurisdiction packs — the full journey, as data.

The plan adapts to where the death happened and where the person is laid to
rest. Packs are DATA, so coverage grows without touching the agent. Each task
is a (title, phase, target, deadline_days, note) tuple; deadline_days=None
means no hard clock.

Coverage now spans the whole arc the README promises:

  IMMEDIATE   the moment of death (pronouncement, organ-donation clock, locate
              the will, who is caring for dependents right now) + the acute
              first 72 hours (certificate, mortuary, release, director).
  FUNERAL     the service itself, in detail (venue, officiant, casket/urn,
              order of service, transport, notices, catering, contributions).
  ADMIN       estate, banks, benefits, government, tax, creditors, mail.
  AFTERCARE   the long tail after burial (digital accounts, property/vehicle
              title, personal effects, headstone, grief support, your own will).

Cross-border repatriation is layered on top when the resting place is a
different country. It is one branch of the journey, not the whole of it.

Task titles are phrased so the deterministic consequence classifier in
consequence.py lands correctly: genuine money/legal/irreversible/claim
DECISIONS carry the trigger words; routine logistics deliberately do not.
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


# Steps shared across every jurisdiction — the moment of death and the human
# realities that come before any paperwork. Prepended to each pack so no
# jurisdiction forgets them.
def _stage0() -> list[Task]:
    return [
        Task("Get a legal pronouncement of death", Phase.IMMEDIATE,
             "attending doctor / coroner", 1,
             "A doctor or coroner must formally confirm the death before anything else."),
        Task("Decide on organ or tissue donation", Phase.IMMEDIATE,
             "hospital / donor registry", 1,
             "Time-critical — viable only for a short window. Irreversible. WEIGHTY."),
        Task("Locate the will and any recorded funeral wishes", Phase.IMMEDIATE,
             "family / solicitor / safe", 2,
             "Wishes about burial vs cremation and a prepaid plan change everything downstream."),
        Task("Arrange immediate care for dependents and pets", Phase.IMMEDIATE,
             "family / neighbours", 1,
             "Who is caring for children, an elderly spouse, or pets right now."),
        Task("Secure the home and belongings of the deceased", Phase.IMMEDIATE,
             "family", 2,
             "Lock up, redirect perishables, hold valuables safe."),
    ]


# Shared aftercare tail — the months-to-a-year+ work almost no tool handles.
def _aftercare_common() -> list[Task]:
    return [
        Task("Close or memorialize digital and social media accounts", Phase.AFTERCARE,
             "online platforms", None,
             "Email, social media, cloud storage, photos. Prevents identity misuse."),
        Task("Cancel or transfer the phone and internet accounts", Phase.AFTERCARE,
             "telecom / ISP", None),
        Task("Transfer or sell the vehicle (title transfer)", Phase.AFTERCARE,
             "vehicle registry", None,
             "Retitling is a legal transfer. WEIGHTY."),
        Task("Transfer property title / update the home", Phase.AFTERCARE,
             "land registry / lawyer", None,
             "Real-property transfer needs a legal step. WEIGHTY."),
        Task("Distribute personal effects and heirlooms", Phase.AFTERCARE,
             "family", None),
        Task("Arrange a headstone or memorial marker", Phase.AFTERCARE,
             "monument mason", None,
             "Often placed months later once the ground settles."),
        Task("Plan the memorial or anniversary observance", Phase.AFTERCARE,
             "family / community", None),
        Task("Find grief and bereavement support", Phase.AFTERCARE,
             "counsellor / support group", None,
             "For the family. The one step that is about the living, not the paperwork."),
        Task("Update your own will and beneficiaries", Phase.AFTERCARE,
             "your solicitor", None,
             "A death often invalidates the survivors' own arrangements."),
    ]


# --- Kenya -----------------------------------------------------------------
_KE = _stage0() + [
    # acute admin
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
    # funeral, in detail
    Task("Choose burial or cremation per the family's wishes", Phase.FUNERAL,
         "family", 3, "Sets everything else about the service."),
    Task("Arrange burial permit and venue", Phase.FUNERAL, "county / church", None),
    Task("Confirm an officiant and the order of service", Phase.FUNERAL,
         "church / celebrant", None),
    Task("Select a casket and flowers", Phase.FUNERAL, "funeral director", None),
    Task("Arrange the hearse and transport of remains", Phase.FUNERAL,
         "funeral director", None),
    Task("Publish obituary / death notice", Phase.FUNERAL, "newspaper / community", None),
    Task("Coordinate funeral contributions (harambee / M-Pesa)", Phase.FUNERAL,
         "family & community", None),
    Task("Arrange catering and the after-service gathering", Phase.FUNERAL,
         "caterer / venue", None),
    # admin / estate
    Task("Claim NSSF / pension survivor benefit", Phase.ADMIN, "NSSF / pension", 30,
         "Time-boxed benefit. WEIGHTY."),
    Task("Notify NHIF and close cover", Phase.ADMIN, "NHIF", None),
    Task("Notify banks and start succession", Phase.ADMIN, "bank(s)", None),
    Task("Notify creditors and check which debts survive", Phase.ADMIN,
         "lenders / SACCOs", None),
    Task("Cancel utilities and subscriptions", Phase.ADMIN, "utilities / subs", None),
    Task("Redirect the deceased's mail", Phase.ADMIN, "Posta Kenya", None),
    Task("Begin estate succession (if assets)", Phase.ADMIN, "court / lawyer", None,
         "May need a lawyer. WEIGHTY."),
] + _aftercare_common()

# --- United Kingdom --------------------------------------------------------
_UK = _stage0() + [
    Task("Get the Medical Certificate of Cause of Death", Phase.IMMEDIATE,
         "hospital / GP", 2),
    Task("Register the death (Register Office)", Phase.IMMEDIATE, "Register Office", 5,
         "Must register within 5 days in England/Wales. Time-critical."),
    Task("Use 'Tell Us Once' to notify govt departments", Phase.IMMEDIATE,
         "GOV.UK Tell Us Once", None),
    Task("Engage a funeral director", Phase.IMMEDIATE, "funeral director", None),
    # funeral
    Task("Choose burial or cremation per the family's wishes", Phase.FUNERAL,
         "family", 3),
    Task("Arrange the funeral / cremation and venue", Phase.FUNERAL, "funeral director", None),
    Task("Confirm an officiant and the order of service", Phase.FUNERAL,
         "celebrant / church", None),
    Task("Select a casket or urn and flowers", Phase.FUNERAL, "funeral director", None),
    Task("Publish obituary / notice", Phase.FUNERAL, "newspaper", None),
    Task("Arrange catering and the wake / reception", Phase.FUNERAL, "venue / caterer", None),
    # admin
    Task("Notify banks, pensions, insurers", Phase.ADMIN, "financial institutions", None),
    Task("Value the estate and check probate need", Phase.ADMIN, "HMRC / probate", None,
         "May need probate. WEIGHTY."),
    Task("File the final tax position with HMRC", Phase.ADMIN, "HMRC", None),
    Task("Notify creditors and check which debts survive", Phase.ADMIN, "lenders", None),
    Task("Cancel utilities and subscriptions", Phase.ADMIN, "utilities / subs", None),
    Task("Redirect the deceased's mail (Royal Mail)", Phase.ADMIN, "Royal Mail", None),
] + _aftercare_common()

# --- United States ---------------------------------------------------------
_US = _stage0() + [
    Task("Obtain the death certificate (order several copies)", Phase.IMMEDIATE,
         "funeral home / vital records", 5),
    Task("Engage a funeral home", Phase.IMMEDIATE, "funeral home", None),
    Task("Notify Social Security Administration", Phase.IMMEDIATE, "SSA", None),
    # funeral
    Task("Choose burial or cremation per the family's wishes", Phase.FUNERAL,
         "family", 3),
    Task("Arrange the funeral / burial / cremation and venue", Phase.FUNERAL,
         "funeral home", None),
    Task("Confirm an officiant and the order of service", Phase.FUNERAL,
         "celebrant / clergy", None),
    Task("Select a casket or urn and flowers", Phase.FUNERAL, "funeral home", None),
    Task("Publish obituary", Phase.FUNERAL, "newspaper", None),
    Task("Arrange catering and the reception", Phase.FUNERAL, "venue / caterer", None),
    # admin
    Task("File any survivor / life-insurance benefit claim", Phase.ADMIN,
         "SSA / insurer", 30, "Time-boxed benefit. WEIGHTY."),
    Task("Notify banks, brokerages, creditors", Phase.ADMIN, "financial institutions", None),
    Task("Open probate if required", Phase.ADMIN, "probate court", None,
         "May need a lawyer. WEIGHTY."),
    Task("File the final tax return with the IRS", Phase.ADMIN, "IRS", None),
    Task("Cancel utilities and subscriptions", Phase.ADMIN, "utilities / subs", None),
    Task("Redirect the deceased's mail (USPS)", Phase.ADMIN, "USPS", None),
] + _aftercare_common()

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
              rest_in: Jurisdiction | str | None = None,
              faith=None) -> list[Task]:
    """Full task list for a case.

    Uses the pack of the country where the death occurred, appends cross-border
    repatriation tasks when the resting place is a different country, and — if a
    faith is given — injects its rites and compresses the service to the
    tradition's customary window. Faith is optional; omit it to impose nothing.
    """
    if isinstance(died_in, str):
        died_in = Jurisdiction(died_in.upper())
    tasks = get_pack(died_in)
    if rest_in is not None:
        if isinstance(rest_in, str):
            rest_in = Jurisdiction(rest_in.upper())
        if rest_in != died_in:
            tasks = _repatriation_tasks(died_in, rest_in) + tasks
    if faith is not None:
        # imported lazily to avoid a circular import (faith imports Task from here)
        from .faith import apply_faith
        tasks = apply_faith(tasks, faith)
    return tasks
