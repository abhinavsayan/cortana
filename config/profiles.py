from __future__ import annotations

import os
from dataclasses import dataclass

from livekit.plugins import anthropic, deepgram, elevenlabs, google, openai

_groq_url = "https://api.groq.com/openai/v1"


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class VoiceProfile:
    provider: str       # "elevenlabs" | "cartesia"
    voice_id: str
    model: str
    speed: float = 1.0


@dataclass
class STTProfile:
    provider: str       # "deepgram" | "elevenlabs"
    model: str
    language: str | None = "en"


@dataclass
class LLMProfile:
    provider: str       # "ollama" | "groq" | "openai" | "anthropic"
    model: str
    base_url: str | None = None
    temperature: float = 0.7


# ── Named presets ──────────────────────────────────────────────────────────────

VOICES: dict[str, VoiceProfile] = {
    "bella":  VoiceProfile(provider="elevenlabs", voice_id="EXAVITQu4vr4xnSDxMaL", model="eleven_turbo_v2_5"),
    "tripti": VoiceProfile(provider="elevenlabs", voice_id="1Z7Y8o9cvUeWq8oLKgMY", model="eleven_turbo_v2_5"),
    "adam":   VoiceProfile(provider="elevenlabs", voice_id="pNInz6obpgDQGcFmaJgB", model="eleven_turbo_v2_5"),
    "rachel": VoiceProfile(provider="elevenlabs", voice_id="21m00Tcm4TlvDq8ikWAM", model="eleven_turbo_v2_5"),
    "ember":   VoiceProfile(provider="elevenlabs", voice_id="WtA85syCrJwasGeHGH2p", model="eleven_turbo_v2_5"),
    "asteria": VoiceProfile(provider="deepgram", voice_id="", model="aura-asteria-en"),
    "luna":   VoiceProfile(provider="deepgram", voice_id="", model="aura-luna-en"),
}

STT_MODELS: dict[str, STTProfile] = {
    "deepgram-en":    STTProfile(provider="deepgram",    model="nova-3",   language="en"),
    "deepgram-es":    STTProfile(provider="deepgram",    model="nova-3",   language="es"),
    "elevenlabs-en":  STTProfile(provider="elevenlabs",  model="scribe_v1", language="en"),
    "elevenlabs-hi":   STTProfile(provider="elevenlabs", model="scribe_v1", language="hi"),
    "elevenlabs-auto": STTProfile(provider="elevenlabs", model="scribe_v1", language=None),
}

_ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

LLM_MODELS: dict[str, LLMProfile] = {
    "ollama-fast":       LLMProfile(provider="ollama",     model="mistral:latest",              base_url=_ollama_url),
    "ollama-smart":      LLMProfile(provider="ollama",     model="mistral:latest",              base_url=_ollama_url),
    "groq-fast":         LLMProfile(provider="groq",       model="llama-3.3-70b-versatile"),
    "openai":            LLMProfile(provider="openai",     model="gpt-4.1-mini"),
    "anthropic-fast":    LLMProfile(provider="anthropic",  model="claude-haiku-4-5-20251001"),
    "anthropic-smart":   LLMProfile(provider="anthropic",  model="claude-sonnet-4-6"),
    "gemini-flash":      LLMProfile(provider="google",     model="gemini-2.0-flash"),
    "gemini-flash-lite": LLMProfile(provider="google",     model="gemini-2.0-flash-lite"),
}


# ── Plugin factories ───────────────────────────────────────────────────────────

def build_tts(profile: VoiceProfile):
    if profile.provider == "elevenlabs":
        return elevenlabs.TTS(voice_id=profile.voice_id, model=profile.model)
    if profile.provider == "deepgram":
        return deepgram.TTS(model=profile.model)
    raise ValueError(f"Unknown TTS provider: {profile.provider!r}")


def build_stt(profile: STTProfile):
    if profile.provider == "deepgram":
        if profile.language is not None:
            return deepgram.STT(model=profile.model, language=profile.language, filler_words=False, smart_format=True)
        return deepgram.STT(model=profile.model, filler_words=False, smart_format=True)
    if profile.provider == "elevenlabs":
        if profile.language is not None:
            return elevenlabs.STT(model_id=profile.model, language_code=profile.language)
        return elevenlabs.STT(model_id=profile.model)
    raise ValueError(f"Unknown STT provider: {profile.provider!r}")


def build_llm(profile: LLMProfile):
    if profile.provider == "ollama":
        return openai.LLM.with_ollama(
            model=profile.model,
            base_url=profile.base_url or _ollama_url,
            temperature=profile.temperature,
        )
    if profile.provider == "groq":
        return openai.LLM(
            model=profile.model,
            base_url=_groq_url,
            api_key=os.environ["GROQ_API_KEY"],
            temperature=profile.temperature,
        )
    if profile.provider == "openai":
        return openai.LLM(model=profile.model, temperature=profile.temperature)
    if profile.provider == "anthropic":
        return anthropic.LLM(model=profile.model, temperature=profile.temperature)
    if profile.provider == "google":
        return google.LLM(model=profile.model, temperature=profile.temperature)
    raise ValueError(f"Unknown LLM provider: {profile.provider!r}")
