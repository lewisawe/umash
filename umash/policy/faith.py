"""Faith and culture packs — urgency and rites, as data.

A jurisdiction-aware product that ignores faith is only half aware. Where the
death happened sets the paperwork; the family's tradition sets the *clock* and
the rites. For Muslim and Jewish families, burial is expected within about a
day, which reorders the entire acute phase; Hindu families cremate quickly;
many Christian and secular families take longer. None of that is legal advice —
it is scheduling reality the coordinator must respect so it doesn't calmly
batch a task the family needed done last night.

Kept as DATA, like the jurisdiction packs, so coverage grows without touching
the agent. Each faith optionally:
  - injects rite-specific tasks (ritual washing, specific rites), and
  - compresses the deadline of matching funeral tasks to its customary window.

Faith is OPTIONAL. With no faith given, the plan is exactly the jurisdiction
pack — no assumptions imposed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .phases import Phase
from .jurisdictions import Task


class Faith(str, Enum):
    MUSLIM = "muslim"
    JEWISH = "jewish"
    HINDU = "hindu"
    CHRISTIAN = "christian"
    SECULAR = "secular"


@dataclass(frozen=True)
class FaithPack:
    label: str
    # customary window from death to burial/cremation, in days (None = no norm)
    burial_window_days: int | None
    # extra rite tasks prepended to the funeral phase
    rites: tuple[Task, ...] = ()
    note: str = ""


_MUSLIM = FaithPack(
    label="Muslim",
    burial_window_days=1,
    note="Burial is customarily as soon as possible, typically within 24 hours.",
    rites=(
        Task("Arrange ghusl (ritual washing) and shrouding (kafan)", Phase.FUNERAL,
             "family / mosque", 1, "Performed before the funeral prayer."),
        Task("Arrange Salat al-Janazah (funeral prayer)", Phase.FUNERAL,
             "imam / mosque", 1),
        Task("Arrange prompt burial facing the qibla", Phase.FUNERAL,
             "burial ground", 1, "Cremation is not practised; burial is expected quickly."),
    ),
)

_JEWISH = FaithPack(
    label="Jewish",
    burial_window_days=1,
    note="Burial is traditionally within a day; the body is not left unattended.",
    rites=(
        Task("Contact the Chevra Kadisha for taharah (ritual purification)",
             Phase.FUNERAL, "burial society", 1),
        Task("Arrange shmira (watching) until burial", Phase.FUNERAL,
             "community", 1),
        Task("Arrange prompt burial and prepare for shiva", Phase.FUNERAL,
             "synagogue / family", 1, "Shiva is the seven-day mourning period after burial."),
    ),
)

_HINDU = FaithPack(
    label="Hindu",
    burial_window_days=2,
    note="Cremation is customary and usually held within a day or two.",
    rites=(
        Task("Arrange the antyesti (last rites) and cremation", Phase.FUNERAL,
             "priest / crematorium", 2),
        Task("Arrange for the chief mourner and rituals", Phase.FUNERAL,
             "family / priest", 2),
    ),
)

_CHRISTIAN = FaithPack(
    label="Christian",
    burial_window_days=None,
    note="Timing varies widely; a service is typically held within one to two weeks.",
    rites=(
        Task("Arrange a wake / vigil and the funeral service", Phase.FUNERAL,
             "church / clergy", None),
    ),
)

_SECULAR = FaithPack(
    label="Secular / none",
    burial_window_days=None,
    note="No religious timing; a celebration of life can be scheduled freely.",
    rites=(),
)


_FAITHS: dict[Faith, FaithPack] = {
    Faith.MUSLIM: _MUSLIM,
    Faith.JEWISH: _JEWISH,
    Faith.HINDU: _HINDU,
    Faith.CHRISTIAN: _CHRISTIAN,
    Faith.SECULAR: _SECULAR,
}


def supported_faiths() -> list[str]:
    return [f.value for f in _FAITHS]


def get_faith_pack(f: Faith | str) -> FaithPack:
    if isinstance(f, str):
        f = Faith(f.lower())
    return _FAITHS[f]


def apply_faith(tasks: list[Task], faith: Faith | str | None) -> list[Task]:
    """Return a new task list adjusted for the family's tradition.

    - Prepends the faith's rite tasks at the front of the funeral phase.
    - Compresses funeral-phase deadlines to the customary burial window when
      the window is tighter than a task's existing clock. Immediate-phase and
      later tasks are left alone; the tradition governs the *service* timing.

    With faith=None the tasks are returned unchanged.
    """
    if faith is None:
        return tasks
    pack = get_faith_pack(faith)
    window = pack.burial_window_days

    adjusted: list[Task] = []
    for t in tasks:
        if window is not None and t.phase is Phase.FUNERAL:
            if t.deadline_days is None or t.deadline_days > window:
                t = replace(t, deadline_days=window)
        adjusted.append(t)

    if not pack.rites:
        return adjusted

    # insert rite tasks just before the first funeral-phase task so they lead
    # the service planning; if there is no funeral task, append them.
    first_funeral = next((i for i, t in enumerate(adjusted)
                          if t.phase is Phase.FUNERAL), None)
    rites = list(pack.rites)
    if first_funeral is None:
        return adjusted + rites
    return adjusted[:first_funeral] + rites + adjusted[first_funeral:]
