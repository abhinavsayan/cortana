# Implementation Plan - Migrate Sub-agents to Google ADK

This plan outlines the steps to transition the current internal "Sub-Agent" architecture to a modular, external architecture using the **Google Agent Development Kit (ADK)**.

## User Review Required

> [!IMPORTANT]
> This change introduces a network boundary between the Voice Agent and the Sub-agents. Sub-agents will now run as independent services (either locally as separate processes or hosted on Cloud Run/Vertex AI).

> [!NOTE]
> We will need to decide on the communication protocol. Google ADK typically exposes agents via HTTP/REST or through the Vertex AI Agent Engine.

## Proposed Communication Mechanism

The Voice Agent and Sub-agents will communicate over **async HTTP/REST** using JSON payloads:

1.  **Hosting**: Each ADK Sub-agent runs as a standalone service (using `adk run` or containerized).
2.  **Discovery**: The main application loads the URL for each sub-agent from environment variables (e.g., `CRM_AGENT_URL=http://localhost:8001`).
3.  **Dispatch**: The `TaskDispatcher` uses `httpx` to POST the task payload to the sub-agent.
4.  **Response**: The sub-agent processes the request. For data tasks (CRM), it returns a standard JSON object. For text tasks (Chat), it can use **HTTP Streaming** to send packets of tokens.

## Streaming LLM Output

> [!TIP]
> Yes, this architecture supports streaming! 

- **Sub-agent side**: The Google ADK `Agent` can be configured to yield tokens using `AsyncGenerator`. When hosted via FastAPI, this becomes a chunked HTTP response.
- **Main Agent side**: The `TaskDispatcher` will be updated to use `httpx.stream`. 
- **LiveKit Integration**: While standard `function_tool` results are usually collected before the main LLM speaks, we can use the `BaseVoiceAgent.session.generate_reply` to inject streaming content directly if the sub-agent is performing a long-form generation.

## Proposed Changes

### 1. Externalize Sub-agent Logic [NEW]
We will create a new directory `external_agents/` to house the ADK-based implementations.

#### [NEW] `external_agents/crm_agent.py`
A standalone ADK agent that wraps the existing `CRMSubAgent` logic. It will use the `google-adk` library to define tools and agent behavior.

#### [NEW] `external_agents/email_agent.py`
A standalone ADK agent for email tasks.

### 2. Update Internal Dispatcher [MODIFY]
The `TaskDispatcher` will be refactored to act as a proxy/client.

#### [MODIFY] [dispatcher.py](file:///Users/batman/dev/cortana/subagents/dispatcher.py)
Update `request()` and `fire()` to make HTTP calls to the external ADK agent endpoints instead of calling local `run()` methods.

#### [MODIFY] [base.py](file:///Users/batman/dev/cortana/subagents/base.py)
Introduce a `RemoteSubAgent` class that implements the `BaseSubAgent` interface but delegates to a URL.

### 3. Environment & Dependencies
- Add `google-adk` to `requirements.txt`.
- Define `CRM_AGENT_URL`, `EMAIL_AGENT_URL` etc. in `.env`.

## Verification Plan

### Automated Tests
1. **Mock Server Test**: Use `pytest` and `httpx` to verify the `TaskDispatcher` correctly formats requests to the remote agents.
2. **ADK Local Run**: Start the new ADK agents locally using `adk run` and verify they respond to manual `curl` requests.

### Manual Verification
1. Run the `worker.py` and trigger a voice command that requires CRM lookup.
2. Observe the logs to ensure the call is dispatched to the external agent and the result is returned correctly.
3. **Test Streaming**: Trigger the `ChatSubAgent` and verify that the console logs show tokens arriving incrementally before the final result is aggregated.
