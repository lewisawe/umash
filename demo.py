#!/usr/bin/env python3
"""Umash demo.

  python demo.py            # run the agent against Bedrock (needs AWS creds)
  python demo.py --offline  # deterministic walkthrough, no model call

The scenario: a father passed in Nairobi; the family wants him laid to rest in
the UK. This exercises the cross-border repatriation branch and shows the whole
journey with the weighty decisions escalated one at a time.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from umash.agent import build_agent, run_offline  # noqa: E402

PROFILE_PATH = os.path.join(HERE, "umash", "data", "demo_profile.json")


def load_profile() -> dict:
    with open(PROFILE_PATH) as f:
        return json.load(f)


def print_offline(profile: dict) -> None:
    from umash.session import Session, auto_decider

    session = Session.new(profile["case_id"], profile["died_in"],
                          profile.get("rest_in"), profile["deceased_name"])
    case = session.case
    print("=" * 72)
    print(f"UMASH — Afterward   |   case: {profile['case_id']}")
    print(f"{profile['situation']}")
    cb = "cross-border (repatriation branch active)" if case.cross_border else "single jurisdiction"
    print(f"Jurisdiction: died {case.died_in} -> rest {case.rest_in}  [{cb}]")
    print("=" * 72)

    # Step 1: quiet routine drafting, phased view.
    session.prepare_routine()
    session.prepare_escalations()
    view = session.phased_view()
    for phase_key in ("immediate", "funeral", "admin"):
        block = view[phase_key]
        if not block["routine"] and not block["weighty"]:
            continue
        print(f"\n## {block['label']}")
        if block["routine"]:
            print(f"   Quietly prepared, batched for ONE approval ({len(block['routine'])}):")
            for t in block["routine"]:
                print(f"     - {t.title}  ->  {t.target}")
        for t in block["weighty"]:
            dl = f" [due in {t.deadline_days}d]" if t.deadline_days is not None else ""
            print(f"   >> NEEDS YOUR DECISION{dl}: {t.title}")

    # Show one real routine draft so the "prepared quietly" step is concrete.
    sample = next((t for t in case.routine() if t.draft), None)
    if sample:
        print("\n" + "-" * 72)
        print(f"Sample routine draft ({sample.title}) — ready for you to review and send:")
        for line in sample.draft.strip().splitlines():
            print(f"   {line}")

    # Step 2: batch-approve routine, then escalate weighty one at a time.
    approved = session.approve_routine_batch()
    esc_log = session.run_escalations(auto_decider)

    print("\n" + "-" * 72)
    print(f"Summary: {approved} routine tasks batched into one approval; "
          f"{len(esc_log)} weighty decisions surfaced one at a time.")
    print("Ordered escalations (most urgent first):")
    ordered = sorted(case.weighty(),
                     key=lambda t: (t.deadline_days is None,
                                    t.deadline_days if t.deadline_days is not None else 10**6))
    for i, t in enumerate(ordered, 1):
        dl = f"{t.deadline_days}d" if t.deadline_days is not None else "no fixed deadline"
        print(f"  {i}. [{t.phase}] {t.title}  ({dl})")
        print(f"     -> recorded decision: {t.decision}")
    print("\nUmash drafted everything and executed nothing. Every weighty step "
          "waited for a human decision before it was even approved.")
    print("-" * 72)


def print_online(profile: dict) -> None:
    agent = build_agent()
    prompt = (
        f"{profile['situation']} His known accounts: "
        f"{', '.join(profile['known_accounts'])}. "
        f"Use died_in='{profile['died_in']}' and rest_in='{profile.get('rest_in','')}'. "
        f"Lay out the plan, keep routine tasks quiet and batched, and surface the "
        f"weighty decisions one at a time."
    )
    result = agent(prompt)
    print(result)


def main() -> None:
    ap = argparse.ArgumentParser(description="Umash demo")
    ap.add_argument("--offline", action="store_true",
                    help="deterministic walkthrough, no Bedrock call")
    args = ap.parse_args()

    profile = load_profile()
    if args.offline:
        print_offline(profile)
    else:
        try:
            print_online(profile)
        except Exception as e:  # noqa: BLE001
            print(f"[online run failed: {e}]\nFalling back to --offline walkthrough:\n")
            print_offline(profile)


if __name__ == "__main__":
    main()
