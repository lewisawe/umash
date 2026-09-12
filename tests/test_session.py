"""Tests for the stateful layer: CaseState lifecycle and the Session loop.

No AWS creds and no Strands needed — this is the deterministic product core.

Run:  python -m pytest tests/  (or)  python tests/test_session.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from umash.policy import build_case, CaseState, Status, InvalidTransition, build_draft
from umash.session import Session, auto_decider, Decision


def test_build_case_classifies_and_counts():
    c = build_case("t", "KE", "UK", "my father")
    assert c.cross_border is True
    # counts are derived from the packs, not hardcoded, so the test stays
    # correct as coverage grows; the invariant is routine + weighty == total.
    assert len(c.tasks()) == len(c.routine()) + len(c.weighty())
    assert len(c.tasks()) > 30            # full-journey pack, not a stub
    assert len(c.weighty()) >= 5          # genuine decisions are surfaced
    assert len(c.routine()) > len(c.weighty())   # most work is routine + batched


def test_weighty_needs_decision_before_approval():
    c = build_case("t", "KE", "UK", "x")
    w = c.weighty()[0]
    try:
        c.approve(w.task_id)  # no decision -> must be blocked
    except InvalidTransition:
        pass
    else:
        raise AssertionError("weighty task approved with no recorded decision")
    # with a decision it goes through
    c.approve(w.task_id, "we will pay to release the body")
    assert c.get(w.task_id).status is Status.APPROVED
    assert "release the body" in c.get(w.task_id).decision


def test_routine_batch_approves_without_decision():
    c = build_case("t", "KE", "UK", "x")
    s = Session(c)
    s.prepare_routine()
    expected = len(c.routine())
    n = s.approve_routine_batch()
    assert n == expected
    assert all(t.status is Status.APPROVED for t in c.routine())


def test_escalations_ordered_by_urgency():
    c = build_case("t", "KE", "UK", "x")
    esc = c.pending_escalations()
    # soonest real deadline first; None deadlines last
    deadlines = [t.deadline_days for t in esc]
    with_dl = [d for d in deadlines if d is not None]
    assert with_dl == sorted(with_dl)
    assert deadlines[0] == min(with_dl)
    # the body-release / repatriation clock should lead
    assert esc[0].deadline_days <= 3


def test_full_session_flow_resolves_everything():
    s = Session.new("t", "KE", "UK", "my father")
    expected_routine = len(s.case.routine())
    expected_weighty = len(s.case.weighty())
    out = s.run(auto_decider)
    assert out["routine_prepared"] == expected_routine
    assert out["routine_approved"] == expected_routine
    assert len(out["escalations"]) == expected_weighty
    assert all(e["outcome"] == "approved" for e in out["escalations"])
    assert out["summary"]["pending_escalations"] == 0


def test_full_journey_covers_all_four_phases():
    from umash.policy.phases import PHASE_ORDER
    c = build_case("t", "KE", "UK", "my father")
    titles = [t.title.lower() for t in c.tasks()]
    phases_present = {t.phase for t in c.tasks()}
    # every phase in the journey is populated, not just the acute ones
    assert phases_present == {p.value for p in PHASE_ORDER}
    # moment-of-death coverage (Stage 0)
    assert any("pronouncement of death" in t for t in titles)
    assert any("organ or tissue donation" in t for t in titles)
    assert any("locate the will" in t for t in titles)
    assert any("dependents and pets" in t for t in titles)
    # aftercare long tail
    assert any("digital and social media" in t for t in titles)
    assert any("headstone" in t for t in titles)
    assert any("grief and bereavement" in t for t in titles)


def test_organ_donation_and_title_transfer_are_weighty():
    from umash.policy.consequence import classify
    assert classify("Decide on organ or tissue donation").escalates
    assert classify("Transfer property title / update the home").escalates
    assert classify("Transfer or sell the vehicle (title transfer)").escalates
    # routine logistics must NOT escalate
    assert not classify("Arrange catering and the reception").escalates
    assert not classify("Find grief and bereavement support").escalates


def test_decline_records_and_resolves():
    c = build_case("t", "KE", "UK", "x")
    s = Session(c)
    s.prepare_escalations()
    w = c.pending_escalations()[0]
    s.run_escalations(lambda t: Decision(False, "bury locally instead")
                      if t.task_id == w.task_id else None)
    assert c.get(w.task_id).status is Status.DECLINED
    assert c.get(w.task_id).decision == "bury locally instead"


def test_unconfirmed_only_lists_sent():
    c = build_case("t", "KE", "UK", "x")
    s = Session(c)
    s.prepare_routine()
    s.approve_routine_batch()
    # approved != chased; nothing is "sent" yet
    assert c.unconfirmed() == []
    t = c.routine()[0]
    c.mark_sent(t.task_id)
    assert [x.task_id for x in c.unconfirmed()] == [t.task_id]
    c.confirm(t.task_id)
    assert c.unconfirmed() == []


def test_cannot_send_before_approval():
    c = build_case("t", "KE", "UK", "x")
    w = c.weighty()[0]
    try:
        c.mark_sent(w.task_id)  # still pending
    except InvalidTransition:
        pass
    else:
        raise AssertionError("sent a task that was never approved")


def test_persistence_roundtrip_preserves_state():
    s = Session.new("t", "KE", "UK", "my father")
    s.run(auto_decider)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "case.json")
        s.case.save(p)
        loaded = CaseState.load(p)
    assert loaded.summary() == s.case.summary()
    assert loaded.deceased_name == "my father"
    assert loaded.cross_border is True


def test_build_draft_weighty_is_a_decision_prompt():
    esc, draft = build_draft("hospital billing",
                             "Settle the hospital bill to release the body")
    assert esc is True
    assert "NEEDS YOUR DECISION FIRST" in draft
    esc2, draft2 = build_draft("employer", "Notify employer and next of kin")
    assert esc2 is False
    assert "has passed away" in draft2


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} tests passed.")
