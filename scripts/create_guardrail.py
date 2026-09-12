"""Create the Umash Amazon Bedrock Guardrail.

Provisions a guardrail tuned for a grief-admin agent and prints its ID, which
you then wire into the agent via:

    export UMASH_GUARDRAIL_ID=<printed id>
    export UMASH_GUARDRAIL_VERSION=DRAFT   # or a published version number

Why a guardrail here (defense-in-depth, not the primary defense):
  Umash's real injection protection is architectural — the agent holds no tool
  that can file, pay, or send anything, and the batch-vs-escalate safety
  decision is deterministic code (umash/policy), not model output. So a
  hijacked model can at worst produce bad text. The guardrail adds:
    - decedent PII redaction (names, contact, financial identifiers),
    - denied topics (medical/legal/financial *advice* — Umash coordinates, it
      does not advise),
    - prompt-attack filtering.

Run:  python scripts/create_guardrail.py            # uses UMASH_AWS_PROFILE / default chain
      python scripts/create_guardrail.py --profile simi-ops --region us-east-1
"""

from __future__ import annotations

import argparse
import os
import sys

import boto3


def main() -> int:
    ap = argparse.ArgumentParser(description="Create the Umash Bedrock guardrail")
    ap.add_argument("--profile", default=os.environ.get("UMASH_AWS_PROFILE"))
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = ap.parse_args()

    session = (boto3.Session(profile_name=args.profile, region_name=args.region)
               if args.profile else boto3.Session(region_name=args.region))
    bedrock = session.client("bedrock")

    grief_block_message = (
        "I can help you organize and prepare this, but I can't advise on it. "
        "For this step you may want a professional — I'll note it in your plan."
    )

    try:
        resp = bedrock.create_guardrail(
            name="umash-grief-coordinator",
            description="Guardrail for the Umash aftermath-coordination agent: "
                        "PII redaction of decedent data, no professional advice, "
                        "prompt-attack filtering.",
            blockedInputMessaging=grief_block_message,
            blockedOutputsMessaging=grief_block_message,
            # Filter prompt attacks (injection) and clearly harmful content.
            contentPolicyConfig={
                "filtersConfig": [
                    {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"},
                    {"type": "MISCONDUCT", "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
                ]
            },
            # Umash coordinates; it must not pose as a lawyer/doctor/financial advisor.
            topicPolicyConfig={
                "topicsConfig": [
                    {"name": "ProfessionalAdvice",
                     "definition": "Giving definitive legal, medical, or financial "
                                   "advice or instructions the family should rely on "
                                   "instead of a qualified professional.",
                     "examples": [
                         "Tell me exactly how to file for probate so I don't need a lawyer.",
                         "What should I invest the life-insurance payout in?",
                         "Is this cause of death medically correct?",
                     ],
                     "type": "DENY"},
                ]
            },
            # Redact decedent/family PII from model I/O (anonymize, don't block).
            sensitiveInformationPolicyConfig={
                "piiEntitiesConfig": [
                    {"type": "NAME", "action": "ANONYMIZE"},
                    {"type": "EMAIL", "action": "ANONYMIZE"},
                    {"type": "PHONE", "action": "ANONYMIZE"},
                    {"type": "ADDRESS", "action": "ANONYMIZE"},
                    {"type": "CREDIT_DEBIT_CARD_NUMBER", "action": "ANONYMIZE"},
                    {"type": "US_BANK_ACCOUNT_NUMBER", "action": "ANONYMIZE"},
                    {"type": "US_SOCIAL_SECURITY_NUMBER", "action": "ANONYMIZE"},
                ]
            },
        )
    except Exception as e:  # noqa: BLE001
        print(f"Failed to create guardrail: {e}", file=sys.stderr)
        print("The profile needs bedrock:CreateGuardrail permission.", file=sys.stderr)
        return 1

    gid = resp["guardrailId"]
    print("Guardrail created.")
    print(f"  id:      {gid}")
    print(f"  arn:     {resp['guardrailArn']}")
    print(f"  version: {resp['version']}")
    print("\nWire it into the agent:")
    print(f"  export UMASH_GUARDRAIL_ID={gid}")
    print(f"  export UMASH_GUARDRAIL_VERSION=DRAFT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
