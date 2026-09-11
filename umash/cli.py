"""Umash command-line interface.

A real family can run their own case, not just the demo scenario:

    umash new --died-in KE --rest-in UK --name "my father" --case dad
    umash plan   --case dad          # show the phased plan
    umash run    --case dad          # batch routine, escalate weighty (interactive)
    umash status --case dad          # progress / what's outstanding
    umash draft  --case dad <task-id>   # show a single task's draft
    umash confirm --case dad <task-id>  # mark an institution as having acknowledged

Cases persist to ~/.umash/cases/<case>.json so work survives between sittings.
This CLI touches no network and no model — it's the deterministic product. The
Bedrock agent (see agent.py / demo.py) is a separate, conversational front end
over the same policy layer.
"""

from __future__ import annotations

import argparse
import os
import sys

from .policy import CaseState, InvalidTransition, supported_jurisdictions
from .policy.phases import PHASE_ORDER, PHASE_LABEL, Phase
from .session import Session, prompt_decider, auto_decider

CASE_DIR = os.path.join(os.path.expanduser("~"), ".umash", "cases")


def _case_path(case_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in case_id)
    return os.path.join(CASE_DIR, f"{safe}.json")


def _load(case_id: str) -> CaseState:
    path = _case_path(case_id)
    if not os.path.exists(path):
        sys.exit(f"No case '{case_id}'. Create one with:  umash new --case {case_id} "
                 f"--died-in <CC> [--rest-in <CC>] --name \"...\"")
    return CaseState.load(path)


def _save(case: CaseState) -> None:
    case.save(_case_path(case.case_id))


BAR = "=" * 72
RULE = "-" * 72


def cmd_new(args: argparse.Namespace) -> None:
    died = args.died_in.upper()
    supported = supported_jurisdictions()
    if died not in supported:
        sys.exit(f"died-in '{died}' not supported. Have: {', '.join(supported)}")
    rest = (args.rest_in or "").upper() or None
    if rest and rest not in supported:
        sys.exit(f"rest-in '{rest}' not supported. Have: {', '.join(supported)}")

    session = Session.new(args.case, died, rest, args.name)
    _save(session.case)
    cb = "cross-border — repatriation branch active" if session.case.cross_border else "single jurisdiction"
    print(f"Created case '{args.case}' for {args.name}.")
    print(f"  died {session.case.died_in} -> rest {session.case.rest_in}  [{cb}]")
    print(f"  {len(session.case.tasks())} tasks "
          f"({len(session.case.routine())} routine, {len(session.case.weighty())} weighty).")
    print(f"\nNext:  umash plan --case {args.case}    then    umash run --case {args.case}")


def cmd_plan(args: argparse.Namespace) -> None:
    case = _load(args.case)
    session = Session(case)
    print(BAR)
    print(f"UMASH — Afterward   |   case: {case.case_id}   |   {case.deceased_name}")
    cb = "cross-border (repatriation branch active)" if case.cross_border else "single jurisdiction"
    print(f"Jurisdiction: died {case.died_in} -> rest {case.rest_in}  [{cb}]")
    print(BAR)
    view = session.phased_view()
    for p in PHASE_ORDER:
        block = view[p.value]
        routine, weighty = block["routine"], block["weighty"]
        if not routine and not weighty:
            continue
        print(f"\n## {block['label']}")
        if routine:
            print(f"   Quietly prepared, batched for ONE approval ({len(routine)}):")
            for t in routine:
                print(f"     - {t.title}  ->  {t.target}")
        for t in weighty:
            dl = f" [due in {t.deadline_days}d]" if t.deadline_days is not None else ""
            print(f"   >> NEEDS YOUR DECISION{dl}: {t.title}")
    esc = session.case.weighty()
    print("\n" + RULE)
    print(f"{len(case.routine())} routine tasks batch into one approval; "
          f"{len(esc)} weighty decisions surface one at a time.")
    print(f"Run them:  umash run --case {case.case_id}")
    print(RULE)


def cmd_run(args: argparse.Namespace) -> None:
    case = _load(args.case)
    session = Session(case)

    prepared = session.prepare_routine()
    print(BAR)
    print(f"UMASH — working case '{case.case_id}' for {case.deceased_name}")
    print(BAR)
    print(f"\nStep 1 — {len(prepared)} routine tasks prepared quietly and batched "
          f"for a single approval:")
    for t in prepared:
        print(f"   - {t.title}  ->  {t.target}")

    if args.yes:
        approve = True
    else:
        approve = input("\nApprove all routine drafts as one batch? [Y/n]: ").strip().lower() in ("", "y", "yes")
    if approve:
        n = session.approve_routine_batch()
        print(f"   ✔ {n} routine tasks approved together. (Umash sends nothing — "
              f"you send when ready.)")
    else:
        print("   Left routine batch pending.")

    decider = auto_decider if args.auto else prompt_decider
    esc = session.case.pending_escalations()
    print(f"\nStep 2 — {len(esc)} weighty decisions, surfaced one at a time "
          f"(most urgent first):")
    log = session.run_escalations(decider)
    if not log:
        print("   (none outstanding)")

    _save(session.case)
    s = session.case.summary()
    print("\n" + RULE)
    print(f"Progress: {s['resolved']}/{s['total']} resolved; "
          f"{s['pending_escalations']} weighty decisions still open.")
    print("Umash drafted everything and executed nothing.")
    print(f"Saved. Resume anytime:  umash status --case {case.case_id}")
    print(RULE)


def cmd_status(args: argparse.Namespace) -> None:
    case = _load(args.case)
    s = case.summary()
    print(f"Case '{case.case_id}' — {case.deceased_name}  "
          f"(died {case.died_in} -> rest {case.rest_in})")
    print(f"  {s['resolved']}/{s['total']} resolved   "
          f"| routine {s['routine']}  weighty {s['weighty']}")
    print("  by status: " + ", ".join(f"{k}={v}" for k, v in sorted(s["by_status"].items())))

    esc = case.pending_escalations()
    if esc:
        print("\n  Open decisions (most urgent first):")
        for t in esc:
            dl = f"{t.deadline_days}d" if t.deadline_days is not None else "no deadline"
            print(f"    >> [{dl}] {t.title}   (id: {t.task_id})")
    unconf = case.unconfirmed()
    if unconf:
        print("\n  Awaiting institution acknowledgement (chase if slow):")
        for t in unconf:
            print(f"    · {t.title} -> {t.target}   (id: {t.task_id})")
    if not esc and not unconf:
        print("\n  Nothing outstanding. Everything is resolved or confirmed.")


def cmd_draft(args: argparse.Namespace) -> None:
    case = _load(args.case)
    session = Session(case)
    session.prepare_routine()
    session.prepare_escalations()
    try:
        t = case.get(args.task_id)
    except KeyError:
        ids = ", ".join(x.task_id for x in case.tasks())
        sys.exit(f"No task '{args.task_id}' in case '{case.case_id}'.\nTask ids: {ids}")
    _save(case)
    kind = "WEIGHTY — decision required first" if t.weighty else "routine draft (review, then send yourself)"
    print(f"[{kind}]\n")
    print(t.draft or "(no draft yet)")


def cmd_confirm(args: argparse.Namespace) -> None:
    case = _load(args.case)
    try:
        t = case.confirm(args.task_id)
    except KeyError:
        sys.exit(f"No task '{args.task_id}' in case '{case.case_id}'.")
    _save(case)
    print(f"Marked confirmed: {t.title}")


def cmd_cases(args: argparse.Namespace) -> None:
    if not os.path.isdir(CASE_DIR):
        print("No cases yet. Create one with:  umash new ...")
        return
    files = [f for f in os.listdir(CASE_DIR) if f.endswith(".json")]
    if not files:
        print("No cases yet. Create one with:  umash new ...")
        return
    print("Cases:")
    for f in sorted(files):
        try:
            c = CaseState.load(os.path.join(CASE_DIR, f))
            s = c.summary()
            print(f"  {c.case_id:20} {c.deceased_name:24} "
                  f"{c.died_in}->{c.rest_in}  {s['resolved']}/{s['total']} done")
        except Exception:  # noqa: BLE001
            print(f"  {f} (unreadable)")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="umash",
        description="Umash — a companion through the whole journey after a death. "
                    "Drafts and plans; never files, pays, or sends.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def with_case(p):
        p.add_argument("--case", default="default", help="case id (default: 'default')")
        return p

    p_new = with_case(sub.add_parser("new", help="start a new case"))
    p_new.add_argument("--died-in", required=True, help=f"country of death ({', '.join(supported_jurisdictions())})")
    p_new.add_argument("--rest-in", default="", help="country laid to rest (if different -> repatriation)")
    p_new.add_argument("--name", default="the deceased", help="the person's name/relationship")
    p_new.set_defaults(func=cmd_new)

    with_case(sub.add_parser("plan", help="show the phased plan")).set_defaults(func=cmd_plan)

    p_run = with_case(sub.add_parser("run", help="batch routine, escalate weighty"))
    p_run.add_argument("--auto", action="store_true", help="auto-decide escalations (demo, non-interactive)")
    p_run.add_argument("--yes", action="store_true", help="approve the routine batch without prompting")
    p_run.set_defaults(func=cmd_run)

    with_case(sub.add_parser("status", help="progress and what's outstanding")).set_defaults(func=cmd_status)

    p_draft = with_case(sub.add_parser("draft", help="show one task's draft"))
    p_draft.add_argument("task_id", help="task id (see 'umash status')")
    p_draft.set_defaults(func=cmd_draft)

    p_conf = with_case(sub.add_parser("confirm", help="mark an institution acknowledgement"))
    p_conf.add_argument("task_id", help="task id (see 'umash status')")
    p_conf.set_defaults(func=cmd_confirm)

    sub.add_parser("cases", help="list all cases").set_defaults(func=cmd_cases)
    return ap


def main(argv: list[str] | None = None) -> None:
    ap = build_parser()
    args = ap.parse_args(argv)
    try:
        args.func(args)
    except InvalidTransition as e:
        sys.exit(f"Blocked by safety rule: {e}")
    except KeyboardInterrupt:
        sys.exit("\nInterrupted. Your case is saved up to the last completed step.")


if __name__ == "__main__":
    main()
