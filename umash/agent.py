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
the entire journey after a death, across four phases:
- IMMEDIATE (the moment of death and the acute first days): a pronouncement of
  death, the organ-donation decision, locating the will and funeral wishes,
  care for dependents and pets, registering the death, the mortuary and its
  clock, the hospital bill, the funeral director, and repatriation if the body
  must cross borders.
- FUNERAL (days to a week): burial vs cremation, venue, officiant and order of
  service, casket, hearse, notices, contributions, catering.
- ADMIN / ESTATE (weeks to months): banks, insurers, benefits, tax, creditors,
  utilities, subscriptions, the estate.
- AFTERCARE (months to a year+): closing digital and social accounts,
  transferring the vehicle and property, personal effects, a headstone,
  memorials, and grief support for the living.

The plan is jurisdiction-aware (KE, UK, US, plus cross-border repatriation) and,
when a family's tradition is known, faith-aware: pass `faith` to
build_journey_plan to add the right rites and pull the funeral to its customary
window (a Muslim or Jewish case compresses to about a day). Never assume a
faith; only apply one the family gives you.

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


def build_agent(model_id: str | None = None, callback_handler=None):
    """Construct the Strands agent on Bedrock. Requires AWS creds with Bedrock.

    Credential/region resolution uses the standard AWS chain, with optional
    Umash-specific overrides:
      - AWS profile: env UMASH_AWS_PROFILE, else AWS_PROFILE. If neither is set,
        boto3's default credential resolution is used (default profile, instance
        role, container role, etc.) — nothing account-specific is assumed.
      - Region: env AWS_REGION, else us-east-1.
      - Model: `model_id` arg, else env UMASH_MODEL_ID, else DEFAULT_MODEL_ID.
      - Guardrail (optional): env UMASH_GUARDRAIL_ID + UMASH_GUARDRAIL_VERSION
        (default DRAFT). Create one with scripts/create_guardrail.py.

    A `callback_handler` (any callable Strands accepts) can be passed to observe
    the agent's streaming events — used by `demo.py --verbose` to print each
    tool call as it fires, making the Strands tool use visible on screen.

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

    model_kwargs = {
        "boto_session": session,
        "model_id": model_id or os.environ.get("UMASH_MODEL_ID") or DEFAULT_MODEL_ID,
    }

    # Optional Amazon Bedrock Guardrail. Umash's real injection defense is
    # architectural — the model holds no tool that can file, pay, or send, and
    # the batch-vs-escalate safety call is deterministic code, not model output
    # — so a hijacked model can at worst produce bad text, never a real action.
    # A guardrail adds defense-in-depth (prompt-injection filtering, PII
    # redaction of decedent data, off-topic blocking). Attach one by setting
    # UMASH_GUARDRAIL_ID (and optionally UMASH_GUARDRAIL_VERSION, default DRAFT).
    guardrail_id = os.environ.get("UMASH_GUARDRAIL_ID")
    if guardrail_id:
        model_kwargs["guardrail_id"] = guardrail_id
        model_kwargs["guardrail_version"] = os.environ.get("UMASH_GUARDRAIL_VERSION", "DRAFT")
        # Mask (not block) so a grieving family never hits a hard wall; the
        # policy layer remains the real gate regardless.
        model_kwargs["guardrail_redact_input"] = True
        model_kwargs["guardrail_redact_output"] = True

    model = BedrockModel(**model_kwargs)
    agent_kwargs = {"model": model, "tools": ALL_TOOLS, "system_prompt": SYSTEM_PROMPT}
    if callback_handler is not None:
        agent_kwargs["callback_handler"] = callback_handler
    return Agent(**agent_kwargs)


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
