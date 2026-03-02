from __future__ import annotations

import logging

from subagents.base import BaseSubAgent, SubAgentMode

log = logging.getLogger(__name__)


class ChatSubAgent(BaseSubAgent):
    """Placeholder — chat sub-agent is TBD."""
    task_type = "chat"
    mode      = SubAgentMode.REQUEST_RESPONSE

    async def run(self, payload: dict) -> dict:
        log.warning("ChatSubAgent.run called but not yet implemented")
        return {"status": "not_implemented"}
