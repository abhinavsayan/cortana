from __future__ import annotations

import asyncio
import logging

from subagents.base import BaseSubAgent, TaskTimeoutError

log = logging.getLogger(__name__)


class TaskDispatcher:
    def __init__(self):
        self._registry: dict[str, BaseSubAgent] = {}

    def register(self, agent: BaseSubAgent) -> None:
        self._registry[agent.task_type] = agent
        log.debug(f"registered sub-agent task_type={agent.task_type!r}")

    async def fire(self, task_type: str, payload: dict) -> None:
        """Fire and forget. Voice agent does not wait for result."""
        agent = self._registry[task_type]
        asyncio.create_task(agent.run(payload))

    async def request(self, task_type: str, payload: dict) -> dict:
        """Blocking call. Raises TaskTimeoutError if sub-agent exceeds its timeout."""
        agent = self._registry[task_type]
        try:
            return await asyncio.wait_for(agent.run(payload), timeout=agent.timeout)
        except asyncio.TimeoutError:
            raise TaskTimeoutError(f"{task_type} did not respond within {agent.timeout}s")
