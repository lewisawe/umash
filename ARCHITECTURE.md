# Umash Architecture

Umash is **one Strands agent** on Amazon Bedrock, backed by a **deterministic
policy layer**. The split is deliberate: the model handles ordering, tone, and
conversation; the safety-critical decisions (what phase, what consequence,
escalate vs batch, which jurisdiction steps) are plain Python that the model
cannot override.

## System diagram

```
                        ┌──────────────────────────────┐
   survivor input ─────▶│         demo.py / UI          │
   (who died, where,    │  loads synthetic profile      │
    laid to rest)       └───────────────┬───────────────┘
                                        │
                                        ▼
                    ┌───────────────────────────────────────┐
                    │        Strands Agent (Bedrock)         │
                    │  system prompt: "run quietly, surface  │
                    │  only for a real decision, never       │
                    │  execute — draft and wait"             │
                    │                                         │
                    │  tools (umash/tools.py):                │
                    │   • build_journey_plan(died_in,rest_in) │
                    │   • classify_phase(task)                │
                    │   • classify_consequence(task,deadline) │
                    │   • draft_notice(target,task,name)      │
                    │   • schedule_followup(task,deadline)    │
                    │   • track_confirmation(task,ack)        │
                    └───────────────────┬─────────────────────┘
                                        │  every tool calls into ▼
                    ┌───────────────────────────────────────┐
                    │   DETERMINISTIC POLICY (umash/policy/)  │
                    │                                         │
                    │   phases.py       phase ordering +      │
                    │                   task→phase routing    │
                    │   consequence.py  ROUTINE vs WEIGHTY;    │
                    │                   the batch-vs-escalate  │
                    │                   rule (the safety core) │
                    │   jurisdictions.py  KE / UK / US packs   │
                    │                   as DATA + cross-border │
                    │                   repatriation branch    │
                    └───────────────────┬─────────────────────┘
                                        │
                                        ▼
        ┌───────────────────────────────────────────────────────┐
        │  routine + low-stakes ──▶ drafted quietly, BATCHED into │
        │                           one approval                  │
        │  weighty / irreversible / ──▶ ESCALATED one at a time,  │
        │  time-critical / legal        with tradeoffs; NEVER     │
        │                               executed autonomously     │
        └───────────────────────────────┬───────────────────────┘
                                        ▼
                        human decides ──▶ mark done · track
                        confirmation · schedule follow-up
                                        ▼
                          phased running-status output
```

## Why the deterministic layer

Whether something needs a grieving person's decision must not depend on a
model's phrasing or mood. So:

- **`consequence.py`** is the safety core. A narrow keyword set (money leaving,
  irreversible commitments, legal signatures, benefit claims) marks a task
  WEIGHTY. Everything else is ROUTINE and gets batched. Deadlines drive
  *urgency ordering*, not escalation.
- **`jurisdictions.py`** holds the country packs as data, so adding a country
  never touches the agent. Cross-border cases prepend the repatriation branch.
- **`phases.py`** orders the journey (immediate → funeral → admin) and routes
  free-text tasks to a phase.

The agent (`agent.py`) composes these via the six tools. `run_offline()` walks
the same policy with no model call, which is how the demo and tests prove the
core behavior without AWS creds.

## Data flow for the demo scenario

Profile: *father died in Nairobi (KE), to be laid to rest in the UK.*

1. `build_journey_plan("KE","UK")` → cross-border detected → repatriation branch
   prepended → 18 tasks across three phases.
2. Each task → `classify_consequence` → 13 routine, 5 weighty.
3. Routine 13 → batched into one approval.
4. Weighty 5, ordered by urgency → surfaced one at a time:
   hospital-bill-release (2d), repatriate-vs-bury (3d), embassy paperwork,
   estate succession, NSSF survivor benefit (30d).
5. Nothing is executed. Every weighty step waits for the human.

## Deployment

- Local: `python demo.py` (Bedrock) or `--offline` (no creds).
- **AgentCore**: the agent is a standard Strands agent, so it deploys to Bedrock
  AgentCore for the hackathon's Technical bonus and a live demo link.
