# Deploying Umash to Amazon Bedrock AgentCore

This packages the Umash conversational agent (`umash.agent.build_agent`) for the
**Amazon Bedrock AgentCore Runtime** — a managed, isolated microVM per session
with built-in observability. The deterministic policy layer is unchanged; this
only exposes the agent over the runtime contract.

> The safety-critical logic (phases, consequence tiers, batch-vs-escalate,
> jurisdiction packs, faith urgency) stays in `umash/policy/` as code. AgentCore
> hosts the model-facing agent; it does not move any safety decision into the model.

## What's here

| File | Purpose |
|------|---------|
| `agentcore_app.py` | Runtime entrypoint. `BedrockAgentCoreApp` provides the required `/invocations` POST and `/ping` GET on port 8080; the handler wraps `build_agent()`. |
| `Dockerfile` | `linux/arm64` image (required by AgentCore), port 8080. |
| `requirements.txt` | Agent + runtime deps (`bedrock-agentcore`, `strands-agents`, `boto3`). |
| `deploy_agent.py` | Registers the pushed image as an AgentCore Runtime. |

## Prerequisites

- AWS credentials with Bedrock **invoke** access and AgentCore permissions.
- An IAM execution role for the runtime (see the AgentCore IAM docs).
- Docker with `buildx` (AgentCore images must be `linux/arm64`).
- Region with AgentCore + your chosen model (default `us-east-1`,
  `us.amazon.nova-pro-v1:0`; override with `AWS_REGION` / `UMASH_MODEL_ID`).

## Option A — Starter toolkit (simplest)

```bash
pip install bedrock-agentcore-starter-toolkit
```

```python
from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session

region = Session().region_name or "us-east-1"
rt = Runtime()
rt.configure(
    entrypoint="deploy/agentcore_app.py",
    requirements_file="deploy/requirements.txt",
    auto_create_execution_role=True,
    auto_create_ecr=True,
    region=region,
    agent_name="umash",
)
rt.launch()      # builds the ARM64 image, pushes to ECR, creates the runtime
```

## Option B — Manual (Docker + ECR + API)

Run from the repository root so the build context includes `umash/`.

```bash
# 1. Build for ARM64
docker buildx create --use
docker buildx build --platform linux/arm64 -f deploy/Dockerfile -t umash:arm64 --load .

# 2. (optional) test locally — needs AWS creds for Bedrock
docker run --platform linux/arm64 -p 8080:8080 \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
  -e AWS_REGION="${AWS_REGION:-us-east-1}" umash:arm64 &
curl localhost:8080/ping
curl -X POST localhost:8080/invocations -H 'Content-Type: application/json' \
  -d '{"prompt":"My father passed in Nairobi; he lived in the UK. Where do I start?"}'

# 3. Push to ECR
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-us-east-1}
aws ecr create-repository --repository-name umash --region "$REGION" || true
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
docker buildx build --platform linux/arm64 -f deploy/Dockerfile \
  -t "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/umash:latest" --push .

# 4. Register the runtime (edit the role ARN inside first)
python deploy/deploy_agent.py
```

## Invoke

```python
import boto3, json
c = boto3.client("bedrock-agentcore", region_name="us-east-1")
r = c.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:us-east-1:<account>:runtime/umash-<suffix>",
    runtimeSessionId="umash-session-000000000000000000000000",  # 33+ chars
    payload=json.dumps({"prompt": "Where do I start?"}),
    qualifier="DEFAULT",
)
print(json.loads(r["response"].read()))
```

## Notes

- The agent's default model avoids the Anthropic legacy-access gate
  (`us.amazon.nova-pro-v1:0`). Set `UMASH_MODEL_ID` to change it.
- No secrets are baked into the image; the runtime supplies AWS credentials.
- For a no-creds walkthrough of the same journey logic, use `python demo.py --offline`.
