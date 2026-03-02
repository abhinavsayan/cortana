# Voice Agent POC — LiveKit + Ollama + ElevenLabs

## Overview

Build a low-latency, modular voice agent platform using **LiveKit Agents** as the orchestration framework. Multiple deployable voice agents (e.g. SellerAgent, CustomerAgent) each own their voice identity and LLM config. Voice agents delegate tasks to specialised sub-agents (email, CRM, chat) via a TaskDispatcher that supports both fire-and-forget and blocking request/response patterns.

See [design.md](docs/design.md) for architecture and implementation details.
See [progress.md](docs/progress.md) for current status and deferred areas.

---

## Tech Stack

| Component       | Provider            | Details                                                         |
| --------------- | ------------------- | --------------------------------------------------------------- |
| Orchestration   | LiveKit Agents      | Python SDK `~=1.4`                                             |
| Transport       | LiveKit Server      | Local dev mode or LiveKit Cloud                                 |
| VAD             | Silero              | `livekit-plugins-silero` — speech start/end detection           |
| STT             | Deepgram            | `livekit-plugins-deepgram` — Nova-3 streaming                  |
| LLM             | Per-agent config    | Ollama local, Groq, or OpenAI — declared per agent              |
| TTS             | Per-agent config    | ElevenLabs or Cartesia — declared per agent with named voice    |
| Turn Detection  | LiveKit built-in    | Multilingual turn detector model                                |
| Noise Cancel    | LiveKit BVC         | `livekit-plugins-noise-cancellation`                            |

---

## Project Structure

```
cortana/
│
├── agents/
│   ├── __init__.py
│   ├── base.py              # BaseVoiceAgent: on_enter swaps session plugins, handoff logic
│   ├── seller.py            # SellerAgent — entry point for seller deployment
│   └── customer.py          # CustomerAgent — entry point for customer deployment
│
├── config/
│   ├── __init__.py
│   ├── settings.py          # Env loading, AGENT_NAME, fail-fast validation at startup
│   ├── profiles.py          # Named presets (VOICES, STT_MODELS, LLM_MODELS)
│   └── logging_config.py    # configure_logging() — call once at startup
│
├── tools/
│   ├── __init__.py
│   └── dispatch.py          # @function_tools used by voice agents → TaskDispatcher
│
├── subagents/
│   ├── __init__.py
│   ├── base.py              # BaseSubAgent (ABC), SubAgentMode, TaskTimeoutError
│   ├── dispatcher.py        # TaskDispatcher: fire() and request()
│   ├── email.py             # EmailSubAgent — FIRE_AND_FORGET
│   ├── crm.py               # CRMSubAgent   — REQUEST_RESPONSE, timeout=8s
│   └── chat.py              # ChatSubAgent  — TBD
│
├── demos/
│   ├── demo.html            # Browser demo UI
│   └── demo_server.py       # Local demo server
│
├── scripts/
│   └── get_token_for_play.py  # Generate LiveKit token for playground testing
│
├── docs/
│   ├── design.md            # Architecture and implementation details
│   ├── progress.md          # Current status and deferred areas
│   └── *.excalidraw         # Architecture diagrams
│
├── envs/
│   ├── .env.seller          # AGENT_NAME=seller + API keys (gitignored)
│   ├── .env.customer        # AGENT_NAME=customer + API keys (gitignored)
│   ├── .env.seller.example  # committed template
│   └── .env.customer.example
│
├── worker.py                # entrypoint(), AGENT_REGISTRY, AgentSession bootstrap
└── requirements.txt
```

---

## Prerequisites

### 1. Ollama (Local LLM)
```bash
ollama pull mistral
curl http://localhost:11434/api/tags   # verify
```

### 2. LiveKit Server
```bash
brew install livekit
livekit-server --dev        # runs on ws://localhost:7880
```

### 3. API Keys
- **Deepgram**: https://console.deepgram.com — free tier available
- **ElevenLabs**: https://elevenlabs.io — 10k chars/month free

---

## Running the Agent

```bash
# 1. Start Ollama
ollama serve

# 2. Start LiveKit
livekit-server --dev

# 3. Install dependencies
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### Demo Dashboard (recommended for local dev)

The demo dashboard is the easiest way to test an agent end-to-end. It runs a local web server that handles room creation and joining.

**Terminal 1 — Demo server:**
```bash
source venv/bin/activate
python demos/demo_server.py                             # reads envs/.env.customer by default
ENV_FILE=envs/.env.seller python demos/demo_server.py   # for seller agent
```
Open http://localhost:8080, type a room name, and click **+ Join**.

**Terminal 2 — Agent worker:**
```bash
source venv/bin/activate
ENV_FILE=envs/.env.customer python worker.py connect --room <room-name>
# e.g. python worker.py connect --room demo-room
```

> **Why `connect` mode?** With a self-hosted LiveKit server, `dev` mode job dispatch can silently fail — the job is accepted but the worker never connects to the room. `connect` mode attaches directly to a named room, bypassing dispatch. It's reliable for local development.

### Other Run Modes
- **Console mode** (text-only, no audio): `ENV_FILE=envs/.env.seller python worker.py console`
- **Playground**: https://agents-playground.livekit.io — use with `worker.py dev` against LiveKit Cloud
- **Dev mode** (LiveKit Cloud only): `ENV_FILE=envs/.env.seller python worker.py dev`

---

## Latency Tuning Notes

1. **LLM**: Mistral 7B → ~500-1000ms TTFT locally. Switch to `groq-fast` preset for cloud-fast inference.
2. **TTS**: `eleven_turbo_v2_5` is ElevenLabs' lowest-latency model.
3. **Barge-in**: Built into `AgentSession` — VAD cancels TTS/LLM generation automatically.
4. **Sub-agent timeouts**: Keep `REQUEST_RESPONSE` sub-agents under 3s for natural conversation feel.

---

## Swapping Components

```python
# Switch to Groq for faster LLM
llm_profile = LLM_MODELS["groq-fast"]

# Switch TTS to Cartesia
voice_profile = VOICES["sonic"]

# Switch STT to Spanish
stt_profile = STT_MODELS["deepgram-es"]
```

---

## Key References

- Agents quickstart: https://docs.livekit.io/agents/start/voice-ai-quickstart/
- Multi-agent handoff: https://docs.livekit.io/agents/build/workflows/
- Tool calling: https://docs.livekit.io/agents/build/tools/
- Ollama plugin: https://docs.livekit.io/agents/models/llm/plugins/ollama/
- ElevenLabs TTS: https://docs.livekit.io/agents/models/tts/plugins/elevenlabs/
- Deepgram STT: https://docs.livekit.io/agents/models/stt/plugins/deepgram/
- Agents Playground: https://agents-playground.livekit.io

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Ollama connection refused | Run `ollama serve`. Check `curl http://localhost:11434/api/tags` |
| Agent never joins room (`dev` mode) | Use `connect` mode: `python worker.py connect --room <room-name>`. Job dispatch is unreliable with self-hosted LiveKit. |
| Slow LLM responses | Switch to `groq-fast` preset |
| ElevenLabs quota exceeded | Switch to Deepgram TTS for testing |
| Agent not responding | Check `DEEPGRAM_API_KEY` and `ELEVEN_API_KEY` in `.env` |
| Sub-agent timeout | Increase `timeout` on the `BaseSubAgent` subclass |
| Echo / feedback loop | Use headphones during testing |
| Tools not working with Ollama | Use `mistral` or `llama3.1` — they support function calling |
| Port 8080 already in use | `lsof -ti :8080 \| xargs kill -9` |
