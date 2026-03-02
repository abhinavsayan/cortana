import os
import sys
from dotenv import load_dotenv

env_file = os.environ.get("ENV_FILE", "envs/.env")
load_dotenv(env_file)


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        print(f"[FATAL] Missing required env var: {key}  (file: {env_file})", file=sys.stderr)
        sys.exit(1)
    return val


def _optional(key: str, default: str) -> str:
    return os.getenv(key, default)


class Settings:
    AGENT_NAME:         str = _require("AGENT_NAME")
    LIVEKIT_URL:        str = _require("LIVEKIT_URL")
    LIVEKIT_API_KEY:    str = _require("LIVEKIT_API_KEY")
    LIVEKIT_API_SECRET: str = _require("LIVEKIT_API_SECRET")
    DEEPGRAM_API_KEY:   str = _require("DEEPGRAM_API_KEY")
    ELEVEN_API_KEY:     str = _require("ELEVEN_API_KEY")
    ANTHROPIC_API_KEY:  str = _require("ANTHROPIC_API_KEY")
    OLLAMA_BASE_URL:    str = _optional("OLLAMA_BASE_URL", "http://localhost:11434/v1")


settings = Settings()
