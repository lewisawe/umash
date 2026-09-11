"""Tests for the deterministic policy layer.

Run:  python -m pytest tests/  (or)  python tests/test_policy.py
No AWS creds needed — this is the safety-critical logic, tested in isolation.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from umash.policy import classify, tasks_for, phase_of_task
from umash.policy.phases import Phase


# (task, deadline_days, expected_escalates)
CONSEQUENCE_CASES = [
    ("Settle the hospital bill to release the body", 2, True),
    ("Decide: repatriate to UK vs bury/cremate in KE", 3, True),
    ("Claim NSSF / pension survivor benefit", 30, True),
    ("Begin estate succession (if assets)", None, True),
    ("Register the death (Huduma Centre)", 6, False),
    ("Choose mortuary and confirm holding period + daily cost", 3, False),
    ("Publish obituary / death notice", None, False),
    ("Cancel utilities and subscriptions", None, False),
    ("Notify employer and next of kin", None, False),
]


def test_consequence_classification():
    for txt, dl, want in CONSEQUENCE_CASES:
        got = classify(txt, dl).escalates
        assert got == want, f"{txt!r}: escalate={got}, want={want}"


def test_cross_border_prepends_repatriation():
    ke_only = tasks_for("KE")
    ke_uk = tasks_for("KE", "UK")
    assert len(ke_uk) > len(ke_only)
    assert "repatriate" in ke_uk[0].title.lower()


def test_same_country_no_repatriation():
    ts = tasks_for("KE", "KE")
    assert not any("repatriate" in t.title.lower() for t in ts)


def test_selective_escalation_ratio():
    # The product thesis: MOST tasks are routine, FEW escalate.
    ts = tasks_for("KE", "UK")
    esc = [t for t in ts if classify(t.title, t.deadline_days).escalates]
    assert len(esc) <= len(ts) // 3, f"{len(esc)}/{len(ts)} escalate — too many"


def test_phase_routing():
    assert phase_of_task("register the death") is Phase.IMMEDIATE
    assert phase_of_task("publish the obituary") is Phase.FUNERAL
    assert phase_of_task("cancel bank account") is Phase.ADMIN


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} tests passed.")
