# Interruption Handling — Research, Decisions & Reasoning

A living document capturing the full research, design discussions, and reasoning behind the interruption handling improvements in Cortana's voice agents.

---

## The Problem

When the agent is mid-speech and the user says something short like "okay", the agent:
1. Physically stops speaking (VAD fires)
2. STT transcribes "okay"
3. The LLM processes "okay" as a full user turn
4. The agent generates a pointless response to it, wasting a turn

This is particularly painful for a multilingual agent — backchannels ("okay", "haan", "sí", "hai") vary by language and a static fix wouldn't generalise.

---

## Design Decisions & Reasoning

### Decision 1: Two-Layer Architecture

**What we decided**: Use two independent layers — a VAD-level word count filter and a semantic LLM classifier — rather than one.

**Why**: The two problems (agent physically stops + agent generates a bad response) happen at different points in the pipeline:
- Physical interruption: happens when VAD fires, before STT completes
- Turn commitment: happens after STT produces a final transcript

Solving only one leaves the other broken. `min_interruption_words` alone can't catch multi-word backchannels. An LLM classifier alone can't prevent the agent from physically stopping.

**Alternatives considered**:
- VAD threshold tuning only → doesn't solve LLM processing the backchannel
- Static phrase list in `user_input_transcribed` → multilingual problem, event timing uncertain
- Full LLM classifier only (no word count filter) → every single-word "okay" reaches the LLM, adds unnecessary latency

---

### Decision 2: `on_user_turn_completed` as the hook (not `user_input_transcribed`)

**What we decided**: Override the `on_user_turn_completed` method on the `Agent` class.

**Why**: This is the official LiveKit pipeline hook for intercepting turns before the LLM processes them. It receives:
- `turn_ctx` — the full `ChatContext` up to (but not including) the new message, giving conversation history for context-aware classification
- `new_message` — the user's utterance
- Supports `raise StopResponse()` to cleanly cancel the agent's reply

`user_input_transcribed` is an event handler. Calling `clear_user_turn()` from it has timing uncertainty — the turn may already be committed by the time the async handler runs. `on_user_turn_completed` is guaranteed to fire before the LLM is called.

**LiveKit's own approach**: LiveKit uses a 135M parameter SmolLM v2 transformer at exactly this hook for their end-of-utterance model. Our Groq classifier is the same pattern with a different model.

---

### Decision 3: Config-switchable modes (`INTERRUPTION_FILTER`)

**What we decided**: Three modes behind an env var — `none`, `static`, `llm`.

**Why (demo context)**: The demo needs to be able to show the difference between approaches, and the lightweight mode (static) should work even if Groq is unavailable or slow. Having `none` as a baseline also lets you isolate the improvement for a live comparison.

**Trade-offs**:

| Mode | Latency cost | Accuracy | Multilingual |
|---|---|---|---|
| `none` | 0ms | No filtering | N/A |
| `static` | 0ms | High for listed languages | Manually maintained |
| `llm` | ~150–250ms (Groq) | High across all languages | Automatic |

**The 8-word shortcut in `llm` mode**: Skip the classifier for utterances over 8 words — they're clearly real turns. Saves a Groq call on the majority of genuine user input.

---

### Decision 4: Static phrase list in its own config file

**What we decided**: `config/interruption.py` holds `BACKCHANNEL_PHRASES` as a `frozenset`.

**Why**: Keeping it in `agents/base.py` would mix configuration with logic. A separate config file means a product person (or the demo operator) can extend the list for a new language without touching agent code.

**Why `frozenset`**: O(1) lookup, immutable, semantically correct for a constant set.

**Known limitation of static mode**: Context-blindness. If the agent asks "How does that sound?" and the user says "okay", that IS a meaningful response. The static filter will suppress it. This is a documented trade-off — static mode is only suitable when the agent's conversation flow rarely ends in yes/no questions, or for quick demos where accuracy matters less than speed.

---

### Decision 5: Interruption context preservation (Twilio's pattern)

**What we decided**: Track `_last_agent_speech` and `_was_interrupted` via session events, inject what the agent was saying into the LLM context when a real interruption is processed.

**Why**: Without this, the LLM has no idea it was interrupted. It starts its reply fresh, which often results in the agent ignoring what it was doing and just responding to the interruption in isolation. This makes conversations feel broken.

**Twilio's ConversationRelay documentation** explicitly describes this as the core challenge: "AI systems generating text before speech conversion don't have context for in-progress conversations." Their `handleInterrupt()` function tracks the interrupted utterance and passes it to the next LLM call.

**Implementation detail**: We use `conversation_item_added` (fires when a turn is committed to history) and `agent_speech_interrupted` (fires when TTS is cut off). Together they give us: "what was the agent saying?" and "was it interrupted?".

---

### Decision 6: Multilingual via LLM, not phrase lists

**What we decided**: For full multilingual support, rely on the LLM classifier rather than maintaining per-language phrase lists.

**Why**: Backchannels are highly language-specific and culturally variable:
- Hindi: "haan", "theek hai", "accha", "bilkul"
- Japanese: "hai", "sō desu ne", "naruhodo"
- Spanish: "sí", "claro", "de acuerdo", "vale"
- Arabic: "na'am", "tayib", "mashi"
- Tamil: "aamā", "sari"

A Groq Llama 3.3-70b model trained on multilingual data handles all of these without any configuration. The static list in `config/interruption.py` covers a few languages for demonstration but is explicitly documented as limited.

---

### Decision 7: What we deliberately skipped

#### Agent backchannel generation ("mm-hmm" during user speech)
- **What it is**: The agent produces short acknowledgments while the *user* is speaking, to signal it's listening. Retell AI has a `backchannel_frequency` slider [0,1] for this.
- **Why skipped**: Entirely separate from backchannel *suppression*. Requires listening to interim `user_input_transcribed` events, timing the injection to avoid clashing with real speech, and carefully choosing when to generate vs. stay silent. Low priority for the current demo.
- **How it would work**: On `user_input_transcribed` (interim), if the user has been speaking for > 3 seconds with no turn-end signal, call `session.say("mm-hmm", add_to_chat_ctx=False)` to inject a filler without adding to conversation history.

#### Lightweight fine-tuned EOT model
- **What it is**: LiveKit ships a 135M parameter SmolLM v2 transformer for end-of-utterance detection with <29ms inference latency. NAMO Turn Detector v1 reports 97.3% accuracy.
- **Why skipped**: Requires self-hosting a model. Groq Llama 3.3-70b at ~200ms is sufficient for demo latency budgets. This is the upgrade path if we need <50ms classification in production.

#### Prosodic features (pitch, energy, duration)
- **What it is**: Academic research shows pitch reset + lengthening at sentence boundaries reduces EOT false positives by 9.15%.
- **Why skipped**: Requires raw audio frame access and DSP processing. High complexity for marginal gain over an LLM that implicitly understands prosody from transcription patterns.

#### Speaker diarization
- **What it is**: Identifying *who* is speaking to filter out background speech from other people in the room.
- **Why skipped**: This demo is 1:1 agent ↔ user. Irrelevant unless rooms have multiple human participants.

---

## Industry Research Summary

### What Market Leaders Do

#### Retell AI
- `interruption_sensitivity` slider [0,1] — lower = more words needed to interrupt
- Separate `backchannel_frequency` slider [0,1] — controls how often agent says "uh-huh"
- Sub-700ms response times when interrupted
- Uses Voice Activity Projection (VAP) model for backchannel timing

#### Vapi
- "Stop speaking" word count threshold (equivalent to `min_interruption_words`)
- VAD duration: default 0.2s before assistant stops
- Two-part pipeline: VAD + turn-taking prediction

#### ElevenLabs Conversational AI
- "Turn eagerness" setting: `eager` (fast-paced) vs `conservative` (waits for complete thoughts)
- Native backchannel support
- Per-utterance `allow_interruptions` flag

#### LiveKit (our platform)
- 135M parameter SmolLM v2 transformer for EOT at `on_user_turn_completed`
- Achieved **39.23% relative reduction in false-positive interruptions** (v0.4.1 vs v0.3.0)
- `false_interruption_timeout` + `resume_false_interruption` for pure-noise cases
- `min_interruption_words`, `min_interruption_duration` as first-pass filters

#### Google Dialogflow CX
- Two-phase barge-in: "no barge-in phase" (plays first N ms) then "barge-in phase"
- Barge-in set at fulfillment level, cascades through message queue
- Billing implication: dual Input + Output billing during barge-in (watch for cost spikes)

#### Twilio ConversationRelay
- Token streaming to reduce first-byte latency
- `handleInterrupt()` explicitly tracks interrupted utterance and passes to next LLM call
- Supports OpenAI, Anthropic, Mistral integrations with context-aware recovery

#### Nuance / Microsoft NVP
- Three barge-in types: Speech (any speech), Selective (ASR-matched keyword), Hotword
- Best practice: enable for experienced users, disable for legal disclaimers/safety messages

#### Amazon Lex/Connect
- Barge-in enabled globally by default
- Session attributes for granular control: `x-amz-lex:allow-interrupt:<intent>:<slot>`

#### Deepgram (Flux model)
- Single model responsible for both transcription AND conversational flow
- Configurable EOT parameters: `eot_threshold`, `eager_eot_threshold`, `eot_timeout_ms`
- Bi-directional streaming with native turn prediction

---

### Academic Research Highlights

**End-of-Turn Detection**
- NAMO Turn Detector v1: 97.3% accuracy, <29ms inference — semantic over silence-based
- LiveKit SmolLM v2: 135M params, sliding 4-turn context window
- Thai Semantic EOT (arXiv 2024): LLM prompting outperforms silence-based VAD for non-English
- Key finding: "Silence-based VAD is fast but brittle" — understanding *why* there's silence is what matters

**Backchannel Research**
- "Yeah, Right, Uh-Huh" (deep learning backchannel predictor): trained model on when and what backchannels to generate
- Voice Activity Projection (VAP): real-time model with backchannel probability; Z-score peak detection for timing
- "A Robot That Listens" (arXiv 2024): sentiment-based backchannels improve engagement over generic "mm-hmm"

**Prosodic Features**
- Inter-syllable boundary features: pitch, energy, duration at boundaries predict interruption points
- Pitch reset + lengthening: 9.15% improvement in EOT detection accuracy
- Less adopted in consumer platforms vs. specialised telecom solutions

**Full-Duplex Models**
- NVIDIA PersonaPlex: simultaneously listens and speaks, learns natural backchannel timing implicitly
- Direction the industry is moving: replace explicit turn detection with full-duplex understanding

---

### Known Failure Modes in Production (from practitioner reports)

1. **Breathing/throat clearing**: passes VAD threshold, STT produces nothing → false interruption timeout handles this
2. **Background noise**: dog barks, car horns at phone mic level → VAD fires, no words → false interruption timeout
3. **Network jitter**: mobile networks add 150–300ms packet delay → if endpointing threshold < 150ms, phantom turn-taking. Fix: `min_silence_duration=0.6+` in production
4. **Context loss after interruption**: agent resumes fresh, ignores what it was doing → addressed by our context preservation
5. **"Thinking pause" misread as turn end**: user pauses 2s mid-sentence → VAD fires → agent jumps in. Turn detection model (not just VAD) mitigates this.
6. **Monitoring blindness**: most teams detect interruption quality failures from user complaints, not metrics. Standard APM tools miss turn-taking quality entirely.

**Production targets cited**:
- Sub-100ms interruption response (industry-leading)
- Sub-200ms for natural conversation feel
- Sub-700ms is Retell's stated benchmark
- 300ms+ breaks immersion noticeably

---

### The Hybrid Architecture Pattern (industry consensus)

```
VAD (Fast baseline — any speech)
  ↓
min_interruption_words (Word count — blocks obvious single-word fillers)
  ↓
on_user_turn_completed (Semantic — LLM/transformer classifies in context)
  ↓
Interruption context injection (LLM gets what agent was saying)
  ↓
StopResponse() or let through
```

All market leaders use 2–4 techniques in combination. No single technique is sufficient.

---

## Open Questions / Future Work

| Question | Notes |
|---|---|
| Should `min_interruption_words` be tunable per-agent? | SellerAgent vs CustomerAgent might want different sensitivity. Currently global via env var. |
| Is Groq always available in production? | If Groq is down, `llm` mode falls through without classification. Add a `static` fallback. |
| Backchannel generation threshold | When user speaks > Ns, inject "mm-hmm". What's the right N for this demo? |
| `agent_speech_interrupted` event name | Needs verification against actual LiveKit Python SDK — may differ from assumed name. |
| Monitoring | Add `[FILTER:xxx]` log parsing to demo dashboard to show suppression rate live. |
