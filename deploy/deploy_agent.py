"""Register the pushed Umash image as an Amazon Bedrock AgentCore Runtime.

Run AFTER building and pushing the ARM64 image to ECR (see deploy/README.md).
Edit ACCOUNT / REGION / ROLE_ARN or supply them via environment variables.

    AWS_REGION            deploy region (default us-east-1)
    UMASH_AWS_PROFILE     AWS profile to use (default simi-ops)
    UMASH_ECR_IMAGE       full ECR image URI (…/umash:latest)
    UMASH_RUNTIME_ROLE    IAM execution role ARN for the runtime
"""

from __future__ import annotations

import os
import sys

import boto3


def main() -> int:
    region = os.environ.get("AWS_REGION", "us-east-1")
    profile = os.environ.get("UMASH_AWS_PROFILE", "simi-ops")
    image = os.environ.get("UMASH_ECR_IMAGE")
    role_arn = os.environ.get("UMASH_RUNTIME_ROLE")

    session = boto3.Session(profile_name=profile, region_name=region)
    if not image:
        account = session.client("sts").get_caller_identity()["Account"]
        image = f"{account}.dkr.ecr.{region}.amazonaws.com/umash:latest"
    if not role_arn:
        print("Set UMASH_RUNTIME_ROLE to the AgentCore execution role ARN.",
              file=sys.stderr)
        return 2

    client = session.client("bedrock-agentcore-control")
    resp = client.create_agent_runtime(
        agentRuntimeName="umash",
        agentRuntimeArtifact={
            "containerConfiguration": {"containerUri": image},
        },
        networkConfiguration={"networkMode": "PUBLIC"},
        roleArn=role_arn,
        lifecycleConfiguration={
            "idleRuntimeSessionTimeout": 300,   # 5 min
            "maxLifetime": 1800,                # 30 min
        },
    )
    print("Agent Runtime created.")
    print("ARN:   ", resp["agentRuntimeArn"])
    print("Status:", resp["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
