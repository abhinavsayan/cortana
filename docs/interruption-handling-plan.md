# Plan: Improve Interruption Handling (Config-Switchable)

> **Industry validation**: This two-layer approach (VAD word-count filter + LLM semantic classifier) matches what Vapi, Retell AI, and LiveKit use in production. LiveKit's own EOT model is a 135M-parameter transformer running at the same `on_user_turn_completed` hook. Our use of Groq as a fast classifier is the same trade-off — speed over a dedicated fine-tuned model.
>
> **Gaps vs. industry leaders** (all addressed in this plan):
> 1. No agent backchannel generation ("mm-hmm" during long user utterances) — Retell AI has a dedicated `backchannel_frequency` parameter for this *(deferred — separate feature)*
> 2. No interruption context preservation — Twilio explicitly tracks what the agent was saying when interrupted and passes it back to the LLM *(addressed in section 5)*
> 3. No non-interruptible windows — Google, Nuance, ElevenLabs all support per-utterance barge-in disabling *(addressed in section 6)*

---

## Context

Currently `AgentSession` has `min_interruption_words=0` (default), so any VAD-detected speech physically interrupts the agent. When a user says "okay" mid-speech, the agent stops, STT transcribes it, and the LLM generates a pointless response.

For a multilingual demo, two modes are useful:
- **`static`**: Keyword list — fast, no LLM cost, but phrase coverage is language-limited
- **`llm`**: Contextual LLM classifier — fully language-agnostic, uses conversation context, ~200ms latency cost

Both modes are gated by a single env var `INTERRUPTION_FILTER`. The static phrase list lives in its own config file so it can be extended without touching agent code.

---

## How the Two Layers Interact

| User says | Word count | Layer 1 (VAD) | Layer 2 (LLM/static) | Outcome |
|---|---|---|---|---|
| "okay" (1 word) | 1 | Blocked by `min_interruption_words=2` | Never fires | Agent continues |
| "yeah sure" (2 words) | 2 | Passes | Suppressed | Agent pauses, no reply |
| "wait, can you explain that?" | 5 | Passes | Let through | Agent stops, responds |
| "okay" after agent asked a question | 1 | Blocked | Never fires | User needs to say more |

> **Note on "stop"/"wait" single words**: Blocked by Layer 1 with `min_interruption_words=2`. In practice, users insistently stopping an agent say "wait wait" or "hold on please" (2+ words). Acceptable trade-off to avoid "okay" false positives.

---

## Cases Handled

| Scenario | `none` | `static` | `llm` |
|---|---|---|---|
| "okay" mid-speech | Agent stops + responds | Suppressed | Suppressed |
| "ठीक है" (Hindi) mid-speech | Agent stops + responds | Only if in config | Suppressed (LLM sees context) |
| "sí" (Spanish) mid-speech | Agent stops + responds | Only if in config | Suppressed |
| "wait, can you explain that?" | Agent stops + responds | Let through | Let through |
| "okay" after agent asked a question | Responds | **Suppressed (false positive!)** | Let through (context-aware) |
| Agent interrupted mid-sentence | No context recovery | No context recovery | Injects what agent was saying |

---

## Implementation

### 1. `config/settings.py` — Add config flag

```python
INTERRUPTION_FILTER: str = _optional("INTERRUPTION_FILTER", "llm")
# Values: "none" | "static" | "llm"
```

### 2. `config/interruption.py` — New file: phrase list lives here

```python
"""
Static backchannel phrase list for INTERRUPTION_FILTER=static mode.
Extend this list to add coverage for additional languages.
For full multilingual support, use INTERRUPTION_FILTER=llm instead.
"""

BACKCHANNEL_PHRASES: frozenset[str] = frozenset({
    # English
    "okay", "ok", "yeah", "yep", "yup", "yes", "sure", "alright", "right",
    "got it", "i see", "understood", "makes sense", "sounds good", "go on",
    "mm", "mm-hmm", "uh-huh", "mhm", "no problem", "of course",
    # Hindi
    "haan", "theek hai", "accha", "samajh gaya", "bilkul",
    # Spanish
    "sí", "claro", "entendido", "de acuerdo", "vale",
    # French
    "oui", "d'accord", "je vois", "bien sûr",
})
```

### 3. `worker.py` — Adjust `min_interruption_words` per mode

```python
from config.settings import settings

_MIN_WORDS = {
    "none":   0,   # current behaviour — any speech interrupts
    "static": 3,   # stricter physical filter, static list handles 2-word cases
    "llm":    2,   # permissive — LLM handles semantic classification
}

session = AgentSession(
    vad=silero.VAD.load(
        activation_threshold=0.7,
        min_speech_duration=0.15,
        min_silence_duration=0.6,
    ),
    turn_detection=MultilingualModel(),
    min_interruption_words=_MIN_WORDS.get(settings.INTERRUPTION_FILTER, 0),  # ADD
    min_interruption_duration=0.6,  # ADD
)
```

### 4. `agents/base.py` — Dual-mode `on_user_turn_completed`

**Add `_classifier_llm` in `__init__`** (before `super().__init__()`):

```python
from config.settings import settings
from config.profiles import LLM_MODELS

def __init__(self, tools=None, handoff_context=None):
    self._classifier_llm = (
        build_llm(LLM_MODELS["groq-fast"])
        if settings.INTERRUPTION_FILTER == "llm"
        else None
    )
    self._last_agent_speech: str = ""
    self._was_interrupted: bool = False
    super().__init__(...)
```

**Wire trackers in `on_enter`** (after `await self.greet(...)`):

```python
async def on_enter(self) -> None:
    # ... existing logging and greet() call ...
    self._register_interruption_tracker()
```

**Override `on_user_turn_completed`**:

```python
from livekit.agents import ChatContext, ChatMessage, StopResponse
from config.interruption import BACKCHANNEL_PHRASES

async def on_user_turn_completed(
    self, turn_ctx: ChatContext, new_message: ChatMessage
) -> None:
    mode = settings.INTERRUPTION_FILTER
    if mode == "none":
        return

    text = (new_message.text_content() or "").strip()
    if not text:
        raise StopResponse()

    if mode == "static":
        if text.lower().rstrip(".,!?") in BACKCHANNEL_PHRASES:
            self.log.info(f"[FILTER:static] suppressed: {text!r}")
            raise StopResponse()

    elif mode == "llm":
        if len(text.split()) > 8:  # long utterance — clearly real, skip classifier
            pass
        elif await self._classify_backchannel(turn_ctx, text):
            self.log.info(f"[FILTER:llm] suppressed: {text!r}")
            raise StopResponse()

    # Real turn — inject interruption context if agent was cut off
    if self._was_interrupted and self._last_agent_speech:
        turn_ctx.add_message(
            role="system",
            content=(
                f"Note: You were interrupted mid-response. "
                f"You had been saying: \"{self._last_agent_speech[:200]}\" "
                f"Acknowledge the user's input and continue naturally — do not repeat what you already said."
            )
        )
        self._was_interrupted = False
```

**Add `_classify_backchannel()` helper**:

```python
async def _classify_backchannel(self, turn_ctx: ChatContext, text: str) -> bool:
    """Returns True if the utterance is a backchannel that needs no response."""
    recent = turn_ctx.messages[-3:] if turn_ctx.messages else []
    ctx_lines = "\n".join(
        f"{m.role}: {m.text_content()}" for m in recent if m.text_content()
    )

    prompt = f"""Classify this voice conversation utterance.

Recent conversation:
{ctx_lines or "(just started)"}

User just said: "{text}"

Reply NO if it is a backchannel or filler that needs no response \
(e.g. "okay", "I see", "mm-hmm", mid-monologue acknowledgment in any language).
Reply YES if it is a question, correction, or direct response to a question the agent asked.

Reply with only YES or NO."""

    chat_ctx = ChatContext()
    chat_ctx.add_message(role="user", content=prompt)

    response = ""
    async for chunk in self._classifier_llm.chat(chat_ctx=chat_ctx):
        if chunk.delta and chunk.delta.content:
            response += chunk.delta.content

    return response.strip().upper().startswith("NO")
```

**Add `_register_interruption_tracker()` helper** (inspired by Twilio's `handleInterrupt()`):

```python
def _register_interruption_tracker(self) -> None:
    """Track last agent speech so we can inject context after interruption."""

    @self.session.on("conversation_item_added")
    def _track_agent_speech(ev) -> None:
        if ev.item.role == "assistant" and ev.item.text_content:
            self._last_agent_speech = ev.item.text_content
            self._was_interrupted = False

    @self.session.on("agent_speech_interrupted")
    def _mark_interrupted(_ev) -> None:
        self._was_interrupted = True
```

### 5. Non-Interruptible Windows (pattern, no new code)

For critical information (prices, legal disclaimers, account details), use LiveKit's built-in per-utterance control. This is already in the API — just a usage pattern:

```python
# In SellerAgent or CustomerAgent tool handlers:
await self.session.say("Your order total is $49.99.", allow_interruptions=False)
```

---

## Switching Modes (env var)

```
INTERRUPTION_FILTER=none    # baseline — current behaviour (for demo comparison)
INTERRUPTION_FILTER=static  # fast keyword list (extend config/interruption.py per language)
INTERRUPTION_FILTER=llm     # contextual LLM, default
```

---

## Critical Files

| File | Change |
|---|---|
| `config/settings.py` | Add `INTERRUPTION_FILTER` (1 line) |
| `config/interruption.py` | **New file** — backchannel phrase list |
| `worker.py` | `_MIN_WORDS` dict + 2 new `AgentSession` params |
| `agents/base.py` | `_classifier_llm`, `_last_agent_speech`, `_was_interrupted` in `__init__`; `on_user_turn_completed`, `_classify_backchannel`, `_register_interruption_tracker` as methods; wire in `on_enter` |

No changes to `seller.py`, `customer.py`, or `.env` files.

---

## What We Are Deliberately NOT Doing (and Why)

| Industry Feature | Why Skipping |
|---|---|
| **Agent backchannel generation** ("mm-hmm" during user speech) | Separate feature — requires interim `user_input_transcribed` events + timing. Low priority for demo |
| **Lightweight fine-tuned EOT model** (LiveKit's 135M SmolLM v2) | Optimization path — would replace Groq classifier but requires self-hosting. Groq at ~200ms is fine for demo |
| **Prosodic features** (pitch/energy) | Requires raw audio access. High complexity, marginal gain over LLM classifier |
| **Speaker diarization** | Only relevant for multi-speaker rooms |
| **Monitoring/metrics dashboard** | Production concern — `[FILTER:xxx]` log lines are sufficient for demo tuning |

---

## Verification

1. `python worker.py dev`
2. With `INTERRUPTION_FILTER=none`: say "okay" mid-speech → agent stops and responds (baseline)
3. With `static`: say "okay" mid-speech → suppressed; say "wait, can you explain?" → let through
4. With `static` limitation: agent asks "How does that sound?" → say "okay" → suppressed (known gap)
5. With `llm`: repeat steps 3–4; step 4 should now let through (context-aware)
6. With `llm`: interrupt agent mid-sentence with "wait, what was that?" → agent should acknowledge what it was saying before the interruption, not start fresh
7. Check logs: `[FILTER:static] suppressed:` or `[FILTER:llm] suppressed:`

---

## Industry References

- **Vapi** — "stop speaking" word count threshold (same as our `min_interruption_words`)
- **Retell AI** — `interruption_sensitivity` slider [0,1] + `backchannel_frequency` slider
- **LiveKit** — 135M SmolLM v2 transformer for EOT at `on_user_turn_completed` hook (39% fewer false positives)
- **Twilio ConversationRelay** — `handleInterrupt()` for interruption context tracking (our section 5)
- **Google Dialogflow CX** — phased barge-in (no-barge-in phase + barge-in phase)
- **ElevenLabs** — "turn eagerness" (eager/conservative) + per-utterance `allow_interruptions`
- **Nuance** — selective barge-in (keyword-matched) vs speech-based
