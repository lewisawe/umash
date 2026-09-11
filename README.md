# Umash — "Afterward"

*A full-journey aftermath coordinator for families after a death.*

> Built for the **Agents for Humans** hackathon (Good Neighbor track) with the
> [Strands Agents SDK](https://strandsagents.com) on Amazon Bedrock.

## The problem

When someone dies, the people left behind are thrown into a chaotic, deadline-laden
journey that spans everything from releasing the body to closing the last bank
account — mortuaries, hospitals, registrars, funeral homes, embassies, banks,
insurers, benefits offices, employers, and dozens of subscriptions. They do this
while grieving, often with no idea what comes first, what is urgent, or what can
wait. The steps differ by country, and for families split across borders (a
Kenyan who died in the UK, say) repatriation adds another layer.

Real accounts: one family spent **four months** just locating a deceased parent's
bank accounts; another was locked out of every login, bill, and investment when
the household's sole manager died suddenly.

## Who it's for

The **family member or next of kin** doing the admin — not a funeral director,
not a lawyer. The person who has to make the calls while grieving.

## Why it matters

Nearly everyone will do this someday. Existing tools are either funeral-home
case-management software (built for the business, not the family) or single-country
estate-settlement checklists. None carry a family through the *whole* journey, and
almost none handle the acute first-72-hours phase or non-US jurisdictions.

## What Umash does

Umash is **one agent across the whole arc**, organized into three phases:

1. **Immediate (hours–days):** register the death, mortuary choice + clock,
   hospital-bill-before-release, funeral director, permits, notifying people,
   repatriation (one branch, if cross-border).
2. **Funeral (days–week):** venue, ceremony logistics, permits, obituary/notices,
   coordinating contributions.
3. **Admin / estate (weeks–months):** banks, insurers, benefits, utilities,
   subscriptions, employer, government, estate.

Across every phase it follows one rule — **the agent runs autonomously and only
surfaces when there's a real decision to make**:

- **Routine + low-stakes** tasks (draft the registration letter, the employer
  notice, a subscription cancellation) are prepared quietly and **batched into one
  approval**.
- **Weighty / irreversible / time-critical** decisions (settle the hospital bill
  to release the body, repatriate vs bury locally, a benefits claim with a
  deadline) are **escalated one at a time**, with the tradeoffs laid out.
- It **never files, pays, or books anything autonomously.** It drafts, plans, and
  waits for the human. Restraint is the point.

It is **jurisdiction-aware**: the plan adapts to where the death happened and
where the person is laid to rest (Kenya, UK, US in this build; more are data).

## Architecture

See [`ARCHITECTURE.md`](./ARCHITECTURE.md). In short: a single Strands agent on
Bedrock with six tools, backed by a **deterministic policy layer** that owns phase
ordering, consequence tiers, the batch-vs-escalate rule, deadlines, and
jurisdiction packs — so the safety-critical logic is code, not model output.

```
umash/
├── umash/
│   ├── policy/          # deterministic: phases, consequence tiers, jurisdiction packs,
│   │                    #   case state machine, draft text — no model, no AWS
│   ├── tools.py         # the six Strands @tool functions
│   ├── session.py       # the batch-vs-escalate loop over a persistent case
│   ├── cli.py           # the `umash` command (run your own case, no creds needed)
│   ├── agent.py         # the Strands agent + escalation/approval loop
│   └── data/            # synthetic demo profiles
├── demo.py              # runnable end-to-end demo (one cross-border scenario)
├── tests/               # policy + case-state + session tests (no creds needed)
├── pyproject.toml       # packaging; core has zero third-party deps
├── ARCHITECTURE.md
├── LICENSE              # MIT
└── requirements.txt     # only the optional Bedrock agent deps
```

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# AWS creds with Bedrock *invoke* access (not just list). Umash uses the
# standard AWS credential chain; set a profile only if you need to override it.
export UMASH_AWS_PROFILE=your-bedrock-profile   # optional; else AWS_PROFILE / default chain
export AWS_REGION=us-east-1
# optional model override (default: us.amazon.nova-pro-v1:0):
# export UMASH_MODEL_ID=us.amazon.nova-lite-v1:0
```

## Run the demo

```bash
python demo.py                 # full run against Bedrock
python demo.py --offline       # deterministic walkthrough, no Bedrock call (for CI / no creds)
```

The demo drives one scenario — *"My father passed in Nairobi; he lived in the
UK"* — through all three phases: it lays out the jurisdiction-aware plan, runs the
routine drafts quietly, and escalates the weighty decisions (hospital-bill release,
repatriate vs bury) one at a time.

## Use it on a real case (CLI)

The deterministic product ships as a `umash` command and needs **no AWS creds and
no third-party packages** — it runs on the standard library. Cases persist to
`~/.umash/cases/` so work survives between sittings.

```bash
pip install -e .                         # installs the `umash` command (core only)

umash new  --case dad --died-in KE --rest-in UK --name "my father"
umash plan --case dad                    # the phased, jurisdiction-aware plan
umash run  --case dad                    # batch routine, then escalate weighty one at a time
umash status --case dad                  # progress + what's outstanding
umash draft  --case dad <task-id>        # review a single prepared draft
umash confirm --case dad <task-id>       # mark an institution as having acknowledged
umash cases                              # list all cases
```

`umash run` prepares every routine task quietly and asks for **one** batch
approval, then surfaces each weighty decision **one at a time** and records your
decision before it is even marked approved. Add `--auto --yes` for a
non-interactive walkthrough. Umash never files, pays, or sends anything.

## Safety & data

- No autonomous filing, payment, or booking. Every consequential action is a
  human-approved draft.
- Synthetic data only in this repo. Real deployments must handle decedent PII with
  care (retention limits, encryption); the policy layer centralizes that boundary.
- Not legal or financial advice; the agent flags when a step may need a
  professional.

## License

MIT — see [`LICENSE`](./LICENSE).
