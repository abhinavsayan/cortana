# Design — Voice Agent Platform

## Architecture

### System Layers

```
User (Browser / Phone)
        │
        ▼  WebRTC / SIP
┌─────────────────────┐
│   LiveKit Server    │  (local dev: livekit-server --dev  |  prod: LiveKit Cloud)
│       (SFU)         │
└──────────┬──────────┘
           │ audio frames
           ▼
┌──────────────────────────────────────────────────────────┐
│                  LiveKit Voice Layer                      │
│                                                          │
│   ┌──────────────────┐      ┌──────────────────┐        │
│   │   SellerAgent    │◄────►│  CustomerAgent   │        │
│   │  (voice, STT,    │      │  (voice, STT,    │        │
│   │   own LLM/TTS)   │      │   own LLM/TTS)   │        │
│   └────────┬─────────┘      └────────┬─────────┘        │
│            │ @function_tool           │                  │
│            └────────────┬────────────┘                  │
│                         ▼                               │
│                  TaskDispatcher                          │
│           (local in POC / HTTP or queue in prod)         │
└─────────────────────────┬────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  Email   │   │   CRM    │   │  Chat    │
    │  Agent   │   │  Agent   │   │  Agent   │
    │  (async) │   │  (sync)  │   │  (TBD)   │
    └──────────┘   └──────────┘   └──────────┘
```

### Voice Pipeline (per agent)

```
VAD (Silero) → STT (Deepgram) → LLM (per-agent config) → TTS (per-agent voice)
```

All stages stream. LiveKit handles WebRTC transport, barge-in, and turn detection automatically.

### Task Dispatch Patterns

```
Fire & Forget (e.g. email)           Request / Response (e.g. CRM lookup)
──────────────────────────           ─────────────────────────────────────
tool called                          tool called
  → dispatcher.fire(...)               → dispatcher.request(..., timeout=8s)
  → returns immediately                → awaits result (or TaskTimeoutError)
  → agent speaks confirmation          → agent speaks result or fallback
  → sub-agent runs in background
```

---

## Agent Class Design

### Handoff Modes

```
1. Fresh start (no handoff)
   Session begins → A1.greet(ctx=None)
   → "Hi, I'm the sales team, how can I help?"

2. Incoming handoff (A1 → A2)
   A1 transfers with context → A2.greet(ctx=HandoffContext(status=NEW))
   → "Hi, I've been brought in to help with your billing issue — let me take a look."

3. Return handoff (A2 → A1, with result)
   A2 completes → A1.greet(ctx=HandoffContext(status=RETURN))
   → "Great news — our support team got that sorted. I'm still here if you need anything else."
```

**Conversation history is NOT carried in HandoffContext.** LiveKit's `AgentSession` carries the full chat history automatically across handoffs. `reason` is a short label to shape the greeting tone only.

### HandoffContext

```python
class HandoffStatus(Enum):
    NEW    = "new"     # incoming handoff
    RETURN = "return"  # returning from sub-task

@dataclass
class HandoffContext:
    from_agent:    str
    status:        HandoffStatus
    reason:        str
    session_state: dict = field(default_factory=dict)  # structured facts
    metadata:      dict = field(default_factory=dict)  # handoff flags
```

### BaseVoiceAgent

- Subclasses declare `voice_profile`, `stt_profile`, `llm_profile`, `instructions` as class variables.
- `on_enter` swaps session plugins to this agent's declared profiles, then calls `greet()`.
- `greet()` generates a contextual opening based on handoff status.
- `on_exit` logs active time.
- `update_state(**kwargs)` accumulates structured facts during the conversation.
- `_state` travels to the next agent via `HandoffContext.session_state`.

### Plugin Factories (config/profiles.py)

Profiles are data. Factories turn them into live plugin instances. Adding a new provider = one new `elif` in the factory, no changes to any agent.

```python
def build_tts(profile: VoiceProfile) -> TTS: ...
def build_stt(profile: STTProfile)   -> STT: ...
def build_llm(profile: LLMProfile)   -> LLM: ...
```

---

## Session & Context Management

### Two Layers of Context

```
1. Conversation history    → LiveKit manages automatically. Full transcript sent to LLM each turn.
                             No code needed. Works across handoffs.

2. Structured session state → Plain dict on the agent. Manually updated during the call.
                              Travels in HandoffContext.session_state on handoff.
```

Calls are transactional — short and focused. Raw history is sufficient; no summarisation needed.

### State Injection at Greet

State is injected only at greet time. The ongoing transcript handles the rest — the LLM naturally retains what was said each turn.

```python
async def greet(self, ctx: HandoffContext | None) -> None:
    state_ctx = self._state_context()   # formats _state as bullet list

    if ctx is None:
        instruction = f"Greet the user warmly and ask how you can help.{state_ctx}"
    elif ctx.status == HandoffStatus.NEW:
        instruction = f"... Introduce yourself. Reason: {ctx.reason}.{state_ctx}"
    elif ctx.status == HandoffStatus.RETURN:
        instruction = f"... Acknowledge outcome: {ctx.reason}.{state_ctx}"

    self.session.generate_reply(instructions=instruction)
```

### State Carried on Handoff

```python
@function_tool
async def transfer_to_support(self, context: RunContext):
    ctx = HandoffContext(
        from_agent="seller",
        status=HandoffStatus.NEW,
        reason="Customer needs help with a billing issue.",
        session_state=self._state,   # ← structured facts travel to new agent
    )
    return CustomerAgent(handoff_context=ctx), "Let me bring in our support team."
```

---

## Task Dispatcher

```python
class TaskDispatcher:
    async def fire(self, task_type, payload) -> None:
        # asyncio.create_task — fire and forget
        # POC: local async task | Prod: publish to SQS/Redis

    async def request(self, task_type, payload) -> dict:
        # asyncio.wait_for with agent.timeout
        # raises TaskTimeoutError on timeout
```

Sub-agents registered at startup in `tools/dispatch.py`. New sub-agent = implement `BaseSubAgent`, register once.

---

## Configuration & Secrets

One `.env` file per deployment. `ENV_FILE` shell var selects which to load. Validation is fail-fast — all required vars checked at import time before the worker accepts any calls.

```bash
ENV_FILE=.env.seller python worker.py dev
ENV_FILE=.env.customer python worker.py dev
```

Required vars: `AGENT_NAME`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, `ELEVEN_API_KEY`

Optional: `OLLAMA_BASE_URL` (defaults to `http://localhost:11434/v1`)

---

## Observability

Plain text logs via standard Python `logging`. No external services for the POC.

### Log Format

```
2026-03-02 14:23:01 INFO  [seller] session_start room=room_abc123
2026-03-02 14:23:01 INFO  [seller] agent_enter  handoff=none
2026-03-02 14:23:04 INFO  [seller] handoff      to=customer reason="billing issue"
2026-03-02 14:23:04 INFO  [customer] agent_enter handoff=new from=seller
2026-03-02 14:23:09 INFO  [customer] agent_exit  active=5.0s
2026-03-02 14:23:09 INFO  [seller] agent_enter  handoff=return from=customer
2026-03-02 14:23:15 INFO  [seller] session_end
2026-03-02 14:23:07 ERROR [customer] error type=TaskTimeoutError msg="crm did not respond within 8s"
```

### Latency

Turn latency is emitted automatically by LiveKit. To surface TTFT and TTS first-byte during development:

```python
logging.getLogger("livekit.agents").setLevel(logging.DEBUG)
```
