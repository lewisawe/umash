# Amazon Bedrock AgentCore Runtime image for Umash.
# Requirements: linux/arm64, port 8080, /invocations + /ping (from the SDK).
FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

# Install the agent + runtime dependencies.
COPY deploy/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The deterministic package (zero third-party deps) and the entrypoint.
COPY umash/ ./umash/
COPY deploy/agentcore_app.py ./agentcore_app.py

# AgentCore Runtime contract.
EXPOSE 8080

# BedrockAgentCoreApp serves /invocations and /ping on 0.0.0.0:8080.
CMD ["python", "-m", "agentcore_app"]
