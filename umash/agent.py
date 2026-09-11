"""The Umash agent + the deterministic journey the demo can run offline.

`build_agent()` returns a Strands agent on Bedrock with the six tools and the
"autonomous, surface only for a real decision" system prompt.

`run_offline(profile)` walks the same policy layer WITHOUT calling a model, so
the product's core behavior (phased plan, batch-vs-escalate) is demonstrable and
testable with no AWS creds.
"""

from __future__ import annotations

import json
import os

from .policy import classify, tasks_for
from .policy.phases import PHASE_ORDER, PHASE_LABEL
from .tools import ALL_TOOLS

SYSTEM_PROMPT = """\
You are Umash ("Afterward"), a companion that helps a grieving family through
the entire journey after a death: the immediate logistics (registering the
death, the mortuary, the hospital bill, the funeral director, repatriation if
the body must cross borders), the funeral, and the weeks of admin that follow.

Your one rule: run quietly and only surface when there is a real decision to
make. Concretely:
- Use build_journey_plan first to lay out the phased, jurisdiction-aware plan.
- Routine, reversible, low-stakes tasks: prepare drafts quietly and BATCH them
  into a single approval. Do not narrate each one.
- Weighty tasks (money, legal, irreversible, or time-critical) — as determined
  by classify_consequence, never by your own judgement — must be ESCALATED to
  the human ONE AT A TIME, each with the tradeoffs stated plainly.
- You NEVER file, pay, book, or send anything yourself. You draft and wait.
- Write with warmth and plainness, never corporate coldness. This person is
  grieving.

Trust the tools for phase, consequence, and jurisdiction steps — they are the
policy. Your job is ordering, tone, and deciding what to put in front of the
human versus what to keep quiet.
"""

# Amazon Nova Pro — a solid default that avoids the Anthropic "legacy model /
# 30-day access" gate. Override per-call or via UMASH_MODEL_ID.
# Nova Lite (us.amazon.nova-lite-v1:0) is a cheaper/faster fallback.
DEFAULT_MODEL_ID = "us.amazon.nova-pro-v1:0"


def build_agent(model_id: str | None = None):
    """Construct the Strands agent on Bedrock. Requires AWS creds with Bedrock.

    Credential/region resolution uses the standard AWS chain, with optional
    Umash-specific overrides:
      - AWS profile: env UMASH_AWS_PROFILE, else AWS_PROFILE. If neither is set,
        boto3's default credential resolution is used (default profile, instance
        role, container role, etc.) — nothing account-specific is assumed.
      - Region: env AWS_REGION, else us-east-1.
      - Model: `model_id` arg, else env UMASH_MODEL_ID, else DEFAULT_MODEL_ID.

    Note: the account used must have Bedrock *invoke* access, not just list.
    """
    import boto3
    from strands import Agent
    from strands.models import BedrockModel

    profile = os.environ.get("UMASH_AWS_PROFILE") or os.environ.get("AWS_PROFILE")
    region = os.environ.get("AWS_REGION", "us-east-1")

    # Only pass profile_name when one is explicitly set; otherwise let boto3 use
    # its normal default credential chain.
    session = (boto3.Session(profile_name=profile, region_name=region)
               if profile else boto3.Session(region_name=region))
    model = BedrockModel(
        boto_session=session,
        model_id=model_id or os.environ.get("UMASH_MODEL_ID") or DEFAULT_MODEL_ID,
    )
    return Agent(model=model, tools=ALL_TOOLS, system_prompt=SYSTEM_PROMPT)


def run_offline(died_in: str, rest_in: str | None, deceased_name: str) -> dict:
    """Deterministic walkthrough of the journey — no model call.

    Returns a structured result: the phased plan, the batched routine items, and
    the ordered list of weighty escalations (most urgent first).
    """
    tasks = tasks_for(died_in, rest_in)
    phases = {p.value: {"label": PHASE_LABEL[p], "routine": [], "escalations": []}
              for p in PHASE_ORDER}

    escalations = []
    for t in tasks:
        v = classify(t.title, t.deadline_days)
        entry = {"title": t.title, "target": t.target,
                 "deadline_days": t.deadline_days, "note": t.note,
                 "reasons": v.reasons}
        if v.escalates:
            phases[t.phase.value]["escalations"].append(entry)
            escalations.append({**entry, "phase": t.phase.value})
        else:
            phases[t.phase.value]["routine"].append(entry)

    # Order escalations by urgency: has-deadline first, soonest first.
    escalations.sort(key=lambda e: (e["deadline_days"] is None,
                                    e["deadline_days"] if e["deadline_days"] is not None else 999))

    routine_count = sum(len(p["routine"]) for p in phases.values())
    return {
        "died_in": died_in.upper(),
        "rest_in": (rest_in.upper() if rest_in else died_in.upper()),
        "cross_border": bool(rest_in and rest_in.upper() != died_in.upper()),
        "deceased_name": deceased_name,
        "phases": phases,
        "routine_count": routine_count,
        "escalations": escalations,
    }
