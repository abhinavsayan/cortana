from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class SubAgentMode(Enum):
    FIRE_AND_FORGET  = "fire_and_forget"
    REQUEST_RESPONSE = "request_response"


class TaskTimeoutError(Exception):
    """Raised when a REQUEST_RESPONSE sub-agent exceeds its timeout."""


class BaseSubAgent(ABC):
    task_type: str            # key used in TaskDispatcher registry
    mode:      SubAgentMode
    timeout:   float = 8.0   # seconds — only meaningful for REQUEST_RESPONSE

    @abstractmethod
    async def run(self, payload: dict) -> dict:
        """Execute the task. Must return a result dict."""
