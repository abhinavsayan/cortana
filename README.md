# Cortana — Voice Agent Platform

A low-latency, modular voice agent platform built on **LiveKit Agents**. Multiple deployable voice agents (SellerAgent, CustomerAgent) each own their voice identity and LLM config, and delegate background tasks to specialised sub-agents via a TaskDispatcher.

## Tech Stack

| Component     | Provider                                    |
| ------------- | ------------------------------------------- |
| Orchestration | LiveKit Agents `~=1.4`                      |
| VAD           | Silero                                      |
| STT           | Deepgram Nova-3 (streaming)                 |
| LLM           | Per-agent — Ollama local, Groq, or OpenAI   |
| TTS           | Per-agent — ElevenLabs or Cartesia          |
| Turn detect   | LiveKit built-in multilingual model         |
| Noise cancel  | LiveKit BVC                                 |

## Quickstart

```bash
# 1. Install Ollama and pull a model
ollama pull mistral

# 2. Start LiveKit dev server
brew install livekit
livekit-server --dev

# 3. Set up Python environment
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 4. Copy and fill in env files
cp envs/.env.seller.example envs/.env.seller
cp envs/.env.customer.example envs/.env.customer
```

Required env vars: `AGENT_NAME`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, `ELEVEN_API_KEY`

### Run with the Demo Dashboard (recommended for local dev)

The demo dashboard is the easiest way to interact with an agent. It handles room creation and joining from the browser.

**Terminal 1 — Demo server:**
```bash
source venv/bin/activate
python demos/demo_server.py                          # reads envs/.env.customer by default
ENV_FILE=envs/.env.seller python demos/demo_server.py  # for seller agent
# Open http://localhost:8080
```

**Terminal 2 — Agent worker (connect mode):**
```bash
source venv/bin/activate
# Type a room name in the browser first, then connect the worker to it:
ENV_FILE=envs/.env.customer python worker.py connect --room <room-name>
```

> **Why `connect` mode?** With a self-hosted LiveKit server (e.g. local Docker), the `dev` mode job dispatch mechanism can silently fail — the job is accepted but the worker subprocess never connects. `connect` mode bypasses dispatch entirely and attaches directly to a named room. It's the reliable path for local development.

The full flow:
1. Start demo server → open browser → type a room name and click **+ Join**
2. Start worker with the same room name → agent joins immediately
3. Start speaking — STT / LLM / TTS events appear in the Pipeline panel

The dashboard has three panels:

| Panel | What it shows |
|---|---|
| Rooms | All active LiveKit rooms with participant count and a Join button (auto-refreshes every 5 s) |
| Connection | Status orb, current room name, agent state pill (idle / listening / thinking / speaking), Mute + Leave controls |
| Pipeline | Live timestamped feed — STT transcriptions, LLM thinking, TTS speaking, room/participant events, and raw data messages |

- Playground: https://agents-playground.livekit.io
- Console mode: `ENV_FILE=envs/.env.seller python worker.py console`

## Project Structure

```
cortana/
├── agents/          # SellerAgent, CustomerAgent — voice identity + handoff logic
├── config/          # Env loading, named profiles (voices, STT, LLM), logging
├── tools/           # @function_tools used by voice agents → TaskDispatcher
├── subagents/       # EmailSubAgent, CRMSubAgent, ChatSubAgent + dispatcher
├── worker.py        # Entrypoint, agent registry, AgentSession bootstrap
├── envs/            # .env.seller, .env.customer (gitignored) + .example files
├── demos/           # demo_server.py, demo.html — dev dashboard
├── scripts/         # get_token_for_play.py — generate LiveKit tokens
└── docs/            # design.md, progress.md, architecture diagrams
```

## Developer Tools (Claude Code)

This project is configured with a **LiveKit Agents skill** and a **LiveKit docs MCP server** for Claude Code.

### LiveKit Agents Skill — `/livekit-agents`

Invoke with `/livekit-agents` in Claude Code to get opinionated, context-aware guidance on:

- Structuring agent sessions and handoffs
- Implementing `@function_tool` tools
- Configuring STT / LLM / TTS plugin pipelines
- LiveKit Cloud + LiveKit Inference best practices

### LiveKit Docs MCP Server

The `livekit-docs` MCP server gives Claude Code direct access to the LiveKit documentation without leaving the editor. It exposes tools for:

| Tool | What it does |
| ---- | ------------ |
| `get_docs_overview` | Table of contents — good starting point for browsing |
| `get_pages` | Render any docs page (or GitHub file) to markdown |
| `docs_search` | Full-text search across all LiveKit docs |
| `get_changelog` | Recent releases for any LiveKit package |
| `get_python_agent_example` | Browse and fetch 100+ Python agent examples |
| `code_search` | grep-style search across LiveKit's public repos |

Example prompts that trigger these tools automatically:

```
What's the latest livekit-agents release?
Show me the multi-agent handoff docs.
Find an example of tool calling in a Python agent.
Search the agents repo for AgentSession.
```

## Documentation

- [agent.md](agent.md) — setup, running, tuning, swapping components
- [design.md](docs/design.md) — architecture, class design, dispatcher, session state
- [progress.md](docs/progress.md) — current status and deferred work
