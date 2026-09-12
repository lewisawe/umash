"""Amazon Bedrock AgentCore Runtime entrypoint for Umash.

Wraps the existing Strands agent (umash.agent.build_agent) in the AgentCore
runtime contract so it can be deployed to a managed, isolated microVM with
observability and session isolation.

The AgentCore SDK (`BedrockAgentCoreApp`) provides the required `/invocations`
POST and `/ping` GET endpoints and runs on port 8080 automatically, so we only
declare the entrypoint handler.

Contract (per AgentCore Runtime requirements):
  - platform linux/arm64
  - /invocations POST + /ping GET  (provided by BedrockAgentCoreApp)
  - port 8080
  - deployed as an ECR container image

Payload shape:
  {"prompt": "My father passed in Nairobi; he lived in the UK. Where do I start?"}

The deterministic policy layer still owns all safety-critical decisions; this
file only exposes the conversational agent over the runtime.
"""

from __future__ import annotations

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from umash.agent import build_agent

app = BedrockAgentCoreApp()

# Build the agent once at cold start; reused across invocations in the session.
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


@app.entrypoint
def handler(payload: dict, context=None) -> dict:
    """One agent invocation.

    `payload` is the JSON body sent to /invocations. We accept either
    {"prompt": "..."} or {"input": {"prompt": "..."}} for compatibility with
    both the AgentCore SDK and the raw-container examples.
    """
    prompt = payload.get("prompt")
    if prompt is None and isinstance(payload.get("input"), dict):
        prompt = payload["input"].get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return {"error": "Provide a non-empty 'prompt' string."}

    result = _get_agent()(prompt)
    # Strands returns a rich result; expose its text message for the runtime.
    message = getattr(result, "message", result)
    return {"message": message}


if __name__ == "__main__":
    # Local run: serves /invocations and /ping on port 8080, matching the
    # container's runtime. Requires AWS creds with Bedrock invoke access.
    app.run()
