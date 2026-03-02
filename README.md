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
cp .env.seller.example .env.seller
cp .env.customer.example .env.customer

# 5. Run an agent
ENV_FILE=.env.seller python worker.py dev
```

Required env vars: `AGENT_NAME`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, `ELEVEN_API_KEY`

### Test in the browser

- Playground: https://agents-playground.livekit.io
- Console mode: `ENV_FILE=.env.seller python worker.py console`

## Project Structure

```
cortana/
├── agents/          # SellerAgent, CustomerAgent — voice identity + handoff logic
├── config/          # Env loading, named profiles (voices, STT, LLM), logging
├── tools/           # @function_tools used by voice agents → TaskDispatcher
├── subagents/       # EmailSubAgent, CRMSubAgent, ChatSubAgent + dispatcher
└── worker.py        # Entrypoint, agent registry, AgentSession bootstrap
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
- [design.md](design.md) — architecture, class design, dispatcher, session state
- [progress.md](progress.md) — current status and deferred work
