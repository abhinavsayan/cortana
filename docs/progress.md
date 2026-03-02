# Progress

## Status: POC scaffolding complete — ready to run

Core implementation is done. The agent can be started with real API keys.

---

## TODO — Pending LLD Discussions

- [x] **Area 2: Agent Class Design** — BaseVoiceAgent internals, lifecycle hooks, plugin swapping on handoff
- [x] **Area 4: Session & Context Management** — session state, conversation history, state on handoff
- [x] **Area 5: Configuration & Secrets** — fail-fast validation, per-deployment `.env` strategy
- [x] **Area 7: Observability** — log levels, latency metrics, tracing across voice → sub-agent
- [ ] **Area 3: Tool Contracts** — tool input/output shapes, error handling per tool, timeout behaviour
  - *Deferred — start with simple LLM conversation, add tools later*
- [ ] **Area 6: Error Handling & Resilience** — Ollama unreachable, STT/TTS failures, sub-agent timeout UX
  - *Deferred — log errors only for now, full resilience strategy later*
- [ ] **Area 8: Testing Strategy** — unit vs integration, mocking sub-agents
  - *Deferred — local demo via console mode is sufficient for POC*

---

## Decisions Made

| Decision | Choice | Reason |
|----------|--------|--------|
| LLM (local) | `mistral:latest` | Already pulled; supports function calling |
| LLM (cloud) | Groq `llama-3.3-70b-versatile` | Low latency, free tier |
| STT | Deepgram Nova-3 | Streaming, low latency |
| TTS | ElevenLabs `eleven_turbo_v2_5` | Lowest latency ElevenLabs model |
| Session state | Plain dict on agent | Calls are short; no need for complex state store |
| Sub-agent transport | Local asyncio tasks | Sufficient for POC; same call site for prod swap |
| Handoff history | LiveKit native | Full transcript automatic; no manual passing needed |

---

## Next Steps

1. Install LiveKit server (`brew install livekit`) and start it
2. Run `pip install -r requirements.txt` in the venv
3. Test with console mode: `ENV_FILE=.env.seller python worker.py console`
4. Test with Playground: `ENV_FILE=.env.seller python worker.py dev` → https://agents-playground.livekit.io
5. Validate handoff flow: seller → customer → seller
6. Validate tool flow: `fetch_customer_profile` (CRM lookup) and `send_follow_up_email`
